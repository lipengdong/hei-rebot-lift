# Jetson 系统图标红叉排障记录

[English](jetson_system_icons.md) | [中文](jetson_system_icons_zh.md) | [文档导航](README_zh.md)

适用环境：Jetson、Ubuntu 22.04、ARM64、GNOME 桌面。记录日期：2026-09-18。
本文处理 Wi-Fi、文件管理器返回按钮等系统图标缺失，不是相机画面、照片损坏或机器人控制故障。
这些是故障发生后的维护步骤，不是每次部署都要执行的安装命令。

## 1. 这次发生了什么

安装环境后，桌面右上角 Wi-Fi 和文件管理器按钮等图标变成红叉。

| 观察 | 能说明什么 |
| --- | --- |
| 当前图标主题是 `Yaru` | 主题名称看起来正常，但不能证明主题文件和解码组件完好 |
| 根分区占用 93%，仍有约 17 GB 可用 | 检查时没有占满；不能排除之前安装时发生过空间或其他资源问题 |
| `.bashrc` 全局加入另一个用户目录下的 Anaconda `lib` 路径 | 有动态库冲突风险，但单独移除它后未看到恢复，不能判定它是本次根因 |
| 清除相关环境变量后，SVG 图标测试仍提示无法识别格式 | 系统 SVG 解码链路存在异常，不只是当前终端环境问题 |
| 重装系统包时提示 `dpkg was interrupted` | 已确认包管理器存在未完成的配置操作 |
| 按恢复包管理器的流程处理后，用户确认图标恢复 | 此流程有效，但没有完整执行日志，不能认定某一条命令是唯一修复点 |

**最有证据支持的解释：此前系统包安装/配置中断，系统处于未完成配置状态；
SVG 加载器或其缓存可能因此没有正确安装、加载或注册，导致系统图标显示失败。**
具体是哪一次安装被中断、哪个包或触发器出了问题，现有日志不足以确定。
中断可能来自关机、终端关闭、手动取消或安装脚本失败，不能断定是项目中的
Conda/pip 安装命令直接破坏了系统。

