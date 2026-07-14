# Stage 8C-3B — Static C8 / CA Binder Evidence

日期：2026-07-14
状态：**PASS / FROZEN**

## 1. 范围

本阶段仅修复并验证 GreenLion 静态表盘最终 Binder 层控制帧抓取，未实现静态上传、`build_static_c8()` 或 `build_static_ca()`，未修改 Uploader BLE 状态机。

已验证 Binder 层：

`android.bluetooth.IBluetoothGatt$Stub$Proxy.writeCharacteristic`

已验证 overload：

`(int, java.lang.String, int, int, int, [B)`

## 2. 冻结术语

| 术语 | 固定含义 |
|---|---|
| `input_image` | 原始 JPG/PNG |
| `static_container` | 351617 字节 BIN，也是全部 C9 DATA 原序拼接 |
| `region_stream` | 353146 字节 DATA+checksum 区域流 |
| `c9_frame_stream` | 362320 字节完整 C9 帧流 |

禁止再用 `source` 指代 `input_image`，避免与既有 351617 字节静态容器混淆。

## 3. 三层字节流关系

| 层 | 计算 | 大小 |
|---|---:|---:|
| `static_container` | `1528 × 230 + 177` | 351617 |
| `region_stream` | `1528 × 231 + 178` | 353146 |
| `c9_frame_stream` | `1528 × 237 + 184` | 362320 |

每个 C9 的 region 比 DATA 多 1 字节 checksum，因此：

`353146 - 351617 = 1529`

每个完整 C9 frame 比 region 多 6 字节头部，因此：

`353146 + 1529 × 6 = 362320`

## 4. 样例证据

| 项目 | 样例 A | 样例 B |
|---|---|---|
| `input_image` | 夜景游船及红色“达仁堂”招牌 | 白衬衫棕发少女、白色床铺背景 |
| `input_image` SHA-256 | `9FDBB04E9DD910296B44BECB98C25A0C988A4B1B98EC0DAE12A0E831BC747CB4` | `993BE3445975504C1BD2E587E38D5E22F421305161FEEBCCB8C1AE0BEA638ACD` |
| `static_container` SHA-256 | `44B4893ACF6244119DE655B32C1CE760048F3128A24489B49FF24F7BB60FA664` | `CBD34D9BE77B138481AB7AD590326CC7437EE55C45DBECB532A0DF1C4F8A2763` |
| `region_stream` SHA-256 | `19C1B72DA080C5F23D0978FF7C93DBD10F8E07D6EAAEFF4E3C4D08608E31BCF5` | `F55AEDE766E7B736535832A88EFEFFD407A1BB6A2735547AF0B42EEBC14BC267` |
| GreenLion 安装 | PASS | PASS |
| 手表显示 | PASS | PASS |

两组 Binder summary 均为：

- C8：1
- C9：1529
- CA：1
- sequence：`0..1528`
- missing：0
- duplicates：0
- malformed：0
- out-of-range：0
- observed handle histogram：`{"98":1531}`
- address policy：`redacted`

## 5. C8 冻结结论

NJ-LEJ-2.1.7、351617 字节 `static_container` 固定 profile 的两次真实 Binder 观测均为：

`BCC8020701815D0500F905E2`

观察到的数值关系：

- offset `5..8`：`81 5D 05 00`，按 LE32 为 `351617`，与两组 `static_container` 大小一致。
- offset `9..10`：`F9 05`，按 LE16 为 `1529`，与两组 C9 count 一致。
- offset `0..11` 在 A/B 间全部相同；差异 offset 为 `[]`。

该结论只能冻结为：

**C8 fixed-profile frame for NJ-LEJ-2.1.7 / 351617-byte static container**

两组样本的 `static_container_size` 和 C9 count 都没有变化，因此尚未证明 offset `5..8`、`9..10` 在大小或包数变化时如何同步变化。

## 6. CA 冻结结论

两次真实 Binder 观测均为：

`BCCA02010505`

- 长度：6
- offset `0..5` 全部相同
- 差异 offset：`[]`

该结论只能冻结为：

**CA observed fixed frame**

目前没有变化样本证明末尾 `05` 的语义或 CA 的通用生成边界。

## 7. 实现边界

- 通用 `build_static_c8()`：**暂不实现**。
- 通用 `build_static_ca()`：**暂不实现**。

原因不是 C8 完全未知，而是缺少 `static_container_size` 或 C9 count 变化的有效 Binder 对照样本；CA 也只有固定帧观测。

## 8. 抓取修复与安全

- 抓取顺序：先识别 `BC C8 / BC C9 / BC CA`，再记录 observed handle。
- handle、write type、地址和 Binder 整数均不作为前置过滤条件。
- 抓取 Hook 只读透传，不修改 byte[]，不调用 `setValue()`，不主动调用 `writeCharacteristic()`。
- 地址始终写为 `<redacted>`。
- raw JSONL、Frida 日志、payload、HCI 和 bugreport 均由 `.git/info/exclude` 排除。

脚本 SHA-256：

- 修复前：`966E921B49F4567CD9C8402057C7F040F0C58304B453B417DBC507C34CD0A624`
- A/B 实机证据版本：`EAEDDC7A5056B292581B40D4D8F10D14279B221BD339E0AD0CF1251F9C9927B4`
- 最终日志契约版本：`AB4BBBE4A617B01400A8CB90175D88314A3CC75E67553296331F96FFF15B0337`

实机证据完成后只规范了 `duplicates`、字符串脱敏计数和控制台摘要字段，未改变协议识别或 Binder 透传行为。

## 9. 离线结果

- `node --check`：PASS
- 样例 A 分析：PASS
- 样例 B 分析：PASS
- A/B 差异分析：PASS
- Editor 生产源码变化：0
- Uploader 生产源码变化：0
- 静态 Uploader 上传实现：0
- BLE 额外写入：0
- 自动上传：0
