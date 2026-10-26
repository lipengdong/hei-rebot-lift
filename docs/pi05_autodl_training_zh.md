# AutoDL RTX PRO 6000 训练与异步部署 Pi0.5

本文记录如何在 AutoDL RTX PRO 6000（48 GB 显存）服务器上，使用已经采集好的
HEI ReBot Lift 真机数据微调 LeRobot Pi0.5，并通过 SSH 隧道把服务器推理结果
发送给真实机器人。训练采用“冻结 VLM、只训练动作专家和投影层”的方案。

服务器、控制电脑和 Jetson 均建议使用本项目中的同一版
`software/lerobot-hei-rebot-lift`，避免策略配置、数据集模块和异步协议版本不一致。

## 1. 训练结构

服务器只负责数据读取和策略训练，不连接机器人，也不启动
`hei-rebot-lift-host`。当前训练链路为：

```text
HEI LeRobotDataset
  ├── observation.images.front
  ├── observation.images.left_wrist
  ├── observation.images.right_wrist
  ├── observation.state（18 维）
  ├── action（18 维）
  └── task
             ↓
        Pi0.5 base
             ↓
  冻结 PaliGemma VLM
  训练动作专家和投影层
```

Pi0.5 会在内部把状态和动作补齐到 32 维，损失只作用于数据集真实提供的
维度。这里使用逐维 `MEAN_STD` 标准化，可以处理升降与关节数值量级不同的
情况。

推理时的三端链路为：

```text
Jetson 机器人端（192.168.31.203）
  └── hei-rebot-lift-host：控制硬件、发布状态和三路图像
                    ↕ 局域网 ZMQ 6555/6556
控制电脑
  └── async robot_client：整理观测、接收动作并发送给机器人
                    ↕ SSH 加密隧道 127.0.0.1:18080
AutoDL 服务器
  └── policy_server：加载 Pi0.5 检查点，在 GPU 上推理
```

`192.168.31.203` 是当前 Jetson 的局域网地址。如果机器人 IP 发生变化，以
Jetson 上 `hostname -I` 的结果为准。

## 2. 目录规划

AutoDL 系统盘空间有限，数据集、模型缓存和训练结果统一放到数据盘：

```text
/root/autodl-tmp/
├── HGM/
│   └── hei-rebot-lift/
│       └── software/lerobot-hei-rebot-lift/   # 本项目 LeRobot 源码
├── huggingface/
│   ├── hub/                                   # Hugging Face 模型缓存
│   └── lerobot/HGM/
│       └── hei_rebot_lift_task1/              # 本地真机数据集
└── outputs/                                   # 训练结果
```

设置环境变量：

```bash
export PROJECT_ROOT=/root/autodl-tmp/HGM/hei-rebot-lift
export LEROBOT_DIR="$PROJECT_ROOT/software/lerobot-hei-rebot-lift"
export DATASET_ROOT=/root/autodl-tmp/huggingface/lerobot/HGM/hei_rebot_lift_task1
export OUTPUT_ROOT=/root/autodl-tmp/outputs
export HF_HOME=/root/autodl-tmp/huggingface
export HF_LEROBOT_HOME=/root/autodl-tmp/huggingface/lerobot
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
```

检查 GPU 和 BF16：

```bash
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
python -c "import torch; print(torch.__version__); print(torch.cuda.get_device_name()); print('BF16:', torch.cuda.is_bf16_supported())"
```

## 3. 安装统一的 HEI LeRobot 环境

服务器、控制电脑和 Jetson 统一使用修复后的 HEI 项目。服务器同时安装
Pi0.5 与异步推理依赖：

```bash
cd /root/autodl-tmp
source /etc/network_turbo

mkdir -p /root/autodl-tmp/HGM
git clone --depth 1 \
  https://github.com/lipengdong/hei-rebot-lift.git \
  /root/autodl-tmp/HGM/hei-rebot-lift

cd /root/autodl-tmp/HGM/hei-rebot-lift/software/lerobot-hei-rebot-lift
conda activate lerobot5
pip install -e ".[pi,async]"
```

已有仓库时更新：

```bash
cd /root/autodl-tmp/HGM/hei-rebot-lift
git pull --ff-only

cd software/lerobot-hei-rebot-lift
pip install -e ".[pi,async]"
```

确认 Python 加载的是 HEI 项目，而不是旧的 `lerobot-official` 或 site-packages：

