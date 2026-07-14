# Stage 8B-1 — GreenLion Static Builder 公共核心报告

日期：2026-07-14  
状态：`COMPLETE — OFFLINE CORE ONLY`

## 1. Git 开始前审计

- 分支：`main`
- 工作区：修改前干净
- HEAD：`afb4e123289162992b60e07331f1348455051425`
- `origin/main`：`afb4e123289162992b60e07331f1348455051425`
- `git fetch origin`：成功
- 冻结标签：`ultra3-editor-v0.3.3-stage8b0`
- Stage 8B-0 报告、脚本及三个审计 JSON：均已纳入 HEAD
- Uploader 修改：`0`

## 2. 冻结证据重新验证

修改源码前重新执行 Stage 8B-0 完整只读审计，结果：

| 项目 | 结果 |
|---|---|
| 外部根清单 | `VERIFIED 105/105` |
| mismatch / missing / non-regular / undeclared | `0 / 0 / 0 / 0` |
| canonical manifest SHA-256 | `AC33C4A8D248F206E60E1125CDDE76B1AE2410946ACDCD0E5A29F060A7D6065C` |
| Frozen Builder SHA-256 | `94DCDE7A959B3A9F9F5939AC295C341A7D713DCD9EEBF2A95669F2F7C815A807` |
| 模板大小 | `351617` |
| 模板 SHA-256 | `5D04DE76C94DA9D7F7069AF3E6038E1575D3B42E5E009EAD590CE4DD33F5E1CC` |
| 模板前 17 字节 | `02 00 00 FF FF FF 00 00 80 01 40 01 FC 00 D2 00 00` |
| Pillow | `10.4.0` |
| 冻结 Builder 双次确定性 | `5/5` |
| 冻结 Builder 历史 exact match | `5/5` |
| Frozen ZIP SHA-256 | `3581B0FA3D8E0B4BB952848CC45492B157DFFF4B125D57C93611FC89BF711231` |

修改后再次复核外部根清单、canonical manifest、Frozen Builder、模板和 Frozen ZIP，结果完全相同。

## 3. 修改前基线

- Editor：`206 passed`
- Uploader：`126 passed`
- GUI 使用 `QT_QPA_PLATFORM=offscreen`
- 未删除、跳过或弱化既有测试

## 4. 新增与修改文件

新增：

- `src/ultra3_editor/greenlion_builder.py`：公共 Builder、模型、exact 算法、事务输出与报告
- `tests/test_greenlion_builder.py`：公共核心、算法、拒绝路径与事务测试
- `tests/test_greenlion_builder_cli.py`：CLI 正常、错误和禁止参数测试
- `tests/test_stage8b1_golden_verifier.py`：黄金验证器全部安全门测试
- `scripts/verify_stage8b1_golden.py`：只调用公共 API 的五样本双次验证器
- `artifacts/stage8b1_builder_core/`：10 个公共核心输出和规范化结果 JSON
- 本报告

修改：

- `src/ultra3_editor/errors.py`：结构化 Builder 异常
- `src/ultra3_editor/__init__.py`：公开 Builder API
- `src/ultra3_editor/cli.py`：`build-static-diy`
- `pyproject.toml`：严格依赖 `Pillow==10.4.0`
- `README.md`：公共核心使用说明和 GUI 边界

未修改：

- `src/ultra3_editor/time_position.py`
- `src/ultra3_editor/gui/`
- `uploader/`
- Stage 8B-0 证据、冻结 Builder、模板、图片和历史输出

## 5. 公共 API

```python
def build_greenlion_static_diy(
    build_input: GreenLionStaticBuildInput,
    *,
    config: GreenLionStaticBuildConfig = GreenLionStaticBuildConfig(),
    json_path: Path | None = None,
    report_path: Path | None = None,
) -> GreenLionStaticBuildResult:
    ...
```

公共入口由 `ultra3_editor.__init__` 导出。输入、配置、结果、资源区段及外部使用统计均为
`frozen=True` dataclass。没有第二套公开构建循环。

## 6. 结构化异常

