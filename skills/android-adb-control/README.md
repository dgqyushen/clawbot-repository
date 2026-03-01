# android-adb-control

用于通过无线 ADB 从 OpenClaw 容器控制 Android 设备（默认目标：`host.docker.internal:5555`）。

## 用途

- 连接并验证设备在线状态
- 截图、执行 shell 命令、抓日志
- 安装 APK 与基础自动化调试

## 目录结构

- `SKILL.md`：技能定义与操作流程
- `references/device-profile.md`：本地设备端点与常用命令

## 快速使用

```bash
adb start-server
adb connect host.docker.internal:5555
adb devices -l
```
