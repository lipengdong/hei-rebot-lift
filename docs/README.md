# HEI ReBot Lift Documentation

[English](README.md) | [中文](README_zh.md)

## Start Here

Follow this order: prepare hardware, deploy environments, test pure simulation,
verify hardware independently, test real teleoperation, record data, then train
and run a policy. Real startup automatically homes the lift; clear the workspace
and keep the emergency stop reachable.

| Topic | Guide | Contents |
| --- | --- | --- |
| Project and quick setup | [Project README](../README.md) | Hardware overview, environments, startup order |
| Hardware reproduction | [Hardware guide](../hardware/README.md) | BOM, full STEP assembly, printed and metal parts |
| Robot configuration | [Driver guide](../software/lerobot-hei-rebot-lift/src/lerobot/robots/hei_rebot_lift/README.md) | Device mapping, motor parameters, lift units, watchdog |
| VR deployment and use | [VR + MuJoCo IK](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/README.md) | Pinocchio/CasADi installation, controller inputs, safe arming, troubleshooting |
| Model and controller entry points | [MuJoCo IK guide](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/mujoco_ik/README.md) | Complete-model simulation/real mode, legacy dual-arm entry, self-checks |
| Debugging and data collection | [Examples guide](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README.md) | Port binding, lift/chassis tests, recording, resume, cleanup |
| Training and inference | [Examples guide](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README.md) | ACT/SmolVLA, checkpoint paths, replay, evaluate, rollout |
| Reproduction and collaboration | [Community](../community/README.md) | WeChat group, contact details, QR code |
| Jetson system icon troubleshooting | [Missing-icon repair record](jetson_system_icons.md) | SVG decoding, interrupted dpkg configuration, recovery and prevention |

## README Map and Maintenance

Each guide has a different scope; synchronization means matching instructions
and shared facts, not copying the entire homepage into every submodule.

| Location (from repository root) | English | Chinese | Scope |
| --- | --- | --- | --- |
| Repository root | [README.md](../README.md) | [README_zh.md](../README_zh.md) | First deployment, simulation practice, real startup; also [French](../README_Fr.md) and [Spanish](../README_es.md) |
| `hardware/` | [Guide](../hardware/README.md) | [Guide](../hardware/README_zh.md) | BOM, CAD, assembly and power-on checks |
| `docs/` | [Index](README.md) | [Index](README_zh.md) | Documentation navigation and maintenance |
| `community/` | [Guide](../community/README.md) | [Guide](../community/README_zh.md) | Contact details and group QR code |
| `media/` | [Guide](../media/README.md) | [Guide](../media/README_zh.md) | Images, GIFs, controller diagrams and static Star History |
| Software root | [Guide](../software/lerobot-hei-rebot-lift/README.md) | [Guide](../software/lerobot-hei-rebot-lift/README_zh.md) | Software module navigation; deployment links to the homepage |
| HEI examples | [Guide](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README.md) | [Guide](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README_zh.md) | Debugging, recording, datasets, training, replay/evaluate/rollout |
| VR/IK root | [Guide](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/README.md) | [Guide](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/README_zh.md) | VR environment, controller tutorial, simulation and real bridge |
| Telegrip | [Guide](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/telegrip/README.md) | [Guide](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/telegrip/README_zh.md) | WebXR bridge and image-display configuration |
| MuJoCo IK | [Guide](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/mujoco_ik/README.md) | [Guide](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/mujoco_ik/README_zh.md) | Complete-model vs. legacy entries and offline tests |
| Complete URDF model | [Guide](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/mujoco_ik/model/HEI_robot_urdf/README.md) | [Guide](../software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/mujoco_ik/model/HEI_robot_urdf/README_zh.md) | Joint inspection, visualization, TCP/gripper conventions, MJCF export |
| Robot driver | [Guide](../software/lerobot-hei-rebot-lift/src/lerobot/robots/hei_rebot_lift/README.md) | [Guide](../software/lerobot-hei-rebot-lift/src/lerobot/robots/hei_rebot_lift/README_zh.md) | Device config, protocol units, motor parameters, homing and watchdog |

When changing installation or startup, update all four homepages. When changing
controller behavior, update the VR guide pair and homepage controller summaries.
When changing driver defaults, update the driver guide pair and any numerical
examples in the VR/homepage guides. Source code and `environment.yml` take
precedence over copied documentation values.

General LeRobot policy, Docker, and other-robot READMEs remain outside this HEI
guide set. The previously discussed standalone D435/audio examples are not in
this checkout and are not advertised as available deployment steps.

## Important Conventions

- Follow each guide's working-directory instructions; paths are relative, not tied to a particular home directory.
- Robot IP and computer IP are different settings. `--remote-ip` changes the LeRobot client connection; configure the VR camera endpoint separately in `telegrip/config.yaml`.
- Run only one robot command source. Stop teleoperation before recording; stop VR control and recording before replay or policy inference.
- Workspace projection and joint limits are not collision avoidance. The stable-grasp scene is a kinematic demonstration, not proof of physical grasp stability.
- Local data is not uploaded by default. Back up datasets before deleting episodes or changing camera schemas.

Additional assembly, wiring, and video tutorials can be linked here when available.