新增最小异常层级：

- `BuildError`
- `BuilderInputError`
- `UnsupportedImageFormatError`
- `InvalidImageError`
- `UnsupportedTemplateError`
- `UnsupportedBuilderConfigError`
- `UnsupportedPillowVersionError`
- `BuildOutputExistsError`
- `BuildInputOutputSamePathError`
- `BuildVerificationError`

所有 Builder 异常都提供稳定 `error_code`，并可携带 `path`、`expected` 和 `actual`。CLI 通过
既有 `EditorError` 边界返回非零，不把 traceback 作为正常错误输出。

## 7. exact 构建链

唯一支持链：

1. 严格验证 Pillow `10.4.0`。
2. 验证配置只能是 `cover + auto-from-main`。
3. 在读取前检查输入/模板/所有输出路径冲突及已有输出。
4. 读取并哈希 PNG/JPEG 和模板。
5. 模板必须同时匹配大小、17 字节头和完整 SHA-256。
6. 图片按冻结语义 `convert("RGB")`。
7. 从同一输入分别执行主资源和缩略资源 cover；缩略图不是主资源二次缩放。
8. 使用 Python `round` 和 Pillow bilinear。
9. RGB565 使用 truncate：R5/G6/B5 直接右移。
10. 对两个资源分别应用 `greenlion-next-high`，各自最后 high byte 为 `00`。
11. 在内存中组装 `header + main + thumbnail`。
12. 验证完整大小、资源长度、模板头和 offset 0。
13. 已知黄金输入在写盘前验证目标 SHA；不匹配即失败。
14. 独占写入、逐字节回读、SHA 和布局复核。
15. 再次哈希输入图片和模板。
16. 由同一公共核心独占生成可选 JSON/Markdown。

## 8. 固定资源和文件布局

| 区域 | 范围（end exclusive） | 长度 |
|---|---:|---:|
| 模板头 | `0..17` | `17` |
| 主资源 | `17..245777` | `245760` (`320×384×2`) |
| 缩略资源 | `245777..351617` | `105840` (`210×252×2`) |

- 完整输出：`351617` 字节
- 模板前 17 字节：完整保留
- offset 0：`02`，没有调用时间位置编辑核心，也没有改写为 `00/01`
- 主资源：`320 × 384`，VERIFIED RESOURCE SIZE
- 缩略资源：`210 × 252`，VERIFIED RESOURCE SIZE
- Physical display geometry：`UNKNOWN`
- Visible display area：`UNKNOWN`

## 9. 支持和拒绝范围

支持：

- PNG
- JPEG
- RGB / RGBA 经 `convert("RGB")`
- exact 模板
- `cover`
- 自动同源独立缩略图
- 可选 JSON/Markdown

明确拒绝或未公开：

- stretch / contain
- 独立缩略图
- 保留模板缩略图
- 其他 Pillow 版本
- 非 PNG/JPEG 容器
- 非 exact 模板
- 自定义 resample / quantize / wire profile / preblur
- 时间位置参数
- `--force`
- 任何已有输出覆盖
- 协议分包、传输、上传、GUI 集成

## 10. 路径与事务安全

- 输入图片、模板、BIN、JSON、Markdown 不能指向同一路径或互相重复。
- 所有输出先检查不存在，实际创建继续使用 `x/xb` 原子独占模式。
- 不提供覆盖确认或 `--force`。
- 写后逐字节比较并验证大小、SHA、头部和两个资源段。
- 任一写入、回读、黄金匹配或报告失败，删除且只删除本次调用创建的文件。
- 不删除调用前已有文件，不修改输入图片或模板。
- JSON/Markdown 只保存文件名，不保存用户名或私人绝对路径。

## 11. 黄金公共核心验证

`scripts/verify_stage8b1_golden.py` 只导入并调用
`ultra3_editor.build_greenlion_static_diy()`；没有导入或执行冻结 Builder。每个输入构建两次，
逐字节比较历史输出。

