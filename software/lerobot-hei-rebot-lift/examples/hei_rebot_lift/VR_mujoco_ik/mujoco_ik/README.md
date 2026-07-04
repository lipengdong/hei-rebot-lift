# MuJoCo IK

This is the MuJoCo + Pinocchio IK submodule in the HEI ReBot Lift VR teleoperation pipeline.

For unified deployment, dependency installation, and startup flow, see the parent document:

```text
../README.md
```

Common startup command:

```bash
cd ..
bash run_mujoco_ik.sh
```

Note: install `pinocchio`, `casadi`, `eigenpy`, and `coal-python` from the conda-forge versions defined in the parent `environment.yml`. Do not install `pin` separately with pip in this folder.

## Chinese Version

- [README_zh.md](README_zh.md)
