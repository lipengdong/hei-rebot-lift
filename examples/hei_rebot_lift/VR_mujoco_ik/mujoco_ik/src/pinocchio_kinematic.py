# This code builds upon following:
# https://github.com/unitreerobotics/xr_teleoperate/blob/main/teleop/robot_control/robot_arm_ik.py
# https://github.com/ccrpRepo/mocap_retarget/blob/master/src/mocap/src/robot_ik.py

import casadi          
import numpy as np
import os
import pinocchio as pin
from pinocchio import casadi as cpin                


# IK 连续性权重：前两个关节更容易出现解支跳变，所以给更高平滑惩罚。
# 数值越大，该关节越不愿意偏离上一帧；太大可能会降低末端跟踪能力。
IK_SMOOTH_WEIGHT_FIRST_TWO = 8.0
# 其它关节的连续性权重，通常低于前两个关节，让手腕/肘部承担更多姿态调整。
IK_SMOOTH_WEIGHT_OTHER = 2.0
# 整体 smooth cost 在 IK 目标函数中的权重；增大整体更稳，减小整体更跟手。
IK_SMOOTH_COST_WEIGHT = 0.005

# IK 输出单步限幅，单位 rad/次 IK。前两个关节更小，防止肩部/底座突然大幅跳动。
# 数值越小越防突变，但目标变化快时会更慢追上。
IK_MAX_STEP_FIRST_TWO = 0.06
# 其它关节单次 IK 允许变化的最大弧度。
IK_MAX_STEP_OTHER = 0.12


def _env_float(name, default):
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name, default):
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in ("1", "true", "yes", "on")