| 样本 | 公共核心 SHA-256 | run1=run2 | 历史 exact | golden |
|---|---|---|---|---|
| photo01 | `44B4893ACF6244119DE655B32C1CE760048F3128A24489B49FF24F7BB60FA664` | 是 | 是 | true |
| photo02 | `CBD34D9BE77B138481AB7AD590326CC7437EE55C45DBECB532A0DF1C4F8A2763` | 是 | 是 | true |
| photo03 | `19CAF5303D780FD6C4F46DED3219AD41E839FD495A1A96C51FD40EAE296C23B6` | 是 | 是 | true |
| photo04 | `7F1F531F94E6C312FFEF167B03B2988AAC44A42790ABA19A6EED9F03795344C9` | 是 | 是 | true |
| photo05 | `62E2B481F62C270937E090AD69CC87A34A11B7DDBEFFCA1B70D31AE638CB4078` | 是 | 是 | true |

统计：

- 公共核心黄金匹配：`5/5`
- 双次确定性：`5/5`
- 历史逐字节一致：`5/5`
- 输入图片不变：`5/5`
- 历史输出不变：`5/5`
- 模板不变：是
- 每份输出大小：`351617`
- 每份 offset 0：`02`

## 12. Artifact

目录：`artifacts/stage8b1_builder_core/`

- `golden_results.json`：7475 字节，使用 `$FROZEN_BASELINE` / `$OUTPUT` 逻辑路径
- `photo01_run1.bin` … `photo05_run2.bin`：10 份，每份 351617 字节
- 文件数：`11`
- 总大小：`3523645` 字节
- 私人绝对路径扫描：无命中

## 13. CLI

```powershell
python -m ultra3_editor build-static-diy `
  --image "<PNG/JPEG>" `
  --template "<verified-template.bin>" `
  --output "<output.bin>" `
  --json "<build.json>" `
  --report "<build.md>"
