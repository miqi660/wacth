# Ultra3 Watchface Editor Stage 7A-2A Reconstructor Report

## 1. 实现范围

本阶段新增纯离线 `reconstruct-c9`：读取 root/Frida 或文本抓包，提取 App→手表的目标
FF02 写入，定位独立 C8/C9 会话，严格按原始顺序校验并重组 BCSDIAL。没有扫描、连接、
上传、抓取新样本、修改 BIN、开发 GUI 或猜测时间位置/颜色字段。

## 2. 新增与修改文件

| 文件 | 职责 |
|---|---|
| `src/ultra3_editor/c9_protocol.py` | 与 uploader 黄金规则一致的只读 C8/C9/LEN/checksum 解析 |
| `src/ultra3_editor/capture_reader.py` | auto/frida/hex-lines/jsonl 抓包读取、FF02/FF03 分类与统计 |
| `src/ultra3_editor/reconstructor.py` | 多会话定位、选择、sequence/大小/头尾严格校验与原序重组 |
| `src/ultra3_editor/reconstruction_reports.py` | 独占 BIN、JSON、Markdown 输出 |
| `src/ultra3_editor/models.py` | 增加不可变 Capture、C8/C9、UploadSession、ReconstructionResult 模型 |
| `src/ultra3_editor/errors.py` | 增加抓包、帧、会话和重组明确异常 |
| `src/ultra3_editor/cli.py` | 增加 `reconstruct-c9` 命令及参数 |
| `README.md` | 增加离线重组命令和拒绝修复说明 |
| `tests/reconstruction_helpers.py` | 合成 C8/C9/抓包测试辅助 |
| `tests/test_capture_reader.py` | 输入格式、FF02/FF03/CA 和统计测试 |
| `tests/test_c9_protocol.py` | C8/C9 字段、LEN、DATA 和 checksum 测试 |
| `tests/test_reconstructor.py` | 严格失败、多会话隔离和黄金抓包回归 |
| `tests/test_reconstruct_cli.py` | 输出保护、失败零 BIN、只读输入和零 BLE 测试 |
| `artifacts/stage7a2a_golden_reconstructed.bin` | 从历史黄金抓包原序重组的 BCSDIAL |
| `artifacts/stage7a2a_golden_reconstruction.json` | 黄金重组机器可读结果 |
| `artifacts/stage7a2a_golden_reconstruction.md` | 黄金重组明细报告 |
| `samples/stage7a2_diy_root_capture/` | 未采集的 A0_repeat_1/2 目录和 null 元数据模板 |

未修改 uploader 源码、上传状态机、Frozen 文件、黄金抓包或黄金 BIN。

## 3. 输入格式支持

- `--format auto`：逐行识别 Frida、JSONL、纯 HEX 和带 TX/write/FF02 标记的文本。
- `--format frida`：识别 `[U3BLE] {JSON}`，实际黄金格式。
- `--format hex-lines`：每行一个连续或常见分隔符分隔的完整 HEX payload。
- `--format jsonl`：支持 `frame_hex`、`hex`、`payload`、`tx`、`write` 字段。

FF03/RX/notify 不计为 FF02 写入；其他 characteristic 计为非目标记录；无法识别行保留统计，
不会从说明文字伪造 payload。

## 4. C8/C9 校验规则

C8 必须是 12 字节 `BC C8 02 07 MODE SIZE_LE32 COUNT_LE16 CHECKSUM`。checksum 使用：

```text
(MODE + sum(SIZE_LE32) + sum(COUNT_LE16)) & 0xFF
```

C9 必须满足 `BC C9 02 LEN SEQ_LE16 DATA CHECKSUM`、`LEN == frame_length - 5`、DATA
长度 `1..230`，checksum 使用：

```text
(seq_lo + seq_hi + sum(DATA)) & 0xFF
```