```bash
cd "$LEROBOT_DIR"

PYTHONPATH=src python - <<'PY'
import lerobot
from lerobot.datasets.depth_utils import MM_PER_METRE
from lerobot.policies.pi05 import PI05Policy

print("LeRobot source:", lerobot.__file__)
print("MM_PER_METRE:", MM_PER_METRE)
print("Pi0.5 import: OK")
PY
```

正确路径应位于：

```text
/root/autodl-tmp/HGM/hei-rebot-lift/software/lerobot-hei-rebot-lift/src/lerobot/
```

## 4. 检查数据集

当前数据集路径：

```text
/root/autodl-tmp/huggingface/lerobot/HGM/hei_rebot_lift_task1
```

检查元数据和统计文件：

```bash
ls "$DATASET_ROOT/meta/info.json"
ls "$DATASET_ROOT/meta/stats.json"
```

训练命令中同时保留逻辑 ID 和物理路径：

```bash
--dataset.repo_id=HGM/hei_rebot_lift_task1
--dataset.root="$DATASET_ROOT"
```

## 5. 下载基础模型

Pi0.5 的 tokenizer 来自受限模型 `google/paligemma-3b-pt-224`。先在
Hugging Face 网页接受该模型许可，再登录服务器：

```bash
hf auth login
hf auth whoami
```

下载 Pi0.5 权重：

```bash
unset HF_HUB_OFFLINE TRANSFORMERS_OFFLINE HF_DATASETS_OFFLINE
export HF_HOME=/root/autodl-tmp/huggingface
source /etc/network_turbo

hf download lerobot/pi05_base
```

当前使用的快照为：

```text
/root/autodl-tmp/huggingface/hub/models--lerobot--pi05_base/snapshots/22c30e5b34f9e7ab738b1b34fc2fc5ecfe2d28f0
```

Hugging Face 快照中的文件是指向 `blobs/` 的软链接。普通 `ls -lh`、
`du -sh` 和 `stat` 看到的可能只是软链接大小，检查真实权重必须跟随链接：

```bash
export PI05_PATH=/root/autodl-tmp/huggingface/hub/models--lerobot--pi05_base/snapshots/22c30e5b34f9e7ab738b1b34fc2fc5ecfe2d28f0

ls -lhL "$PI05_PATH/model.safetensors"
du -shL "$PI05_PATH"
find -L "$PI05_PATH" -type l -print
```

最后一条命令正常情况下没有输出。快照应包含：

```text
config.json
model.safetensors
policy_preprocessor.json
policy_postprocessor.json
```

## 6. 补全 PaliGemma Tokenizer

只需要 tokenizer 和配置，不需要再次下载完整 PaliGemma 权重。使用 Python
接口可以避免不同版本 `hf download --include` 的参数解析差异：

```bash
unset HF_HUB_OFFLINE TRANSFORMERS_OFFLINE HF_DATASETS_OFFLINE
source /etc/network_turbo

python -c "
from huggingface_hub import snapshot_download

path = snapshot_download(
    repo_id='google/paligemma-3b-pt-224',
    allow_patterns=['*.json', '*.model'],
)
print('Downloaded to:', path)
"
```

下载后进行严格的离线验证：

```bash
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1

python -c "
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained(
    'google/paligemma-3b-pt-224',
    local_files_only=True,
)
print('Tokenizer loaded:', type(tokenizer).__name__)
print('Vocabulary size:', len(tokenizer))
"
```

只有这个测试成功后再启动训练。

## 7. 十步冒烟测试

第一次先使用 `batch_size=1` 和 `steps=10`，验证数据、三路相机、18 维动作、
模型权重和 tokenizer 能完整通过一次反向传播。

```bash
cd "$LEROBOT_DIR"

PYTHONPATH=src lerobot-train \
  --dataset.repo_id=HGM/hei_rebot_lift_task1 \
  --dataset.root="$DATASET_ROOT" \
  --dataset.video_backend=pyav \
  --policy.type=pi05 \
  --policy.pretrained_path="$PI05_PATH" \
  --policy.normalization_mapping='{"ACTION":"MEAN_STD","STATE":"MEAN_STD","VISUAL":"IDENTITY"}' \
  --policy.n_action_steps=10 \
  --policy.empty_cameras=0 \
  --policy.freeze_vision_encoder=true \
  --policy.train_expert_only=true \
  --policy.gradient_checkpointing=true \
  --policy.dtype=bfloat16 \
  --policy.device=cuda \
  --policy.push_to_hub=false \
  --output_dir="$OUTPUT_ROOT/pi05_hei_smoke_test" \
  --job_name=pi05_hei_smoke_test \
  --batch_size=1 \
  --steps=10 \
  --save_freq=10 \
  --log_freq=1 \
  --num_workers=2 \
  --wandb.enable=false
```

