# Ultra3 Stage 7A-1 BCSDIAL Diff Report

## 实现范围

仅实现离线 BCSDIAL 检查、逐字节差分和已知补丁验证；不修改 BIN，不调用 BLE，不实现编辑功能。

## 新增文件

- `pyproject.toml`、`README.md`
- `src/ultra3_editor/`：CLI、数据模型、只读解析、检查、差分、范围合并、HEX、报告和黄金补丁验证
- `tests/`：42 项纯离线单元与黄金样本回归测试
- `artifacts/stage7a1_known_patch_diff.json`：完整机器可读差分

## 离线测试

`42 passed in 1.02s`。测试未导入 Bleak，未扫描、连接或产生 BLE 写入。

## 文件信息

| Role | Path | Size | SHA-256 | Header | Footer |
|---|---|---:|---|---|---|
| Before | `C:\Users\Administrator\Desktop\Ultra3-Reverse_Updated_2026-07-13\dynamic_watchface\baseline\2026-07-13_bcsdial_ff02_upload_success\evidence\samples\168844266159401_original.bin` | 891180 | `C16BAAD36C20FA3473753B12907DF155510C95C4187FE9369C11AF4EFF6F3F8C` | True | True |
| After | `C:\Users\Administrator\Desktop\Ultra3-Reverse_Updated_2026-07-13\dynamic_watchface\baseline\2026-07-13_bcsdial_ff02_upload_success\evidence\samples\168844266159401_jump13_to_4_reconstructed_from_ble.bin` | 891180 | `7B25A833D431ED29622EDF4C102F4B555F1E251D1CEC842D848E8E7DCE2C015D` | True | True |

## 差分摘要

- Same size: `True`
- Changed bytes: `1`
- Unchanged bytes: `891179`
- Range count: `1`
- First difference: `0x0000016F`
- Last difference: `0x0000016F`
- Changed percentage: `0.000112210777%`
- Known patch verified: `True`

## 差异连续区间

### Range 1: 0x0000016F..0x0000016F

- Length: `1`
- Before HEX: `0D`
- After HEX: `04`
- Context: `0x0000014F..0x0000018F`

Before context:

```text
0000014F  00 01 02 AE 00 EF 00 24 00 00 00 00 00 09 0A 00  |.......$........|
0000015F  00 0A FF 00 00 00 00 87 00 5C 00 00 00 00 01 00  |.........\......|
0000016F  0D 0A FF C6 00 00 00 79 00 66 00 00 00 00 01 00  |.......y.f......|
0000017F  03 0A FF 00 00 12 01 88 00 6D 00 00 00 00 01 00  |.........m......|
0000018F  04                                               |.|
```

After context:

```text
0000014F  00 01 02 AE 00 EF 00 24 00 00 00 00 00 09 0A 00  |.......$........|
0000015F  00 0A FF 00 00 00 00 87 00 5C 00 00 00 00 01 00  |.........\......|
0000016F  04 0A FF C6 00 00 00 79 00 66 00 00 00 00 01 00  |.......y.f......|
0000017F  03 0A FF 00 00 12 01 88 00 6D 00 00 00 00 01 00  |.........m......|
0000018F  04                                               |.|
```

## 已确认含义与边界

真实黄金样本已确认 `0x0000016F` 在本样本中由 `0x0D`（电话跳转）变为 `0x04`（心率跳转）。

- 当前只确认该字段在该样本中的功能。
- 尚未确认组件记录起始位置。
- 尚未确认字段宽度。
- 尚未确认完整 action 枚举。
- 尚未确认该偏移是否对所有 BCSDIAL 固定。

## 安全结果

- Frozen changes = 0。
- 真实 BLE 使用次数 = 0。
- 未实现 patch/write/save/set-action/set-color/set-position 或组件编辑。

## Stage 7A-2 样本矩阵（仅计划）

| ID | 单一变量 | 目标值 |
|---|---|---|
| A0 | 基准表盘 | 基准 |
| A1 | 时间位置 | 上 |
| A2 | 时间位置 | 下 |
| A3 | 时间颜色 | 纯红 |
| A4 | 时间颜色 | 纯绿 |
| A5 | 时间颜色 | 纯蓝 |
| A6 | 点击跳转 | 电话 |
| A7 | 点击跳转 | 心率 |

采样原则：每次只改变一个变量；背景图片保持一致；位置样本颜色相同；颜色样本位置相同；保存带变量和值的文件名、截图、BIN、SHA-256、官方 App 设置及 root 手机抓取证据。真实样本不足前，不宣称已定位时间位置或颜色字段。
