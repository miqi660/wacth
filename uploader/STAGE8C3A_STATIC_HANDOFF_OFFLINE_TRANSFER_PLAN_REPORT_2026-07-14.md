# Stage 8C-3A — Static Handoff → Offline Transfer Plan

## 结论

**PASS（仅离线）**

Stage 8C-3A 已实现 Validated Static Handoff 到确定性 C9 transfer plan 的公共核心与 CLI。
本阶段没有扫描或连接 BLE，没有 FF02/FF03 操作，没有真实上传，也没有修改动态 BCSDIAL
上传状态机。

## 1. 开始前审计

| 项目 | 结果 |
|---|---|
| 分支 | `main` |
| HEAD | `0aba87fd74e18d1cfcea4eba58312e5e9c230b48` |
| 本地 `origin/main` | 与 HEAD 一致 |
| 冻结标签 | `ultra3-editor-v0.3.8-stage8c2`，指向 HEAD |
| 工作区 | 修改前干净 |
| Uploader 基线 | 198 passed，零失败 |
| Editor 基线 | 288 passed，零失败 |

源码审计定位：

- Handoff：`uploader/src/ultra3_uploader/handoff.py`
- CLI：`uploader/src/ultra3_uploader/cli.py`
- C9 构造与解析：`uploader/src/ultra3_uploader/bc_frames.py`
- checksum：`uploader/src/ultra3_uploader/checksum.py`
- 动态上传：`uploader/src/ultra3_uploader/upload_bcsdial.py`
- Schema package resource：`uploader/src/ultra3_uploader/schemas/`
- Stage 8C-2 脱敏证据：`archives/static-upload/2026-07-14_greenlion_static_success_01/public/`

## 2. 边界决定

Handoff v1 只描述 351617-byte `greenlion_static_diy_complete_bin`，`transfer.payload_size` 和
`chunk_count` 必须为 `null`。因此 Uploader 不从 source BIN 生成 353146-byte payload，也不复制
Builder 的图像或 payload 编码职责。

离线计划构建必须显式接收：

- 已通过 `validate_handoff()` 的 Manifest；
- 位于显式 `bundle_root` 内的普通 payload 文件；
- 调用方提供的期望 payload SHA-256。

353146-byte payload 的冻结语义为：把 source 按 230-byte DATA 分块，并在每块后附现有 C9
checksum。故普通 region 是 `230 DATA + 1 checksum = 231 bytes`。构建完整 C9 时只为 region
补上 `BC C9 02 LEN SEQ_LE16`；代码通过既有 `build_c9()` 复核和构造，通过既有 `parse_c9()`
解析，未实现第二套 checksum。

## 3. 修改文件

| 文件 | 作用 |
|---|---|
| `uploader/src/ultra3_uploader/static_transfer.py` | 不可变计划模型、显式 payload 安全读取、C9 构建/重组/验证、确定性计划读写 |
| `uploader/src/ultra3_uploader/errors.py` | 增加 `StaticTransferPlanError` |
| `uploader/src/ultra3_uploader/cli.py` | 注册三个离线静态计划命令 |
| `uploader/src/ultra3_uploader/__init__.py` | 导出公共离线 API |
| `uploader/tests/static_transfer_fixtures.py` | 生成不含私有证据的确定性测试 fixture |
| `uploader/tests/test_static_transfer.py` | 核心、损坏、顺序、路径和确定性测试 |
| `uploader/tests/test_static_transfer_cli.py` | CLI PASS/FAIL、JSON 与无 BLE 参数测试 |
| `uploader/README.md` | 记录 Stage 8C-3A 离线用法和边界 |
| `docs/handoff/README.md` | 更新静态离线计划兼容性，不改变 Handoff v1 语义 |
| 本报告 | 冻结实现与验证结果 |

## 4. 公共 API 与计划格式

公共 API：