class Kinematics:
    def __init__(self, ee_frame) -> None:
        self.frame_name = ee_frame
        self.verbose = _env_bool("SAM101_KIN_VERBOSE", False)
        self.full_model_nq = None
        self.active_q_indices = None
        self.reference_q = None

    def buildFromMJCF(self, mcjf_file, active_q_indices=None, reference_q=None):
        # self.arm = pin.RobotWrapper.BuildFromMJCF(mcjf_file)
        self.arm = pin.RobotWrapper.BuildFromURDF(
            mcjf_file,
            package_dirs=[os.path.dirname(os.path.abspath(mcjf_file))],
        )
        self._maybe_reduce_robot(active_q_indices, reference_q)
        if self.verbose:
            print(self.arm.model)
            print("可用的帧名称：")
            for i in range(self.arm.model.nframes):
                frame = self.arm.model.frames[i]
                print(f"  [{i}] {frame.name}")
        self.createSolver()

    def buildFromURDF(self, urdf_file, active_q_indices=None, reference_q=None):
        self.arm = pin.RobotWrapper.BuildFromURDF(
            urdf_file,
            package_dirs=[os.path.dirname(os.path.abspath(urdf_file))],
        )
        self._maybe_reduce_robot(active_q_indices, reference_q)
        if self.verbose:
            print("可用的帧名称：")
            for i in range(self.arm.model.nframes):
                frame = self.arm.model.frames[i]
                print(f"  [{i}] {frame.name}")
        self.createSolver()

    def _maybe_reduce_robot(self, active_q_indices, reference_q):
        self.full_model_nq = self.arm.model.nq
        self.active_q_indices = None
        self.reference_q = None
        if active_q_indices is None:
            return

        self.active_q_indices = np.asarray(active_q_indices, dtype=int)
        self.reference_q = np.asarray(reference_q, dtype=float).copy()
        if self.reference_q.shape[0] != self.full_model_nq:
            raise ValueError(
                f"reference_q length {self.reference_q.shape[0]} does not match "
                f"full model nq {self.full_model_nq}"
            )

        active = set(self.active_q_indices.tolist())
        joints_to_lock = []
        for joint_id in range(1, self.arm.model.njoints):
            q_start = self.arm.model.idx_qs[joint_id]
            q_stop = q_start + self.arm.model.nqs[joint_id]
            if all(q_index not in active for q_index in range(q_start, q_stop)):
                joints_to_lock.append(self.arm.model.names[joint_id])

        self.arm = self.arm.buildReducedRobot(joints_to_lock, self.reference_q)
        if self.verbose:
            print(
                f"Reduced '{self.frame_name}' model: full nq={self.full_model_nq}, "
                f"active nq={self.arm.model.nq}, locked joints={joints_to_lock}"
            )

    def _to_model_q(self, q):
        q = np.asarray(q, dtype=float)
        if self.active_q_indices is None:
            return q.copy()
        if q.shape[0] == self.model.nq:
            return q.copy()
        if q.shape[0] == self.full_model_nq:
            return q[self.active_q_indices].copy()
        raise ValueError(
            f"q length {q.shape[0]} does not match reduced nq {self.model.nq} "
            f"or full nq {self.full_model_nq}"
        )

    def _to_full_q(self, reduced_q, fallback_q=None):
        reduced_q = np.asarray(reduced_q, dtype=float)
        if self.active_q_indices is None:
            return reduced_q.copy()
        if fallback_q is not None and len(fallback_q) == self.full_model_nq:
            full_q = np.asarray(fallback_q, dtype=float).copy()
        else:
            full_q = self.reference_q.copy()
        full_q[self.active_q_indices] = reduced_q
        return full_q

    def _smooth_weights(self):
        weights = np.full(self.model.nq, _env_float("IK_SMOOTH_WEIGHT_OTHER", IK_SMOOTH_WEIGHT_OTHER))
        weights[:min(2, self.model.nq)] = _env_float(
            "IK_SMOOTH_WEIGHT_FIRST_TWO",
            IK_SMOOTH_WEIGHT_FIRST_TWO,
        )
        return weights

    def _max_step_limits(self):
        limits = np.full(self.model.nq, _env_float("IK_MAX_STEP_OTHER", IK_MAX_STEP_OTHER))
        limits[:min(2, self.model.nq)] = _env_float(
            "IK_MAX_STEP_FIRST_TWO",
            IK_MAX_STEP_FIRST_TWO,
        )
        return limits

    def _limit_joint_step(self, sol_q, current_q):
        max_step = self._max_step_limits()
        delta = np.asarray(sol_q, dtype=float) - np.asarray(current_q, dtype=float)
        limited_delta = np.clip(delta, -max_step, max_step)
        limited_q = current_q + limited_delta
        limited_q = np.clip(limited_q, self.model.lowerPositionLimit, self.model.upperPositionLimit)
        clamped = bool(np.any(np.abs(delta - limited_delta) > 1e-9))
        return limited_q, clamped

    def getJac(self, q):
        q = self._to_model_q(q)
        pin.forwardKinematics(self.model, self.data, q)
        pin.updateFramePlacements(self.model, self.data)
        J = pin.computeFrameJacobian(self.model, self.data, q, self.ee_id, pin.ReferenceFrame.WORLD)
        return J

    def createSolver(self):
        self.model = self.arm.model
        self.data = self.arm.data

        # Creating Casadi models and data for symbolic computing
        self.cmodel = cpin.Model(self.model)
        self.cdata = self.cmodel.createData()

        # Creating symbolic variables
        self.cq = casadi.SX.sym("q", self.model.nq, 1) 
        self.cTf = casadi.SX.sym("tf", 4, 4)
        cpin.framesForwardKinematics(self.cmodel, self.cdata, self.cq)
        
        # Get the hand joint ID and define the error function
        try:
            self.ee_id = self.model.getFrameId(self.frame_name)
            if self.verbose:
                print(f"成功找到帧 '{self.frame_name}'，ID为 {self.ee_id}")
        except Exception as e:
            print(f"找不到帧 '{self.frame_name}'：{e}")
            print("可用的帧：")
            for i in range(self.model.nframes):
                print(f"  [{i}] {self.model.frames[i].name}")
            raise

        # 在Casadi模型中获取帧ID
        try:
            self.c_ee_id = self.cmodel.getFrameId(self.frame_name)
            if self.verbose:
                print(f"在Casadi模型中成功找到帧 '{self.frame_name}'，ID为 {self.c_ee_id}")
        except Exception as e:
            print(f"在Casadi模型中找不到帧 '{self.frame_name}'：{e}")
            print("Casadi模型中可用的帧：")
            for i in range(self.cmodel.nframes):
                print(f"  [{i}] {self.cmodel.frames[i].name}")
            raise

        self.translational_error = casadi.Function(
            "translational_error",
            [self.cq, self.cTf],
            [
                casadi.vertcat(
                    self.cdata.oMf[self.c_ee_id].translation - self.cTf[:3,3]
                )
            ],
        )
        # Use a small-angle-friendly SO(3) residual. cpin.log3() goes through
        # acos(trace(R)) and can produce NaN gradients exactly at R ~= I.
        rot_mat = self.cdata.oMf[self.c_ee_id].rotation @ self.cTf[:3, :3].T
        rot_err = 0.5 * casadi.vertcat(
            rot_mat[2, 1] - rot_mat[1, 2],
            rot_mat[0, 2] - rot_mat[2, 0],
            rot_mat[1, 0] - rot_mat[0, 1],
        )
        self.rotational_error = casadi.Function(
            "rotational_error",
            [self.cq, self.cTf],
            [
                rot_err
            ],
        )

        # Defining the optimization problem
        self.opti = casadi.Opti()
        self.var_q = self.opti.variable(self.model.nq)
        self.var_q_last = self.opti.parameter(self.model.nq)   # for smooth
        self.param_tf = self.opti.parameter(4, 4)
        self.translational_cost = casadi.sumsqr(self.translational_error(self.var_q, self.param_tf))
        self.rotation_cost = casadi.sumsqr(self.rotational_error(self.var_q, self.param_tf))
        self.regularization_cost = casadi.sumsqr(self.var_q)
        smooth_weight_matrix = casadi.diag(casadi.DM(self._smooth_weights()))
        weighted_smooth_error = casadi.mtimes(
            smooth_weight_matrix,
            self.var_q - self.var_q_last,
        )
        self.smooth_cost = casadi.sumsqr(weighted_smooth_error)

        # Setting optimization constraints and goals
        self.opti.subject_to(self.opti.bounded(
            self.model.lowerPositionLimit,
            self.var_q,
            self.model.upperPositionLimit)
        )
        self.opti.minimize(
            20.0 * self.translational_cost
            + 0.01 * self.rotation_cost
            + 0.00 * self.regularization_cost
            + _env_float("IK_SMOOTH_COST_WEIGHT", IK_SMOOTH_COST_WEIGHT) * self.smooth_cost
        )

        ##### IPOPT #####
        opts = {
            'ipopt':{
                'print_level': 0,
                'max_iter': _env_int("SAM101_IPOPT_MAX_ITER", 80),
                'tol': _env_float("SAM101_IPOPT_TOL", 1e-4),
                'acceptable_tol': _env_float("SAM101_IPOPT_ACCEPTABLE_TOL", 5e-4),
                'acceptable_iter': _env_int("SAM101_IPOPT_ACCEPTABLE_ITER", 3),
                'hessian_approximation': "limited-memory",
            },
            'print_time':False,# print or not
            'calc_lam_p':False # https://github.com/casadi/casadi/wiki/FAQ:-Why-am-I-getting-%22NaN-detected%22in-my-optimization%3F
        }
        self.opti.solver("ipopt", opts)

        self.init_data = np.zeros(self.model.nq)

    def fk(self, q):
        q = self._to_model_q(q)
        pin.forwardKinematics(self.model, self.data, q)
        pin.updateFramePlacements(self.model, self.data)
        # tf = pin.SE3ToXYZQUAT(self.data.oMf[self.ee_id])
        se3_obj = self.data.oMf[self.ee_id]
        tf = np.eye(4, dtype=np.float64)
        tf[:3, :3] = se3_obj.rotation
        tf[:3, 3] = se3_obj.translation
        return tf
      
    def ik(self, T , current_arm_motor_q = None, current_arm_motor_dq = None):
        fallback_q = current_arm_motor_q
        if current_arm_motor_q is not None:
            self.init_data = self._to_model_q(current_arm_motor_q)
        current_model_q = self.init_data.copy()
        self.opti.set_initial(self.var_q, self.init_data)

        self.opti.set_value(self.param_tf, T)
        self.opti.set_value(self.var_q_last, self.init_data) # for smooth

        try:
            sol = self.opti.solve()
            # sol = self.opti.solve_limited()

            raw_sol_q = self.opti.value(self.var_q)
            sol_q, clamped = self._limit_joint_step(raw_sol_q, current_model_q)
            # self.smooth_filter.add_data(sol_q)
            # sol_q = self.smooth_filter.filtered_data

            if current_arm_motor_dq is not None:
                v = self._to_model_q(current_arm_motor_dq) * 0.0
            else:
                v = (sol_q - self.init_data) * 0.0

            self.init_data = sol_q

            sol_tauff = pin.rnea(self.model, self.data, sol_q, v, np.zeros(self.model.nv))
            sol_tauff = np.concatenate([sol_tauff, np.zeros(self.model.nq - sol_tauff.shape[0])], axis=0)
            
            info = {"sol_tauff": sol_tauff, "success": True, "clamped": clamped}

            dof = self._to_full_q(sol_q, fallback_q)
            return dof, info
        
        except Exception as e:
            print(f"ERROR in convergence, plotting debug info.{e}")

            sol_q = self.opti.debug.value(self.var_q)
            # self.smooth_filter.add_data(sol_q)
            # sol_q = self.smooth_filter.filtered_data

            if current_arm_motor_dq is not None:
                v = self._to_model_q(current_arm_motor_dq) * 0.0
            else:
                v = (sol_q - self.init_data) * 0.0

            self.init_data = sol_q

            sol_tauff = pin.rnea(self.model, self.data, sol_q, v, np.zeros(self.model.nv))
            # import ipdb; ipdb.set_trace()
            sol_tauff = np.concatenate([sol_tauff, np.zeros(self.model.nq - sol_tauff.shape[0])], axis=0)

            print(f"sol_q:{sol_q} \nmotorstate: \n{current_arm_motor_q} \ntarget_pose: \n{T}")

            info = {"sol_tauff": sol_tauff * 0.0, "success": False, "clamped": False}

            dof = np.zeros(self.model.nq)
            if current_arm_motor_q is not None:
                dof = self._to_full_q(self._to_model_q(current_arm_motor_q), current_arm_motor_q)
                self.init_data = self._to_model_q(current_arm_motor_q)
            else:
                dof = self._to_full_q(sol_q)

            return dof, info

