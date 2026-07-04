# MuJoCo IK

这是 HEI ReBot Lift VR 遥操作链路里的 MuJoCo + Pinocchio IK 子模块。

统一部署、依赖安装和启动流程请看上一级文档：

```text
../README.md
```

常用启动方式：

```bash
cd ..
bash run_mujoco_ik.sh
```

注意：`pinocchio`、`casadi`、`eigenpy`、`coal-python` 请使用上级 `environment.yml` 里的 conda-forge 版本安装，不要在这里单独 `pip install pin`。
