# Ultra3 Uploader v0.3.0 协议实现计划

## 证据边界

本阶段只实现动态 `BCSDIAL` 的离线协议路径。依据为冻结基准中的 root 手机 Frida
直接 BLE 抓包；未知字段不推测。静态表盘、BLE 连接和真实上传不在 Stage 1–4 范围内。

## 已验证格式

- 输入：以 `BCSDIAL` 开头、以 `BCBC` 结尾的非空文件。
- C8：`BC C8 02 07 MODE SIZE_LE32 PACKET_COUNT_LE16 CHECKSUM`。
- 动态模式 `MODE=01`，`CHECKSUM=sum(MODE + SIZE_LE32 + PACKET_COUNT_LE16) & 0xFF`。
- C9：`BC C9 02 LEN SEQ_LE16 DATA CHECKSUM`，每块最多 230 字节。
- C9 checksum：`(seq_low + seq_high + sum(DATA)) & 0xFF`。
- 黄金样本：891180 字节、3875 包、末包 160 字节，C8 为
  `BCC80207012C990D00230F05`。

## 模块边界

1. `bcsdial.py` 负责文件边界校验和动态 payload。
2. `bc_frames.py` 只负责帧构造/解析，不访问文件或 BLE。
3. `capture_parser.py` 解析 `[U3BLE]` JSONL，并完成抓包与生成帧的比较。
4. `cli.py` 提供 `inspect`、`build`、`compare-capture` 三个离线命令。
5. `UploadPayload` 仅定义后续 transport 所需的最小接口；本阶段只有
   `BCSDIALPayload` 实现。

## 验收

- 单元测试覆盖 checksum、动态 C8、C9、文件边界和抓包异常。
- 黄金回归逐包比较 C8、3875 个完整 C9、序列、checksum 和重组 SHA-256。
- 测试不连接真实手表。

## unknown / 后续阶段

- C8 的 `PACKET_COUNT` 是 LE16，因此 65536 无法编码。本实现拒绝超过 65535 包；
  设备对边界值 65536 的行为保持 unknown。
- 断线续传、重传和最小安全包间隔保持 unknown。
- Stage 5 才实现 BLE transport；Stage 6 才实现真实上传状态机。

