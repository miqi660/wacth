# Stage 7B-1 GreenLion Static DIY 时间位置公共编辑核心报告

## 1. 结论

Stage 7B-1 已完成。公共 `set_time_position()` API 与 `set-time-position` CLI 只编辑完成 C9
重组后的 351617 字节 GreenLion Static DIY BIN，并且只允许 offset `0x00000000` 的
`00 = top`、`01 = bottom` 映射。双向黄金输出均与官方样本逐字节完全相同。

本阶段未修改或接入 GUI，未实现 Builder，未调用 Uploader、BLE、adb 或 Frida，未执行上传。

## 2. Git 与扁平化审计

开始前执行了远程同步与本地审计：

| 项目 | 结果 |
|---|---|
| 分支 | `main` |
| HEAD | `838697f22ab9726fe411c95ccfd1e08d055d9c00` |
| origin/main | `838697f22ab9726fe411c95ccfd1e08d055d9c00` |
| 最新提交 | `838697f chore(repo): flatten project layout` |
| 工作区 | 修改前干净 |
| 远程 | `https://github.com/miqi660/wacth.git` |
| 根目录 | `.gitignore`、`README.md`、`archives`、`editor`、`uploader` |
| 旧包装目录 | 不存在 |

所有开发、测试和产物均使用扁平化后的 `C:\Users\Administrator\Desktop\wacth\editor`。
历史报告、抓包和 metadata 中的旧路径没有批量修改。

## 3. 修改前能力与测试基线

| 检查 | 修改前结果 |
|---|---|
| Editor 测试 | `134 passed`，约 `2.290s` |
| Uploader 测试 | `126 passed`，约 `2.054s` |
| `TimePosition` | 已存在，`TOP/BOTTOM` |
| `inspect_static_diy()` | 已存在，严格验证大小、首字节、位置和 SHA-256 |
| `set_time_position()` | 不存在 |
| `set-time-position` CLI | 不存在 |
| GUI | `READ ONLY` |
| Builder 公共接口 | `NOT AVAILABLE` |
| Uploader 未预期变化 | `0` |

## 4. 新增与修改文件

| 文件 | 职责 |
|---|---|
| `src/ultra3_editor/time_position.py` | 公共编辑 API、不可变结果模型、单字节差分、事务写入、写后复验、JSON/Markdown |
| `src/ultra3_editor/errors.py` | 增加编辑、no-op、同路径、输出冲突、复验及意外差分明确异常 |
| `src/ultra3_editor/cli.py` | 增加严格的 `set-time-position` 命令和验收输出 |
| `src/ultra3_editor/__init__.py` | 导出 `TimePosition`、`TimePositionEditResult`、`set_time_position` |
| `tests/test_time_position_editor.py` | 核心、黄金、失败回滚、格式门、报告和隔离测试 |
| `tests/test_time_position_cli.py` | top/bottom、非法参数、no-op、冲突及退出码测试 |
| `README.md` | 记录公共 API/CLI、安全边界与 GUI 仍未接入 |
| `artifacts/stage7b1_time_position/` | 双向黄金 BIN 及对应 JSON/Markdown 编辑记录 |
| `STAGE7B1_TIME_POSITION_EDITOR_REPORT_2026-07-13.md` | 本报告 |

`static_diy.py`、GUI、Uploader、黄金输入、原始抓包和 Frozen ZIP 均未修改。

## 5. 公共 API 与严格 CLI

公共入口：

```python
set_time_position(
    input_path,
    output_path,
    position: TimePosition,
    json_path=None,
    report_path=None,
) -> TimePositionEditResult
```

API 使用 `TimePosition.TOP` 或 `TimePosition.BOTTOM`。CLI 的 argparse `choices` 只接受精确
小写 `top`、`bottom`；`TOP`、`Bottom`、`0`、`1` 和中文别名均以非零状态退出。

```powershell
python -m ultra3_editor set-time-position `
  --input "<input.bin>" `
  --position bottom `
  --output "<output.bin>" `
  --json "<edit.json>" `
  --report "<edit.md>"