成功日志应包含：

```text
Loaded state dict from model.safetensors
All keys loaded successfully!
Creating optimizer
step:1 ... loss:...
```

如果重复冒烟测试，请换一个新的 `output_dir` 和 `job_name`，避免已有目录冲突。

## 8. 48 GB 正式训练

48 GB 显存优先冻结 VLM，只训练动作专家和连接投影层：

```bash
cd "$LEROBOT_DIR"

PYTHONPATH=src lerobot-train \
  --dataset.repo_id=HGM/hei_rebot_lift_task1 \
  --dataset.root="$DATASET_ROOT" \
  --dataset.video_backend=pyav \
  --policy.type=pi05 \
  --policy.pretrained_path="$PI05_PATH" \
  --policy.normalization_mapping='{"ACTION":"MEAN_STD","STATE":"MEAN_STD","VISUAL":"IDENTITY"}' \
  --policy.n_action_steps=10 \
  --policy.empty_cameras=0 \
  --policy.freeze_vision_encoder=true \
  --policy.train_expert_only=true \
  --policy.gradient_checkpointing=true \
  --policy.dtype=bfloat16 \
  --policy.device=cuda \
  --policy.push_to_hub=false \
  --output_dir="$OUTPUT_ROOT/pi05_hei_rebot_lift_task1_expert" \
  --job_name=pi05_hei_rebot_lift_task1_expert \
  --batch_size=4 \
  --steps=10000 \
  --save_freq=2000 \
  --log_freq=50 \
  --num_workers=4 \
  --wandb.enable=false
```

另开终端观察：

```bash
watch -n 1 nvidia-smi
```

- 峰值显存低于约 40 GB：可以尝试 `batch_size=8`。
- 接近 48 GB：保持 `batch_size=4`。
- 出现 CUDA OOM：先降为 `batch_size=2`。
- 仍然 OOM：增加 `--policy.chunk_size=32`。

少量数据不建议直接训练 100000 步。当前建议每 2000 步保存一次，分别测试
2000、4000、6000、8000、10000 步的实际成功率，最后一个检查点不一定最好。

## 9. 输出位置

训练结果保存在：

```text
/root/autodl-tmp/outputs/pi05_hei_rebot_lift_task1_expert/
```

检查点位于：

```text
/root/autodl-tmp/outputs/pi05_hei_rebot_lift_task1_expert/checkpoints/
```

训练完成后应及时将检查点下载到本地或上传到自己的 Hugging Face 模型仓库；
AutoDL 实例释放后，不应假设系统盘内容仍然保留。

## 10. 检查训练结果

设置准备测试的检查点：

```bash
export CKPT=/root/autodl-tmp/outputs/pi05_hei_rebot_lift_task1_expert/checkpoints/010000/pretrained_model
```

检查必要文件：

```bash
ls -lh "$CKPT/config.json"
ls -lh "$CKPT/model.safetensors"
ls -lh "$CKPT/policy_preprocessor.json"
ls -lh "$CKPT/policy_postprocessor.json"
```

直接使用 `PI05Config` 检查配置，避免只导入 `PreTrainedConfig` 时策略注册表为空：

```bash
cd "$LEROBOT_DIR"

PYTHONPATH=src python - <<'PY'
import os
from lerobot.policies.pi05.configuration_pi05 import PI05Config

cfg = PI05Config.from_pretrained(os.environ["CKPT"])
print("type:", cfg.type)
print("chunk_size:", cfg.chunk_size)
print("n_action_steps:", cfg.n_action_steps)

print("\nInput features:")
for name, feature in cfg.input_features.items():
    print(f"  {name}: type={feature.type}, shape={feature.shape}")

print("\nOutput features:")
for name, feature in cfg.output_features.items():
    print(f"  {name}: type={feature.type}, shape={feature.shape}")
PY
```

应确认：

- `type` 是 `pi05`；
- `observation.state` 是18维；
- `action` 是18维；
- 图像键为 `observation.images.front`、`observation.images.left_wrist`、
  `observation.images.right_wrist`。

进一步验证模型权重可以完整加载：