```

CLI 只提供以上五个参数。禁止选项测试覆盖 `--force`、`--thumbnail`、`--time-position`、
`--wire-profile`、`--quantize`、`--resample`、`--fit` 和 `--preblur`。

使用真实 photo05 和模板执行离线 CLI，结果：

- output size：`351617`
- output SHA-256：`62E2B481F62C270937E090AD69CC87A34A11B7DDBEFFCA1B70D31AE638CB4078`
- header preserved：`true`
- offset 0：`02`
- output revalidated：`true`
- exact golden match：`true`
- external usage：`0`

## 14. 测试

新增 `44` 项测试，覆盖：

- exact 布局、头部与 offset 0
- PNG、JPEG、RGB、RGBA
- 独立缩略图
- cover / Python round / bilinear
- RGB565 truncate 和 next-high 固定向量
- Pillow 版本门禁
- 模板大小、头部、SHA
- 非 exact 配置拒绝
- 缺失/损坏/不支持图片
- 输入输出同路径、重复路径、已有输出
- 写后复核和报告失败回滚
- JSON/Markdown 完整性及路径隐私
- 已知黄金不匹配硬失败
- 模型不可变和公共导出
- CLI 正常、错误非零、必填参数和禁止参数
- 无外部/网络/时间位置编辑依赖

最终结果（包含冻结前可靠性补强）：

- Editor：`266 passed in 4.89s`
- 原 Editor 206 项：全部保留
- Stage 8B-1 初始新增测试：`44 passed`
- 冻结前可靠性补强新增测试：`16 passed`
- Stage 8B-1 累计新增测试：`60 passed`
- Uploader：`126 passed in 1.67s`
- `git diff -- uploader`：无输出
- `git diff -- editor/src/ultra3_editor/gui`：无输出
- `git diff -- editor/src/ultra3_editor/time_position.py`：无输出
- `git diff --check`：通过

## 15. 静态边界扫描

Builder 生产模块扫描确认没有：

- 外部设备库或硬件 API
- 网络客户端、socket 或子进程
- shell、动态执行或 pickle
- C9/传输分包实现
- 时间位置编辑导入或调用
- GUI 导入

两个资源缓冲区只参与完整 BIN 的离线组装；本阶段没有实现任何传输容器或上传数据生成。

## 16. 外部调用统计

| 项目 | 次数 |
|---|---:|
| 硬件初始化 | 0 |
| 扫描 | 0 |
| 连接 | 0 |
| 特征写入 | 0 |
| adb | 0 |
| Frida | 0 |
| Uploader | 0 |
| 网络请求 | 0 |
| 真实上传 | 0 |

## Freeze Reliability Hardening

本次冻结前补强只修改公共结果语义、黄金状态、事务回滚和黄金验证器，不改变任何图像字节算法。

### 单次确定性语义

- 新增 `BuildDeterminismStatus`：`not_evaluated` / `verified_repeat`。
- 普通 `build_greenlion_static_diy()` 固定返回 `NOT_EVALUATED`。
- `repeated_build_sha256` 固定为 `None`。
- 公共函数内部没有为了证明确定性而重复构建。
- 双次确定性只由独立 `verify_stage8b1_golden.py` 判断并记录
  `repeat_determinism_verified=true`。

### 黄金状态

- 新增 `GoldenBuildStatus`：`match` / `not_applicable` / `mismatch`。
- 已知黄金输入成功：`MATCH` 且 `exact_golden_match=True`。
- 普通合法图片：`NOT_APPLICABLE` 且 `exact_golden_match=None`。
- 已知输入不匹配：不返回结果，抛出 `BuildVerificationError`，异常携带 `MISMATCH`、期望 SHA
  和实际 SHA。
- JSON 与 Markdown 均写入稳定枚举字符串。
- 两个枚举均由 `ultra3_editor` 公共导出。

### 回滚失败处理

- 新增 `BuildRollbackError(BuildVerificationError)`。
- 字段包含 `error_code`、`original_error_type`、`original_error_message` 和
  `failed_cleanup_paths`。
- 公共核心只回滚本次调用创建的文件，并尝试清理全部路径。
- 全部清理成功时重新抛出原始异常；任一路径清理失败时，以原始异常为 cause 抛出
  `BuildRollbackError`，明确提示可能存在未完成文件。
- `_write_binary_exclusive()` 和 `_write_text_exclusive()` 的部分写入失败使用同一回滚报告语义。
- 不捕获 `BaseException`，`KeyboardInterrupt` 和 `SystemExit` 不会被吞掉。
- 不删除调用前已有文件。

### 强化黄金验证器

每个样本的 passed 条件现同时要求：双次逐字节一致、历史逐字节一致、两次 SHA 等于期望、
两次 `golden_status=match`、两次 `exact_golden_match=True`、大小 351617、offset 0 为 2、
写后复核通过、输入和历史输出未变、两次单次状态均为 `not_evaluated`，且两次
`repeated_build_sha256` 均为 `null`。

顶层 `COMPLETE` 同时要求模板未变、`passed_count=5`、`repeat_deterministic_count=5` 和
`historical_exact_match_count=5`。

### 补强验证结果

- 原测试：`250` 项全部保留。
- 新增可靠性测试：`16` 项。
- 最终 Editor：`266 passed in 4.89s`。
- Uploader：`126 passed in 1.64s`。
- 十份黄金 BIN SHA：全部与补强前一致。
- 黄金验证：`5/5 repeat exact`、`5/5 historical exact`、`5/5 golden MATCH`。
- 所有输出：`351617` 字节、offset 0=`02`、写后复核通过。
- GUI 差异：`0`。
- Uploader 差异：`0`。
- `time_position.py` 差异：`0`。
- 外部设备、ADB、Frida、Uploader 和真实上传调用：`0`。

## 18. 最终状态

Stage 8B-1 已把冻结 v0.2.4 exact 行为提取为唯一、可测试、可审计的离线公共核心。五份历史
样本全部双次确定并逐字节一致；输入、模板、历史输出、Frozen Builder、外部清单和 Frozen ZIP
均未改变。GUI 仍保持原状态，Builder 尚未接入 GUI；没有进入 Stage 8B-2，也没有执行真实上传。

本阶段未提交、未打标签、未推送，等待人工验收。
