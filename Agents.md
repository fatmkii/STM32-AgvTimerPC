# 项目背景
用途：
检测 AGV 经过光电开关的事件，并通过 USB CDC 发送给 PC。
用于统计AGV的通过节拍间隔
基本架构是  欧姆龙E3Z-R61光电开关 —— STM32 —— 电脑
这个项目文件夹是其中PC程序部分

AGV：
12 ~ 16台固定顺序循环。
台数不固定，STM32和PC端程序也无法识别，故由人工自行记录和处理。

节拍：
约 60~110 秒。

单台 AGV 遮挡：
约 4 秒。

USB：
通过 USB CDC 向 PC 上报事件。
recording ON 时发送 `START,<timestamp>\r\n`，recording OFF 时发送
`END,<timestamp>\r\n`；光电事件发送 `EVENT,<timestamp>\r\n`。
固件使用 64 条 RAM 队列缓存待发消息，队列满时覆盖最早消息；
发送状态不确定的事件会重发，PC 必须按 timestamp 去重。
PC 根据 MCU timestamp 计算相邻 AGV 节拍。

AGV编号：
MCU 不需要识别具体 AGV。

# 通信协议
详情见`docs/communication-protocol.md`

# 开发环境
使用uv作为python包和虚拟环境管理器。
