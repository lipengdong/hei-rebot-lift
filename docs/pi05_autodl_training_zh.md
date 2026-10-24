# AutoDL RTX PRO 6000 训练 Pi0.5

本文记录如何在 AutoDL 的 RTX PRO 6000 服务器上，使用已经采集好的
HEI ReBot Lift 数据集微调 LeRobot Pi0.5。本文按 48 GB 显存配置编写，
训练采用“冻结 VLM、只训练动作专家和投影层”的方案。

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

## 2. 目录规划

AutoDL 系统盘空间有限，数据集、模型缓存和训练结果统一放到数据盘：

```text
/root/autodl-tmp/
├── huggingface/
│   ├── hub/                         # Hugging Face 模型缓存
│   └── lerobot/HGM/
│       └── hei_rebot_lift_task1/    # 本地数据集
├── lerobot-official/                # 官方 LeRobot 训练源码
└── outputs/                         # 训练结果
```

设置环境变量：

```bash
export HF_HOME=/root/autodl-tmp/huggingface
export HF_LEROBOT_HOME=/root/autodl-tmp/huggingface/lerobot
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
```

检查 GPU 和 BF16：

```bash
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
python -c "import torch; print(torch.__version__); print(torch.cuda.get_device_name()); print('BF16:', torch.cuda.is_bf16_supported())"
```

## 3. 安装训练环境

建议训练时使用完整的官方 LeRobot 源码。HEI 项目主要用于真机控制和数据
采集；如果它与上游同步时漏掉新文件，可能出现 `depth_utils` 等导入错误。

```bash
cd /root/autodl-tmp
source /etc/network_turbo

git clone --depth 1 \
  https://github.com/huggingface/lerobot.git \
  lerobot-official

cd lerobot-official
pip install -e ".[pi]"
```

验证：

```bash
python -c "from lerobot.datasets.depth_utils import MM_PER_METRE; print('LeRobot OK:', MM_PER_METRE)"
python -c "from lerobot.policies.pi05 import PI05Policy; print('Pi05 OK')"
```

## 4. 检查数据集

当前数据集路径：

```text
/root/autodl-tmp/huggingface/lerobot/HGM/hei_rebot_lift_task1
```

检查元数据和统计文件：

```bash
ls /root/autodl-tmp/huggingface/lerobot/HGM/hei_rebot_lift_task1/meta/info.json
ls /root/autodl-tmp/huggingface/lerobot/HGM/hei_rebot_lift_task1/meta/stats.json
```

训练命令中同时保留逻辑 ID 和物理路径：

```bash
--dataset.repo_id=HGM/hei_rebot_lift_task1
--dataset.root=/root/autodl-tmp/huggingface/lerobot/HGM/hei_rebot_lift_task1
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
cd /root/autodl-tmp/lerobot-official

PYTHONPATH=src lerobot-train \
  --dataset.repo_id=HGM/hei_rebot_lift_task1 \
  --dataset.root=/root/autodl-tmp/huggingface/lerobot/HGM/hei_rebot_lift_task1 \
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
  --output_dir=/root/autodl-tmp/outputs/pi05_hei_smoke_test \
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
cd /root/autodl-tmp/lerobot-official

PYTHONPATH=src lerobot-train \
  --dataset.repo_id=HGM/hei_rebot_lift_task1 \
  --dataset.root=/root/autodl-tmp/huggingface/lerobot/HGM/hei_rebot_lift_task1 \
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
  --output_dir=/root/autodl-tmp/outputs/pi05_hei_rebot_lift_task1_expert \
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

## 10. 常见问题

### `No module named lerobot.datasets.depth_utils`

本地 LeRobot 源码更新不完整。训练服务器使用完整的官方
`huggingface/lerobot` 仓库，不要仅通过安装 Python 包掩盖问题，因为
`PYTHONPATH=src` 会优先加载当前目录源码。

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
