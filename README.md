# STM32 AGV 节拍测量 PC 程序

用于接收 STM32 USB CDC 上报的 `START`、`END`、`EVENT` 消息，并按 MCU 单调递增时间戳计算 AGV 通过节拍。

## 环境

- Python 3.12
- `uv`
- Windows 或其他可用 Qt 的桌面系统

## 安装与运行

```bash
uv sync
uv run agv-timer
```

在 Windows 上也可以双击项目根目录的 `start_agv_timer.bat` 启动。脚本支持项目位于 WSL 的 `\\wsl$\...` 路径，会自动临时映射为盘符，并使用独立的 `.venv-windows` 环境。

程序使用固定串口参数 115200、8N1。启动后选择 STM32 对应的 COM 端口并点击“连接”。端口下拉框展开时会重新扫描可用端口。

## 测试

```bash
uv run pytest
```

协议详情见 [docs/communication-protocol.md](docs/communication-protocol.md)，产品需求见 [docs/PRD.md](docs/PRD.md)。