```bash
PYTHONPATH=src python - <<'PY'
import os
from lerobot.policies.pi05.modeling_pi05 import PI05Policy

policy = PI05Policy.from_pretrained(os.environ["CKPT"])
policy.to("cuda").eval()
print("Policy loaded successfully")
print("Policy type:", policy.config.type)
print("Device:", next(policy.parameters()).device)
PY
```

如果出现 `Returning model without loading pretrained weights`，必须停止测试，
不能继续真机推理。

## 11. 修复旧检查点的 `optimizer_fused`

如果检查点由另一版 LeRobot 生成，服务器加载时可能报：

```text
The fields `optimizer_fused` are not valid for PI05Config
```

这表示检查点 `config.json` 含有当前 `PI05Config` 已删除的训练优化器字段。
`optimizer_fused` 不参与推理，可以在保留备份后删除；模型权重不会被修改：

```bash
python - <<'PY'
import json
import os
import shutil
from pathlib import Path

config_path = Path(os.environ["CKPT"]) / "config.json"
backup_path = config_path.with_name("config.json.before_runtime_fix")

shutil.copy2(config_path, backup_path)
config = json.loads(config_path.read_text(encoding="utf-8"))
removed = config.pop("optimizer_fused", "<字段原本不存在>")
config_path.write_text(
    json.dumps(config, ensure_ascii=False, indent=4) + "\n",
    encoding="utf-8",
)

print("配置文件:", config_path)
print("备份文件:", backup_path)
print("删除 optimizer_fused:", removed)
PY
```

修复后重新执行第10节的配置与权重加载测试。

## 12. AutoDL 异步真机推理

### 12.1 安全准备

第一次测试必须清空工作空间、准备好急停，并将底盘架空或关闭底盘电源。升降
应远离机械限位，先使用 `actions_per_chunk=5`。同一时间只能运行一个控制源，
启动策略前应停止 VR、键盘控制、record、replay 和其他 rollout。

任务文字应尽量使用采集数据中的原始描述。没有在数据中示范过的目标物、动作或
任务文字，不能仅依靠修改 prompt 获得可靠真机行为。

### 12.2 AutoDL 启动策略服务器

```bash
cd "$LEROBOT_DIR"
conda activate lerobot5

export CKPT=/root/autodl-tmp/outputs/pi05_hei_rebot_lift_task1_expert/checkpoints/010000/pretrained_model
export HF_HOME=/root/autodl-tmp/huggingface
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1

PYTHONPATH=src python -m lerobot.async_inference.policy_server \
  --host=127.0.0.1 \
  --port=8080 \
  --fps=30 \
  --inference_latency=0 \
  --obs_queue_timeout=2
```

正常日志应出现：

```text
PolicyServer started on 127.0.0.1:8080
```

只监听 `127.0.0.1`，不要把未加密的推理端口直接暴露到公网。

### 12.3 控制电脑建立 SSH 隧道

在控制电脑单独打开一个终端：

```bash
ssh -C -N \
  -L 18080:127.0.0.1:8080 \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=15 \
  -o ServerAliveCountMax=3 \
  -p 19546 \
  root@connect.westc.seetacloud.com
```

按提示输入 AutoDL SSH 密码。成功后终端会保持运行且通常没有输出；关闭终端或
按 `Ctrl+C` 会断开隧道。不要把密码写入命令、脚本、文档或 Git 仓库。

验证本地隧道：

```bash
nc -vz 127.0.0.1 18080
```

### 12.4 Jetson 启动机器人 Host

```bash
cd ~/hei-rebot-lift-main/software/lerobot-hei-rebot-lift

PYTHONPATH=src conda run --no-capture-output -n lerobot5 \
  hei-rebot-lift-host
```

等待升降回零以及机械臂、底盘和相机初始化完成。另开 Jetson 终端确认：

```bash
hostname -I
ss -lntp | grep -E ':(6555|6556)\b'
```

### 12.5 控制电脑启动异步客户端

控制电脑先安装相同版本的异步依赖：

```bash
cd ~/下载/hei-rebot-lift/software/lerobot-hei-rebot-lift
conda activate lerobot5
pip install -e ".[hei_rebot_lift,async]"
```

第一次安全测试：