重组前还必须满足：packet count 与声明大小计算一致；sequence 原始顺序严格为
`0..count-1`；无缺失、重复或乱序；非最后包 DATA 为 230；最后包长度精确匹配；C9 数量、
拼接大小、BCSDIAL 头和 BCBC 尾全部正确。工具不排序、不去重、不补零、不跳过坏包。

## 5. 会话选择规则

- 结构上以 `BC C8 02` 开始新会话。
- 收齐 C8 声明数量、遇到 CA apply、新 C8 或文件结束时结束当前会话。
- 会话各自保存 C9，禁止跨 C8 混合。
- 唯一完整会话自动选择。
- 多个完整会话且无 `--session-index` 时拒绝并列出候选。
- `--session-index` 只分析指定会话；指定会话失败时不输出 BIN。
- 没有 C8 或无法唯一选择时返回非零。

## 6. 测试结果

```text
Editor:   84 passed
Uploader: 126 passed
```

原有 Stage 7A-1 的 42 项测试未修改且全部保留；新增 42 项纯离线测试，覆盖附件要求的
36 类输入、协议、失败、会话、输出和零 BLE 场景。

## 7. 黄金抓包重组结果

输入：`capture_light_v2.log`

```text
Status: COMPLETE
Detected format: frida
Session count/index: 1 / 0
C8: BCC80207012C990D00230F05
Declared/actual size: 891180 / 891180
Declared/actual packet count: 3875 / 3875
Sequence: 0..3874
Checksum: 3875/3875
Missing sequences: []
Duplicate sequences: []
Out of order: false
BCSDIAL header: true
BCBC footer: true
Reconstructed SHA-256: 7B25A833D431ED29622EDF4C102F4B555F1E251D1CEC842D848E8E7DCE2C015D
```

解析统计：

```text
Total lines: 3926
Recognized records: 3916
FF02 writes: 3877
FF03 notifications: 39
Unrecognized lines: 10
Non-target frames: 0
C8/C9/CA apply: 1/3875/1
```

重组 BIN 与既有黄金 BIN 逐字节一致。

## 8. 输入与 Frozen 哈希复核

```text
capture_light_v2.log
CD85A7AADDCC6BD85E108335DA0E0D63AF9FF24A88C5478F6E0BEA7E9CD6AE7F

黄金 BCSDIAL / 本次重组 BIN
7B25A833D431ED29622EDF4C102F4B555F1E251D1CEC842D848E8E7DCE2C015D

Ultra3_v0.2.4_Frozen_Baseline_2026-07-11.zip
3581B0FA3D8E0B4BB952848CC45492B157DFFF4B125D57C93611FC89BF711231
```

输入抓包哈希在运行前后保持一致，Frozen changes = 0。

## 9. BLE 与编辑安全统计

```text
Bleak 初始化: 0
scan: 0
connect: 0
FF02 writes: 0
```

Editor 没有导入 Bleak，也没有 scan/connect/write 实现。未实现 patch、save、set-action、
set-color、set-position、组件编辑、自动修复或 GUI。

## 10. A0 重复样本计划

已创建：

- `samples/stage7a2_diy_root_capture/A0_repeat_1/metadata.json`
- `samples/stage7a2_diy_root_capture/A0_repeat_2/metadata.json`

两份模板对尚未采集的背景 SHA、时间位置、颜色和 root 抓取状态使用 `null`。本阶段没有
创建或伪造 capture、BIN、截图、背景图、重组报告或 SHA256SUMS。

后续 Stage 7A-2B 必须经单独授权，使用同一背景、裁剪、位置、颜色、App、root 手机、
Ultra3 和 `NJ-LEJ-2.1.7` 固件分别采集一次完整上传。两份都严格重组后才能做 repeat diff；
若存在差异，先排查时间戳、批次、随机 ID、缓存和图片编码，不得直接宣称为位置或颜色字段。

状态：A0_repeat_1/A0_repeat_2 **NOT CAPTURED**。未进入 Stage 7A-2B。