```

## 6. 现有检查器复用与格式门

编辑入口在写入前后均调用现有 `inspect_static_diy()`，没有复制第二套大小验证、首字节解析、
位置映射或文件 SHA 逻辑。当前格式门严格限定为：

- Container：`greenlion-static`；
- Firmware 证据范围：`NJ-LEJ-2.1.7`；
- 输入：完成 C9 重组后的 BIN；
- 大小：严格 `351617` 字节；
- offset 0：只能为 `00` 或 `01`；
- 不适用于 C9 帧流、BCSDIAL、预设表盘及未知固件/格式。

黄金 SHA 只用于结果匹配，不是输入白名单；自动化测试确认普通合法非黄金 BIN 可双向编辑。

## 7. 字段证据链与唯一编辑规则

Stage 7A-2C 的真实单变量证据为：

| 字段 | Top | Bottom |
|---|---:|---:|
| offset | `0x00000000` | `0x00000000` |
| width | 1 byte | 1 byte |
| value | `00` | `01` |

内存差分与写后差分均要求：

- 输入和输出大小均为 `351617`；
- changed bytes = `1`；
- changed offsets = `[0]`；
- unchanged bytes = `351616`；
- offset `1..EOF` 逐字节一致。

任何偏离都会抛出 `UnexpectedChangedBytesError`，且不会留下交付物。

## 8. no-op、路径和事务安全

`00 + top` 与 `01 + bottom` 由 `NoChangeRequestedError` 拒绝，CLI 返回非零，不创建 BIN、
JSON 或 Markdown。输入与任一输出目标同路径由 `InputOutputSamePathError` 拒绝；三个输出目标
之间也不能重复。

所有输出路径在创建前统一检查。已有 BIN、JSON 或 Markdown 由 `EditOutputExistsError` 拒绝，
不提供 `--force`。父目录沿用项目策略按需创建，文件使用 `xb`/`x` 独占模式。

事务顺序为：

1. 现有检查器验证输入并记录 SHA-256；
2. 只读加载输入，在内存仅改 offset 0；
3. 严格验证单字节差分并计算输出 SHA-256；
4. 独占创建 BIN；
5. 回读 BIN，再次调用现有检查器并复核大小、位置、SHA 和完整差分；
6. 再次检查输入 SHA 未变化；
7. 独占写入 JSON、Markdown；
8. 任一步失败时，逆序删除且只删除本次调用创建的文件。

失败注入测试覆盖输出复验失败和 Markdown 写入失败，两者均确认没有半完成 BIN/JSON/Markdown。

## 9. 结构化结果和报告

`TimePositionEditResult` 记录状态、功能、容器、适用范围、输入前后 SHA、检测/请求/输出位置、
输出大小与 SHA、字段 offset/宽度/before/after、完整差分统计、写后复验、黄金匹配、外部调用
统计和错误列表。JSON 额外明确记录：

```json
{
  "external_usage": {
    "ble": 0,
    "adb": 0,
    "frida": 0,
    "uploader": 0
  }
}
```

Markdown 明确声明只改 offset 0、输入保持只读、未执行上传、未接入 GUI、未实现/调用 Builder、
未实现其他组件。

## 10. 双向黄金验证

产物目录：`editor/artifacts/stage7b1_time_position/`

| 方向 | 输出 | 大小 | SHA-256 | 官方样本逐字节相等 |
|---|---|---:|---|---|
| Top → Bottom | `top_to_bottom.bin` | 351617 | `3B8302F6746AB2B78FA48599328DB7907788FA322D18ADF297280C8A5D3370C0` | `true` |
| Bottom → Top | `bottom_to_top.bin` | 351617 | `9305529D6C644C757F6B193671B84153F0ADEBE385E7B3B30552E9BC23513635` | `true` |

两个方向均为 changed bytes `1`、changed offsets `[0]`、unchanged bytes `351616`、
`exact_golden_match = true`。输入黄金文件复核后仍为原 SHA：

- A0 Top：`9305529D6C644C757F6B193671B84153F0ADEBE385E7B3B30552E9BC23513635`；
- P1 Bottom：`3B8302F6746AB2B78FA48599328DB7907788FA322D18ADF297280C8A5D3370C0`。

## 11. 实现后测试

执行环境均设置 `PYTHONPATH=src`、`PYTHONDONTWRITEBYTECODE=1`，Editor GUI 测试使用
`QT_QPA_PLATFORM=offscreen`，pytest 禁用 cache provider。

| 测试集 | 结果 | 本次可见计时 |
|---|---:|---:|
| Editor 全量 | `174 passed` | `2.865s` |
| 其中原有基线 | `134/134` 保留并通过 | — |
| Stage 7B-1 新测试 | `40 passed` | 包含在 Editor 全量中 |
| Uploader 全量 | `126 passed` | `1.965s` |

新测试覆盖 top/bottom 映射和 CLI、双向编辑、单字节与后缀一致性、错误大小/空文件/未知首字节/
不存在文件、同路径、三类输出冲突、双向 no-op、输入 SHA、写后复验、故障回滚、严格参数、
完整 JSON/Markdown、双向黄金 exact match、非黄金合法输入、无硬件/Uploader 导入及 GUI 未接入。

## 12. Uploader、GUI、Builder 与外部调用保护

| 检查 | 结果 |
|---|---|
| `git diff -- uploader` | 空，Uploader changes = `0` |
| Uploader tracked manifest SHA-256 | `59A22F8D3D1707AABFBEF1A900A1AFB34AC16063A5D3D5C24C13E79AB3093265`，前后相同 |
| Stage 6C 真实上传记录 SHA-256 | `967C936A1856F28362922017168C615256588001E6763D52E73D28850D342599`，前后相同 |
| `git diff -- editor/src/ultra3_editor/gui editor/tests/gui` | 空 |
| GUI 状态 | `READ ONLY`，编辑/导出/生成控件继续硬禁用 |
| GUI 调用 `set_time_position()` | `0` |
| Builder 公共接口 | `NOT AVAILABLE` |
| 资源画布 | `320×384`、`210×252` 测试继续通过 |
| GUI `320×505` | 不存在 |

实际调用统计：

```text
Bleak initialization: 0
BLE scan: 0
BLE connect: 0
FF02 writes: 0
adb: 0
Frida: 0
Uploader calls: 0
真实上传: 0
```

## 13. Frozen 保护

Frozen ZIP 未修改，复核结果：

```text
Ultra3_v0.2.4_Frozen_Baseline_2026-07-11.zip
size: 218518
SHA-256: 3581B0FA3D8E0B4BB952848CC45492B157DFFF4B125D57C93611FC89BF711231
```

Frozen changes = `0`。

## 14. 尚未支持与停止边界

以下内容仍未实现或未解锁：GUI 编辑接入（Stage 8A.2）、Builder、背景图导入、裁剪/适配、
RGB565、缩略图生成、时间颜色、日期/星期/健康组件、自由坐标、C8/C9 修改、BLE 上传。

本阶段没有提交、打标签或推送，没有进入 Stage 8A.2；等待人工验收。