系统图标加载大致经过：图标主题文件 → SVG 解码插件 → GdkPixbuf 加载器缓存 → 桌面程序。
任意一环异常都可能出现缺失图标。`gdk-pixbuf-query-loaders --update-cache`
用于重新注册加载器，不是修复图片内容。参见 [Ubuntu 工具说明](https://manpages.ubuntu.com/manpages/jammy/man1/gdk-pixbuf-query-loaders.1.html)。

## 2. 下次出现后的处理顺序

### 2.1 先停止机器人并检查状态

安全停止 host、遥操作、回放和调试程序，支撑可能失能下落的部件，再维护系统。
保存工作，保证供电稳定。确认没有另一项 apt/dpkg 或软件更新任务仍在运行；
若只是锁被占用，等待已有任务结束，不要删除锁文件或强杀包管理器。

以下只读命令可在任意目录执行：

```bash
df -h / /home
df -i / /home
sudo dpkg --audit
gsettings get org.gnome.desktop.interface icon-theme
printenv | grep -E 'LD_LIBRARY_PATH|LD_PRELOAD|GDK_PIXBUF|GTK_PATH|GTK_DATA_PREFIX'
grep -nE 'LD_LIBRARY_PATH|LD_PRELOAD|GDK_PIXBUF|GTK_PATH|GTK_DATA_PREFIX|anaconda|conda|source ' ~/.bashrc ~/.profile /etc/environment
```

`printenv` 的筛选没有输出，表示未发现这些变量，不一定是错误。
`gsettings` 建议在 Jetson 本机桌面终端执行。磁盘或 inode 耗尽时先释放已确认
可以清理的数据空间；不要删除 `/usr/lib`、dpkg 数据库或 JetPack 文件。

### 2.2 先恢复被中断的包配置

只有发现未完成配置或出现以下报错时，先做这一项：

```text
E: dpkg was interrupted, you must manually run 'sudo dpkg --configure -a' to correct the problem.
```

```bash
sudo dpkg --configure -a
```

该命令完成所有待配置包及相关触发器，不只配置图标包，可能需要一段时间。
正常运行期间不要关机或按 `Ctrl+C`。若失败，保留完整报错，先定位失败的包，
不要反复强制执行或卸载 NVIDIA 包。参见 [dpkg 手册](https://manpages.ubuntu.com/manpages/jammy/man1/dpkg.1.html)。

仅在提示依赖损坏时，先模拟查看修复计划：

```bash
sudo apt-get -s --fix-broken install
```

确认没有危险删除后，再执行：

```bash
sudo apt-get --fix-broken install
sudo dpkg --configure -a
```

**若计划删除 NVIDIA、JetPack、CUDA、ROS 或大量桌面包，停止并排查软件源和依赖。
模拟操作不改系统；实际操作不要加自动确认 `-y`。**
参见 [APT 修复与模拟选项](https://manpages.ubuntu.com/manpages/jammy/man8/apt-get.8.html)。

### 2.3 如果 SVG 图标仍有问题，重装解码组件

```bash
sudo apt update
sudo apt install --reinstall libgdk-pixbuf-2.0-0 librsvg2-2 librsvg2-common
```

检查 apt 操作列表，避免误删平台组件。不需要升级整个系统或重装 CUDA。
如果这一步已经恢复图标，也要检查包管理器状态，不能仅凭画面正常判断安装完整。

### 2.4 重建系统加载器缓存

下面是 Ubuntu 22.04 ARM64 的系统路径，不是 Conda 环境路径：

```bash
sudo env -u LD_LIBRARY_PATH -u LD_PRELOAD \
  -u GDK_PIXBUF_MODULE_FILE -u GDK_PIXBUF_MODULEDIR \
  /usr/lib/aarch64-linux-gnu/gdk-pixbuf-2.0/gdk-pixbuf-query-loaders --update-cache
```

正常通常没有输出。若报缺少依赖、`undefined symbol` 或工具不存在，先保留报错，
不要改用 Conda 内的同名工具，也不要从其他系统复制 `.so` 文件覆盖。

### 2.5 验证 SVG 解码，再重新登录

```bash
env -u LD_LIBRARY_PATH -u LD_PRELOAD \
  -u GDK_PIXBUF_MODULE_FILE -u GDK_PIXBUF_MODULEDIR \
  /usr/bin/gdk-pixbuf-thumbnailer \
  /usr/share/icons/Adwaita/scalable/actions/go-previous-symbolic.svg \
  /tmp/jetson-icon-test-clean.png

file /tmp/jetson-icon-test-clean.png
sudo dpkg --audit
sudo apt-get check
```

预期：SVG 测试不再警告，输出文件显示 `PNG image data`，`dpkg --audit` 没有
待处理异常，`apt-get check` 成功退出。测试图标路径不存在时不能据此判定
解码失败，需要换成系统中实际存在的 SVG 图标。

最后保存工作并**注销桌面、重新登录**，让 Wi-Fi 图标和文件管理器重新加载。
只在终端中 `unset` 或执行 `source ~/.bashrc`，不会更新已经运行的桌面进程。
若 dpkg/apt 表明需要重启，再安排重启；不要在配置操作未结束时重启。

## 3. 如果仍不恢复

直接检查 SVG 插件是否存在及能否加载：

```bash
ls -l /usr/lib/aarch64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders/libpixbufloader-svg.so
env -u LD_LIBRARY_PATH -u LD_PRELOAD \
  -u GDK_PIXBUF_MODULE_FILE -u GDK_PIXBUF_MODULEDIR \
  /usr/lib/aarch64-linux-gnu/gdk-pixbuf-2.0/gdk-pixbuf-query-loaders \
  /usr/lib/aarch64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders/libpixbufloader-svg.so
```

| 结果 | 下一步 |
| --- | --- |
| 插件不存在 | 检查 `librsvg2-common` 是否安装成功 |
| `not found` / `undefined symbol` / 加载失败 | 排查依赖版本、`/usr/local/lib` 或全局库路径；不要直接删系统库 |
| 插件正常，但 SVG 缩略图仍失败 | 检查缓存中的 SVG 注册项、实际图标文件及报错 |
| SVG 测试正常，但桌面仍红叉 | 确认已重新登录，检查实际使用的图标主题及桌面日志 |

仅在确认 Yaru/Adwaita 主题文件缺失时，重装主题：

```bash
sudo apt install --reinstall adwaita-icon-theme yaru-theme-icon
```

保存排障记录时附上完整终端输出，必要时查看 `/var/log/apt/history.log`、
`/var/log/apt/term.log` 和 `/var/log/dpkg.log`，确定中断的包与时间。
`Nautilus-Share-Message` 提到找不到 `net` 是共享功能提示，不等于图标解码失败，
不用为修图标专门安装 Samba。系统图标故障也不应通过删除照片缩略图缓存解决。

## 4. 避免再次发生

- 在独立 Conda 环境安装项目依赖，不使用 `sudo pip install` 修改系统 Python。
- 不将 Conda 的 `lib` 路径全局加入 `.bashrc`、`.profile` 或 `/etc/environment`；本次曾存在另一个用户目录的 Anaconda 路径，应删除这种遗留注入。
- 修改启动文件前备份；只删除已确认有问题的库路径项，保留正常 Conda 初始化块、必要的 ROS/CUDA 路径。不要全局清空 Jetson 库路径。
- 特定程序需要调整动态库环境时，只对该进程设置，不把 GDK/GTK 或 Conda 库变量导入整个桌面会话。[Conda 官方建议](https://docs.conda.io/projects/conda-build/en/stable/resources/use-shared-libraries.html)。
- apt/dpkg 安装时保持供电、网络和终端稳定；SSH 部署可使用 `tmux`，断线后重新连接查看任务，不要重复启动安装。
- 安装前检查空间和 inode；本次磁盘已使用 93%，应提前规划数据集、模型与缓存的存储空间。
- 不盲目执行 `apt autoremove`、强制降级、跨 Ubuntu 版本混用软件源或覆盖 `/usr/lib`；JetPack/NVIDIA 软件源应与设备系统匹配。

本记录没有远程执行 Jetson 系统修复命令；恢复结果来自用户实机反馈。
