# Claude Traffic Light 🚦

Claude Code 运行状态桌面红绿灯，实时显示 Claude CLI 的工作状态。

## 状态说明

| 灯色 | 状态 | 含义 |
|------|------|------|
| 🟢 绿灯 | 运行中 | Claude 在干活，你看着就行 |
| 🔴 红灯 | 等待中 | 需要你输入/确认 |
| 🟡 黄灯 | 就绪 | 任务完成，等你下一步指令 |

## 功能

- 桌面悬浮窗，红绿灯样式
- 可调节大小
- 可设置是否置顶
- 可最小化到托盘
- 实时检测 Claude CLI 状态

## 安装

```bash
pip install -r requirements.txt
python main.py
```

## 打包

```bash
pyinstaller --onefile --windowed main.py
```

## 技术栈

- Python 3.11+
- PyQt5（桌面 UI）
- psutil（进程监控）

## License

MIT