if __name__ == "__main__":
    import sys, os
    sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    import src.utils as utils

    # 左右臂分别进行IK和FK计算
    print("=== 左臂 IK/FK 计算 ===")
    left_arm = Kinematics("left_Link7")
    left_arm.buildFromMJCF("../model/hgm_robot/urdf/hgm_robot.urdf")
    
    # 设置左臂目标位姿
    left_target = utils.transform2mat(0.3, -0.3, 0.5, np.pi, 0, 0)
    print(f"左臂目标位姿：\n{left_target}")
    
    try:
        # 左臂IK求解
        left_dof, left_info = left_arm.ik(left_target)
        print(f"左臂IK结果：\n{np.array2string(left_dof, precision=3, suppress_small=True)}")
        print(f"左臂IK成功：{left_info['success']}")
        
        # 左臂FK验证
        dof = np.zeros(16)
        left_fk = left_arm.fk(dof)
        print(f"左臂FK结果：\n{np.array2string(left_fk, precision=3, suppress_small=True)}")
    except Exception as e:
        print(f"左臂IK/FK计算失败：{e}")

    print("\n=== 右臂 IK/FK 计算 ===")
    right_arm = Kinematics("right_Link7")
    right_arm.buildFromMJCF("../model/hgm_robot/urdf/hgm_robot.urdf")
    
    # 设置右臂目标位姿
    right_target = utils.transform2mat(0.3, 0.3, 0.5, np.pi, 0, 0)
    print(f"右臂目标位姿：\n{right_target}")
    
    try:
        # 右臂IK求解
        right_dof, right_info = right_arm.ik(right_target)
        print(f"右臂IK结果：\n{np.array2string(right_dof, precision=3, suppress_small=True)}")
        print(f"右臂IK成功：{right_info['success']}")
        
        # 右臂FK验证
        right_fk = right_arm.fk(right_dof)
        print(f"右臂FK结果：\n{np.array2string(right_fk, precision=3, suppress_small=True)}")
    except Exception as e:
        print(f"右臂IK/FK计算失败：{e}")