- `build_static_transfer_plan()`
- `verify_static_transfer_frames()`
- `write_static_transfer_plan()`
- `inspect_static_plan()`
- `verify_static_plan()`

不可变模型：

- `StaticTransferPlan`
- `StaticC9Frame`
- `StaticTransferVerification`

CLI：

- `build-static-plan`
- `inspect-static-plan`
- `verify-static-plan`

输出目录：

```text
static-plan/
├── manifest.json
└── c9_frames.bin
```

manifest 使用 `ultra3-static-transfer-plan/v1`，不记录当前时间、设备地址、本机绝对路径或随机值。
输出目录独占创建，不覆盖已有内容。完整私有 payload 和黄金 `c9_frames.bin` 没有写入仓库。

## 5. C8 与 CA 状态

| 项目 | 状态 | 原因 |
|---|---|---|
| C8 | `not_implemented` / `null` | Stage 8C-2 公开冻结证据未给出完整静态 C8 字段 |
| CA | `not_implemented` / `null` | 仅确认最后 C9 后观察到 CA，未冻结完整静态 CA 字节语义 |

本阶段没有伪造“完整静态上传计划”。当前计划只冻结已证实的 C9 离线部分。

## 6. 黄金 payload 离线验证

使用 Stage 8C-2 私有冻结 payload 只读构建计划，输出置于仓库外临时目录；以下结果均由 CLI
真实生成后再次读取验证：

| 项目 | 结果 |
|---|---:|
| source size | 351617 |
| source SHA-256 | `44b4893acf6244119de655b32c1ce760048f3128a24489b49ff24f7bb60fa664` |
| payload size | 353146 |
| payload SHA-256 | `19c1b72da080c5f23d0978ff7c93dbd10f8e07d6eaaeff4e3c4d08608e31bcf5` |
| C9 count | 1529 |
| sequence | 0..1528 |
| missing | 0 |
| duplicates | 0 |
| out of order | false |
| checksum failures | 0 |
| normal region | 231 |
| final region | 178 |
| normal frame | 237 |
| final frame | 184 |
| frame stream size | 362320 |
| reconstructed size | 353146 |
| reconstructed SHA-256 | `19c1b72da080c5f23d0978ff7c93dbd10f8e07d6eaaeff4e3c4d08608e31bcf5` |
| exact match | true |

冻结 source 与 payload 在验证前后哈希不变。

## 7. 测试

运行命令：

```powershell
$env:PYTHONPATH = (Resolve-Path '.\uploader\src').Path
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m pytest uploader -q -p no:cacheprovider
```

结果：

- 原 Uploader：198 passed，全部保留；
- 新增 Stage 8C-3A：33 passed；
- Uploader 总计：231 passed，0 failed；
- Editor 回归：288 passed，0 failed。

新增测试覆盖：1529 帧、连续 sequence、region/frame 尺寸、checksum、精确重组、任意帧修改、
缺包、重复、乱序、越界 sequence、末包错误、payload size/SHA 错误、非法 Handoff、不支持固件、
bundle 越界、元数据篡改、独占输出、重复构建确定性及 CLI 退出码/JSON 稳定性。

## 8. 副作用与未实现项

| 调用 | 次数 |
|---|---:|
| Bleak initialization | 0 |
| BLE scan | 0 |
| BLE connect | 0 |
| FF02 writes | 0 |
| FF03 notifications | 0 |
| adb | 0 |
| Frida | 0 |
| network requests | 0 |
| real uploads | 0 |

动态 `BCSDIAL` 的 `bc_frames.py`、`checksum.py`、`bcsdial.py`、`prepare_bcsdial.py`、
`upload_bcsdial.py` 和所有 BLE transport 文件均无差异。尚未实现 C8、CA、BLE static upload、
重试、断点续传或设备命令。

## 9. Git

未自动 commit，未自动 tag，未 push。最终以 `git diff --check`、`git diff --stat` 和
`git status --short` 的实际结果交付人工审查。
