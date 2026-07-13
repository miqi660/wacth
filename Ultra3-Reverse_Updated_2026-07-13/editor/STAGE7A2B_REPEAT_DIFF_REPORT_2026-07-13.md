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
| Before | `C:\Users\Administrator\Desktop\wacth\Ultra3-Reverse_Updated_2026-07-13\editor\samples\stage7a2_diy_root_capture\A0_repeat_1\reconstructed.bin` | 351617 | `9305529D6C644C757F6B193671B84153F0ADEBE385E7B3B30552E9BC23513635` | False | False |
| After | `C:\Users\Administrator\Desktop\wacth\Ultra3-Reverse_Updated_2026-07-13\editor\samples\stage7a2_diy_root_capture\A0_repeat_2\reconstructed.bin` | 351617 | `9305529D6C644C757F6B193671B84153F0ADEBE385E7B3B30552E9BC23513635` | False | False |

## 差分摘要

- Same size: `True`
- Changed bytes: `0`
- Unchanged bytes: `351617`
- Range count: `0`
- First difference: `none`
- Last difference: `none`
- Changed percentage: `0.000000000000%`
- Known patch verified: `False`

## 差异连续区间

无差异。
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