```bash
PYTHONPATH=src python -m lerobot.async_inference.robot_client \
  --robot.type=hei_rebot_lift_client \
  --robot.remote_ip=192.168.31.203 \
  --robot.id=hei_rebot_lift \
  --robot.connect_timeout_s=20 \
  --server_address=127.0.0.1:18080 \
  --policy_type=pi05 \
  --pretrained_name_or_path=/root/autodl-tmp/outputs/pi05_hei_rebot_lift_task1_expert/checkpoints/010000/pretrained_model \
  --policy_device=cuda \
  --client_device=cpu \
  --actions_per_chunk=5 \
  --chunk_size_threshold=0.8 \
  --aggregate_fn_name=weighted_average \
  --fps=30 \
  --task="pick up the black dog and put it in the orange box"
```

`pretrained_name_or_path` 是控制电脑发送给 AutoDL 的路径，所以必须填写服务器
上的绝对路径。链路成功时，控制电脑应出现：

```text
Robot connected and ready
Sending policy instructions to policy server
```

服务器应出现：

```text
Client ... connected and ready
Loading model from: .../pretrained_model
Loaded state dict from model.safetensors
All keys loaded successfully!
```

确认动作方向、关节范围和急停均正常后，可以把 `actions_per_chunk` 提高到10。
只有动作队列持续耗尽时才考虑15或20；块越大，网络抖动容忍度越高，但旧动作
持续执行的时间也越长。

### 12.6 网络带宽说明

当前通用异步客户端传输未压缩的观测数组。三路 `640x480 RGB` 单帧合计约
2.64 MiB，30 Hz 理论原始图像流量约79 MiB/s，尚未包含序列化与协议开销。
公网带宽或延迟不足时，可能出现动作卡顿、观测积压或动作队列耗尽。

最终部署应优先使用 HEI 专用的 JPEG/缩放观测传输。临时降低 `fps` 可以用于
连通性测试，但会改变相对于30 Hz训练数据的动作执行节奏，不应直接作为最终方案。

## 13. 常见问题

### `No module named lerobot.datasets.depth_utils`

当前 HEI LeRobot 源码更新不完整，或者 Python 加载了错误目录。执行：

```bash
cd "$LEROBOT_DIR"
git pull --ff-only
pip install -e ".[pi,async]"
PYTHONPATH=src python -c "import lerobot; print(lerobot.__file__)"
PYTHONPATH=src python -c "from lerobot.datasets.depth_utils import MM_PER_METRE; print(MM_PER_METRE)"
```

不要通过安装另一个 `lerobot` 包掩盖问题，因为 `PYTHONPATH=src` 会优先加载
当前目录源码。

### `Available policy types: {}` 或 `Policy type 'pi05' is not registered`

单独检查配置时没有导入 Pi0.5 注册模块。使用第10节的 `PI05Config` 直接加载，
不要只导入 `PreTrainedConfig`。

### `optimizer_fused` 不是有效字段

训练检查点与当前运行源码存在配置版本差异。按第11节备份并清理检查点配置，
然后重新验证；该操作不会修改模型权重。

### 客户端提示等待 LeKiwi Host 超时

`HeiRebotLiftClient` 继承了 LeKiwi 网络客户端，因此错误文字仍可能显示
`LeKiwi Host`。它实际表示控制电脑没有从 Jetson 的 `6556` 端口收到 HEI
观测。检查：

```bash
ping -c 3 192.168.31.203
nc -vz -w 3 192.168.31.203 6555
nc -vz -w 3 192.168.31.203 6556
```

### `model.safetensors` 或 `policy_preprocessor.json` 不存在

`pi05_base` 快照下载不完整。退出离线模式后重新运行：

```bash
hf download lerobot/pi05_base
```

如果日志出现：

```text
Returning model without loading pretrained weights
```

必须停止训练。这表示模型正在使用随机权重。

### PaliGemma tokenizer 离线加载失败

缓存目录存在不代表内容完整。按本文第 6 节下载 `*.json` 和 `*.model`，并用
`local_files_only=True` 验证。

### TorchCodec 无法加载

如果日志随后显示：

```text
Falling back to 'pyav' as a default decoder
```

并且配置中的 `video_backend` 是 `pyav`，则不是致命错误，可以继续训练。

### 输出目录已经存在

为 `output_dir` 和 `job_name` 换一个新名称，或明确决定是否从已有检查点恢复。
不要在不清楚目录内容时直接覆盖训练结果。

### 训练过拟合

Pi0.5 的预训练知识不能替代机器人示范。夹爪、底盘旋转或升降动作如果在数据
中没有变化，模型无法学会对应行为。应增加示范数量、物体位置变化、视角变化
和任务文字变化，并通过真实机器人成功率选择检查点。
