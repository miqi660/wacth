# Stage 8B-0 — Builder v0.2.4-greenlion-exact 冻结实现审计与公共 API 设计

日期：2026-07-14  
状态：`COMPLETE · AUDIT ONLY · NO PRODUCTION BUILDER IMPLEMENTED`

## 1. 范围与结论

本阶段仅审计冻结的 `Ultra3 Builder v0.2.4-greenlion-exact`，生成证据清单并设计下一阶段
公共 API。没有修改冻结源码、样本、Stage 7B-1、Stage 8A.2 GUI 或 Uploader，也没有实现
公共 Builder、CLI 或 GUI 接入。

核心结论：

- Frozen ZIP SHA-256 正确，36 个 ZIP 条目和 35 个包内声明哈希全部匹配，无 path traversal。
- 真实 Builder 是一个 13786 字节的独立 Python CLI 脚本，不是当前 Editor 包的一部分。
- 主图 `320 × 384` 与缩略图 `210 × 252` 由同一输入图片分别缩放和编码。
- 标准 RGB565 和 GreenLion next-high wire 实现已在冻结源码中定位，并由冻结函数和中间产物
  双重验证。
- 5 张历史输入均完成两次仓库外复现；10 次新输出与 5 份历史输出逐字节完全一致。
- Builder 从模板保留前 17 字节；冻结模板 offset 0 实际为 `02`，不是 Stage 7B-1 已验证的
  `00/01`。下一阶段不得复制时间位置 patch，也不得未经新证据直接调用 `set_time_position()`。
- 五类真机结果有历史文字记录和一次完整 C9 替换日志，但没有逐样本真机截图或逐样本抓包，
  证据等级均为 Level C。

## 2. Git 审计

开始前结果：

| 项目 | 结果 |
|---|---|
| 分支 | `main` |
| 工作区 | 干净 |
| HEAD | `dd7eb2636b0d55ca82ccf831d3b38614818ff84c` |
| origin/main | `dd7eb2636b0d55ca82ccf831d3b38614818ff84c` |
| 最新提交 | `dd7eb26 feat(gui): integrate verified time position editing` |
| 标签 | `ultra3-editor-v0.3.2-stage8a2` 存在并指向 HEAD |
| Uploader 未提交差异 | 0 |

执行了 `git fetch origin`，随后重新确认 `HEAD = origin/main`。未执行 reset、clean、checkout、
commit、tag 或 push。

## 3. 修改前测试基线

| 项目 | 结果 | 时间 |
|---|---:|---:|
| Editor | `206 passed` | 3.573 秒 |
| Uploader | `126 passed` | 2.088 秒 |

## 4. Frozen ZIP

仓库当前未跟踪或保存此 ZIP；只读审计使用项目冻结归档中的副本。提交产物统一记为：

```text
$FROZEN_ZIP
```

| 项目 | 结果 |
|---|---|
| 大小 | 218518 bytes |
| SHA-256 | `3581B0FA3D8E0B4BB952848CC45492B157DFFF4B125D57C93611FC89BF711231` |
| 预期哈希匹配 | 是 |
| ZIP 条目 | 36 |
| path traversal | 0 |
| `PACKAGE_CHECKSUMS.sha256` 声明条目 | 35 |
| 内部 SHA-256 不匹配 | 0 |
| 未声明/缺失条目 | 0 / 0 |

完整条目大小、压缩大小、CRC32 和逐文件 SHA-256 位于
`artifacts/stage8b0_builder_audit/frozen_zip_manifest.json`。ZIP 目录内容为：

| ZIP 路径（省略顶层包目录） | 大小 | CRC32 |
|---|---:|---|
| `PACKAGE_CHECKSUMS.sha256` | 5380 | `E95B00A1` |
| `README_FIRST.md` | 592 | `B232199C` |
| `baseline/.../CHECKSUMS.sha256` | 3213 | `4F743328` |
| `baseline/.../FROZEN.lock` | 118 | `DB9F48DC` |
| `baseline/.../README.md` | 1730 | `98B9D405` |
| `baseline/.../builder/rebuild_official_from_pre_rgb565_v1.py` | 2971 | `822F31CE` |
| `baseline/.../builder/ultra3_builder_v0.2.4-greenlion-exact.py` | 13786 | `345C3369` |
| `baseline/.../docs/Ultra3_MActivePro_GreenLion_BLE_Protocol.md` | 14921 | `A034592A` |
| `baseline/.../docs/greenlion_photo_watchface_protocol.md` | 1570 | `36AC9815` |
| `baseline/.../evidence/VALIDATION.txt` | 289 | `93455D16` |
| `baseline/.../evidence/device_tests/README.md` | 687 | `ACC7ED88` |
| `baseline/.../evidence/official_pre_rgb565_210x252.png` | 14597 | `89A6B240` |
| `baseline/.../evidence/official_pre_rgb565_320x384.png` | 25517 | `6E1B0C23` |
| `baseline/.../evidence/official_real_file_analysis.txt` | 483 | `130DD59B` |
| `baseline/.../evidence/wire_profile_proof.json` | 1133 | `91086C5E` |
| `baseline/.../metadata.json` | 1521 | `8A546387` |
| `baseline/.../sample/main_greenlion_wire.bin` | 245760 | `8A5830D7` |
| `baseline/.../sample/main_intended_rgb565_preview.png` | 6064 | `0A6D6D19` |
| `baseline/.../sample/main_normal_rgb565_le.bin` | 245760 | `596BD22F` |
| `baseline/.../sample/main_preprocessed.png` | 6353 | `13E08527` |
| `baseline/.../sample/main_wire_naive_preview.png` | 6458 | `B998612E` |
| `baseline/.../sample/metadata.json` | 1818 | `765D9838` |
| `baseline/.../sample/official_calibration_351617.bin` | 351617 | `347B8042` |
| `baseline/.../sample/payload_353146.bin` | 353146 | `925AC3DD` |
| `baseline/.../sample/real_file_351617.bin` | 351617 | `F5956612` |
| `baseline/.../sample/thumb_greenlion_wire.bin` | 105840 | `8E7ABE23` |
| `baseline/.../sample/thumb_intended_rgb565_preview_210x252.png` | 9817 | `CD3689A4` |
| `baseline/.../sample/thumb_normal_rgb565_le.bin` | 105840 | `56F4D4B2` |
| `baseline/.../sample/thumb_preprocessed_210x252.png` | 12514 | `D3344E36` |
| `baseline/.../sample/thumb_wire_naive_preview_210x252.png` | 10821 | `FA5F3012` |
| `baseline/.../sample/ultra3_calibration_320x384.png` | 6353 | `13E08527` |
| `baseline/.../tools/capture_final_binder_c9.js` | 8985 | `DA44E3D1` |
| `baseline/.../tools/capture_hi8_bitmap_pipeline_v1.js` | 9061 | `C153229D` |
| `baseline/.../tools/capture_official_real_async_v2.js` | 4741 | `F0D95819` |
| `baseline/.../tools/compare_ultra3_real_files.py` | 5847 | `9FE4899A` |
| `freeze_to_project.ps1` | 4551 | `3C8771EC` |

ZIP 未解压到仓库，也未被修改。

## 5. Builder 候选与真实入口

本机 copy-only 冻结基线包含 106 个文件；当前 Git 仓库名称候选为 8 个，均不是公共
Builder 实现。完整候选角色、大小、SHA、tracked 状态和分类位于
`artifacts/stage8b0_builder_audit/builder_file_manifest.json`。

关键候选：

| 角色 | 相对冻结基线路径 | 大小 | SHA-256 |
|---|---|---:|---|
| 真实 Builder/CLI | `builder/ultra3_builder_v0.2.4-greenlion-exact.py` | 13786 | `94DCDE7A959B3A9F9F5939AC295C341A7D713DCD9EEBF2A95669F2F7C815A807` |
| 官方预处理重建工具 | `builder/rebuild_official_from_pre_rgb565_v1.py` | 2971 | `D7BA9AC845E8386C9634CB14DD54D9F3FF169E8E644D67E85DC23711B73EFCB6` |
| 固定模板/官方黄金 | `sample/official_calibration_351617.bin` | 351617 | `5D04DE76C94DA9D7F7069AF3E6038E1575D3B42E5E009EAD590CE4DD33F5E1CC` |
| 校准输入 | `sample/ultra3_calibration_320x384.png` | 6353 | `DB0E23F2482E5B684607B196D59D50FA1652B0FD41BB04C7101034C602DA83BA` |
| exact rebuild 证据 | `evidence/VALIDATION.txt` | 289 | `A099C977413CA09844863B03F8E48A902D4A481D884EC64F013EC7100CB0E6C1` |
| wire 证据 | `evidence/wire_profile_proof.json` | 1133 | `837495A2A922981384FDCEB86C172BD123042B63ED1C6CA7F8DDC74C7CD69790` |
| 本机上传日志 | `evidence/local_additions/v024_greenlion_test.txt` | 7185 | `36DDB34B2F3F3E92C27A8194E6C70643B7125C6588AD0B19A903D0F7D99F7148` |

真实入口为脚本的 `main()` 和 `argparse` CLI；没有 Python 包入口、`__version__` 或公共函数
契约。版本来自文件名、CLI 输出和生成的 `metadata.json` 字符串。

## 6. 运行环境与依赖

| 项目 | 审计结果 |
|---|---|
| 冻结代码声明的 Python 版本 | 未声明 |
| 代码语法最低推断 | Python 3.9+；未作为冻结契约验证 |
| 本次复现 Python | 3.10.8 |
| 第三方依赖 | Pillow；冻结包没有 requirements/lock 文件 |
| 本次 Pillow | 10.4.0 |
| OpenCV / numpy | 未导入 |
| 外部可执行程序 | Builder 本身不调用 |
| 网络 / GreenLion / MActivePro / adb / Frida / BLE | 不调用 |
| 随机性、时间戳、机器名写入 BIN | 无 |
| 绝对路径 | 代码不固定路径；metadata 会保存调用参数的实际路径 |

由于使用 `Image.Resampling`，Pillow 的可用版本范围应在下一阶段显式冻结；当前冻结包没有
依赖版本契约。

## 7. 图片输入契约

冻结 CLI 接受一个 `--image`，不接受独立缩略图。`--mode full` 时同一图片分别生成主图与
缩略图；`main-only` 时只替换主图并保留模板缩略图。

| 能力 | 结论 |
|---|---|
| JPEG | VERIFIED：1 个历史输入和双次复现 |
| PNG | VERIFIED：4 个历史输入和双次复现 |
| BMP/其他 Pillow 格式 | UNKNOWN；代码交给运行时 Pillow，冻结证据未覆盖 |
| RGB | VERIFIED |
| RGBA | VERIFIED：photo02；直接 `convert("RGB")` |
| 灰度/调色板 | CODE PATH PRESENT，但无冻结样本，未升级为设备验证 |
| EXIF 旋转 | NOT SUPPORTED；没有 `ImageOps.exif_transpose()`，唯一 JPEG orientation 为 1 |
| ICC profile | NOT SUPPORTED；没有显式色彩管理 |
| alpha 合成 | NOT SUPPORTED；直接丢弃 alpha，没有背景合成策略 |
| 非标准尺寸 | SUPPORTED BY CODE；进入 fit 流程 |
| 超大/小图片限制 | 无显式限制 |
| 输入修改 | 无；只读打开和哈希 |

5 张历史输入实际为：JPEG/RGB `4320×3240`、PNG/RGBA `1081×608`、三个 PNG/RGB
`2560×1600`。没有根据图片内容推断或补写类别名称。

## 8. resize、crop 与预处理

| 选项 | 真实行为 |
|---|---|
| `stretch` | 直接缩放到目标尺寸 |
| `cover` | 按较大比例缩放，使用 Python `round()` 计算尺寸，中心裁剪 |
| `contain` | 按较小比例缩放，居中放到黑色 RGB 画布 |
| resample | nearest/bilinear/bicubic/lanczos；默认 bilinear |
| preblur | GaussianBlur；默认 0，不处理 |
| 主图 | 独立调用 fit/preblur/encode，目标 `320×384` |
| 缩略图 | 独立调用 fit/preblur/encode，目标 `210×252` |

五个历史成功输出均使用 `full + cover + bilinear + truncate + greenlion-next-high + preblur 0`。

## 9. 标准 RGB565

冻结函数 `image_to_normal_rgb565_le()`：

```text
r5 = r >> 3
g6 = g >> 2
b5 = b >> 3
word = (r5 << 11) | (g6 << 5) | b5
output = low byte, high byte
```

默认量化为截断；可选 `round(value * max / 255)`，但五类成功样本没有使用 round。输入先
`convert("RGB")`，主图和缩略图共用同一函数，没有 BGR 通道交换。

以下结果由审计脚本直接调用冻结函数产生，并非另写算法：

| 像素 | RGB | 标准 RGB565 LE |
|---|---|---|
| black | 0,0,0 | `0000` |
| white | 255,255,255 | `FFFF` |
| red | 255,0,0 | `00F8` |
| green | 0,255,0 | `E007` |
| blue | 0,0,255 | `1F00` |
| middle gray | 128,128,128 | `1084` |
| asymmetric | 18,165,124 | `2F15` |

## 10. GreenLion wire 编码

冻结实现位于 `apply_greenlion_next_high()`：

```text
wire[2*i]   = normal[2*i]
wire[2*i+1] = normal[2*(i+1)+1]
last high   = 0
```

验证结果：

- 主图冻结 normal → wire exact match：是。
- 缩略图冻结 normal → wire exact match：是。
- 主图/缩略图最后高字节：均为 `00`。
- 主图 wire：245760 bytes；缩略图 wire：105840 bytes。
- 主图行边界不重置：已用第 320/321 个线性像素验证。
- 主图和缩略图分别调用编码函数，各自结束链；不存在跨资源串联。
- 没有行反转、旋转或镜像。

最小连续像素向量的 wire 为：

```text
normal: 0000 FFFF 00F8 E007 1F00 1084 2F15
wire:   00FF FFF8 0007 E000 1F84 1015 2F00
```

## 11. 完整 BIN 组装

Builder 先复制完整模板，再只替换两段资源：

| 区域 | offset | 长度 | 状态 |
|---|---:|---:|---|
| 模板头 | 0..16 | 17 | VERIFIED：完全保留 |
| 主图 wire | 17..245776 | 245760 | VERIFIED |
| 缩略图 wire | 245777..351616 | 105840 | VERIFIED |
| 总计 | 0..351616 | 351617 | VERIFIED |

冻结模板头：

```text
02 00 00 FF FF FF 00 00 80 01 40 01 FC 00 D2 00 00
```

其中主图高/宽 `384/320`、缩略图高/宽 `252/210` 与冻结分析一致。其他头字段语义没有由
本阶段新增证据证明，保持 `OBSERVED/UNKNOWN`。Builder 不生成文件级 checksum、metadata 区
或固定尾部；前 17 字节全部依赖模板。

Builder 还会把完整 BIN 按 230 字节切块，在每块后附一字节
`(seq_low + seq_high + sum(data)) & 0xff`，产生 353146 字节 payload 和 1529 块。该 payload
不是完整 C9 帧流，不能与 351617 字节 BIN 混为一谈。

## 12. offset 0 与时间位置边界

冻结模板 offset 0 为 `02`；Builder 使用 `bytearray(template)`，从 offset 17 才开始替换，
所以输出 offset 0 也为 `02`。Builder 没有设置 Top/Bottom，也没有时间位置参数。

Stage 7B-1 的 `set_time_position()` 只验证 `00/01`，适用于后续已验证的 GreenLion Static DIY
重组样本。当前证据不足以证明 v0.2.4 模板中的 `02` 与该字段同义。因此：

- 不在 Builder 复制 offset patch。
- Stage 8B-1 第一版不接受 `TimePosition`。
- 只有取得使用 `00/01` 头部且与本 Builder 资源布局兼容的模板证据后，才可采用
  `Builder → set_time_position()` 后处理链。

## 13. 确定性复现

临时输出位于仓库外，提交产物统一记为：

```text
$TEMP_AUDIT
```

每个样本运行两次，输出目录在调用前必须不存在。结果：

| 样本 | 输入 SHA-256 | 历史 real SHA-256 | run1/run2/历史 | changed bytes |
|---|---|---|---|---:|
| photo01 | `9FDBB04E9DD910296B44BECB98C25A0C988A4B1B98EC0DAE12A0E831BC747CB4` | `44B4893ACF6244119DE655B32C1CE760048F3128A24489B49FF24F7BB60FA664` | exact | 0 |
| photo02 | `993BE3445975504C1BD2E587E38D5E22F421305161FEEBCCB8C1AE0BEA638ACD` | `CBD34D9BE77B138481AB7AD590326CC7437EE55C45DBECB532A0DF1C4F8A2763` | exact | 0 |
| photo03 | `158C38A2E0713B7B1AE5F24A346C24A72102A1F2E3FD49ACA71DB5CAD8D2A6E5` | `19CAF5303D780FD6C4F46DED3219AD41E839FD495A1A96C51FD40EAE296C23B6` | exact | 0 |
| photo04 | `8AA6F1830BE27CDC86DCE7A44997B6FD32EBF4A419E5F74A6420C579870C8BE7` | `7F1F531F94E6C312FFEF167B03B2988AAC44A42790ABA19A6EED9F03795344C9` | exact | 0 |
| photo05 | `0748AADB7C9B20D99C78C4165E77B0129B8554AB331F670886E3D0BD3F3E6828` | `62E2B481F62C270937E090AD69CC87A34A11B7DDBEFFCA1B70D31AE638CB4078` | exact | 0 |

统计：可复现样本 `5/5`，run1/run2 确定性 `5/5`，历史 exact match `5/5`。输入、模板、
历史 real/payload 和 Frozen ZIP 前后 SHA 均不变。完整命令、payload SHA、逐字节 ranges 和
环境版本位于 `reproduction_results.json`。

确定性结论限定于 Python 3.10.8、Pillow 10.4.0 和已记录参数；冻结包没有 Pillow lock，跨版本
像素重采样的完全一致性尚未证明。

## 14. 五类真机证据分级

| 样本 | 输入 | Builder 输出 | 文字/上传日志 | 真机截图 | 逐样本抓包 | 等级 |
|---|---|---|---|---|---|---|
| photo01 | 有 | 有 | 有历史总记录 | 缺失 | 缺失 | C |
| photo02 | 有 | 有 | 有历史总记录 | 缺失 | 缺失 | C |
| photo03 | 有 | 有 | 有历史总记录 | 缺失 | 缺失 | C |
| photo04 | 有 | 有 | 有历史总记录 | 缺失 | 缺失 | C |
| photo05 | 有 | 有 | 有历史总记录 | 缺失 | 缺失 | C |

`v024_greenlion_test.txt` 记录一次 1529 块替换完成和 CA，但没有把每次上传与五个具体输出逐一
绑定。冻结说明也明确写出五张截图和 Frida 日志未自动包含。因此结论为：

`HISTORICALLY REPORTED · ARTIFACTS INCOMPLETE`

本阶段没有否定历史真机结果，也没有伪造 Level A/B 证据。

## External Baseline Provenance

包含五张输入和五组历史输出的外部 copy-only baseline 是本机冻结后的扩展基线，不属于
36-entry Frozen ZIP。Frozen ZIP 完整性结论保持独立，不使用外部 baseline 补齐 ZIP 条目。

外部 baseline 根清单验证：

| 项目 | 结果 |
|---|---|
| checksum 文件 | `CHECKSUMS.sha256` |
| checksum 文件 SHA-256 | `EBEC5E71B6D32725D93264335FD89E7AD6E8225C95AA7EA9BF17D9F6F28FAA6A` |
| 声明数量 | 105 |
| 验证匹配 | 105 |
| 哈希不匹配 | 0 |
| 缺失 | 0 |
| 非普通文件 | 0 |
| 未声明文件 | 0（按设计不计清单自身） |
| 清单是否声明自身 | 否；识别为合法的 self-excluded 设计 |
| canonical manifest entries | 105 |
| canonical manifest SHA-256 | `AC33C4A8D248F206E60E1125CDDE76B1AE2410946ACDCD0E5A29F060A7D6065C` |
| external baseline integrity | `VERIFIED` |

canonical 输入严格按相对路径排序，每行使用
`<relative_path>\t<size>\t<SHA256>\n`，路径为 `/`、SHA 为大写、编码为 UTF-8、换行为 LF；
不包含绝对路径、修改时间、用户名或机器名。

历史 oracle 覆盖：

| 对象 | CHECKSUMS 覆盖且匹配 |
|---|---|
| 五张输入图片 | 是，5/5 |
| 五份历史 real BIN | 是，5/5 |
| 五份历史 payload | 是，5/5 |
| 冻结 Builder | 是 |
| 模板 | 是 |
| `FROZEN.lock` | 是 |
| `LOCAL_FREEZE.json` | 是 |

`FROZEN.lock` 大小 118 bytes，SHA-256 为
`980FA8F8FAF6EB9CC5DF6E1F8CF499E8EF2F5F3ABE68AC9BCF56DB5450B782CE`。内容声明
`FROZEN_STABLE_DEVICE_VERIFIED` 和不可原地修改规则；可信依据是根清单覆盖和哈希匹配，
不是文件名。

`LOCAL_FREEZE.json` 大小 533 bytes，SHA-256 为
`A1A602CE237BC205F026FCF7782F2D245715E54D884CF039AAB36A522A1E8985`。JSON 可解析，预期
8 个字段存在，`archive_mode=copy_only`、`original_files_moved=false`、记录文件数 105 与清单
声明数一致。其 `source_package` 和 `destination` 值只用于本地执行，提交 JSON 不保存这些值。
该文件没有任何 SHA/hash 字段，因此“其中记录的哈希是否匹配”为
`UNKNOWN_NO_HASH_FIELDS`；仅能确认 `LOCAL_FREEZE.json` 本身受根清单保护。

结论必须分开表达：

- Build reproducibility：`5/5 exact`。
- Historical oracle integrity：`VERIFIED`。
- Device evidence：仍为 `Level C`，没有升级为 Level A/B。

## Path Normalization

审计执行仍使用本机真实路径读取冻结基线并在仓库外运行 Builder；路径规范化只发生在 JSON
序列化阶段，不改变实际命令、文件哈希、复现输出或比较逻辑。

提交产物只使用以下逻辑根：

| 逻辑根 | 含义 |
|---|---|
| `$REPO/` | 当前仓库内文件 |
| `$FROZEN_BASELINE/` | 外部 copy-only baseline |
| `$FROZEN_ZIP` | Frozen ZIP |
| `$TEMP_AUDIT/` | 仓库外本阶段复现目录 |
| `<PYTHON>` | 实际 Python 解释器 |

`command` 数组保留参数顺序和语义，但不保存 Python 安装路径、用户名、Desktop/AppData 路径
或临时目录真实位置。公开仓库产物的隐私扫描结果为 0 命中。

## 15. 安全调用审计

冻结 Builder 只导入 `argparse`、`hashlib`、`json`、`pathlib`、`typing` 和 Pillow。

| 检查 | 结果 |
|---|---|
| 网络/requests/urllib/socket | 无 |
| Bleak/Bluetooth/FF02 | 无 |
| adb/Frida/Uploader | 无 |
| subprocess/os.system/shell | Builder 中无 |
| eval/exec/pickle | 无 |
| tempfile/rmtree/删除目录 | 无 |
| 修改输入 | 无 |
| 输出覆盖 | 有风险：`mkdir(exist_ok=True)` 后固定文件名 `write_bytes/save/write_text` |
| 事务输出 | 无 |
| 路径穿越 | Builder 不处理归档；无专门路径约束 |
| 临时文件泄漏 | Builder 不使用临时文件 |

冻结 Builder 曾真机成功，但现有输出策略不适合直接作为公共 API：已有输出会被静默覆盖，
多个文件可能只写入一部分，metadata 含环境绝对路径。

## 16. 公共 API 设计（仅设计）

### 16.1 最小输入与配置

建议下一阶段保留真实能力，不引入独立缩略图或猜测参数：

```python
@dataclass(frozen=True)
class GreenLionStaticBuildInput:
    image_path: Path
    template_path: Path
    output_path: Path


@dataclass(frozen=True)
class GreenLionStaticBuildConfig:
    fit_mode: FitMode = FitMode.COVER
    thumbnail_mode: ThumbnailMode = ThumbnailMode.AUTO_FROM_MAIN
```

第一版固定：bilinear、truncate、greenlion-next-high、preblur 0。冻结代码虽然实现更多选项，
但五类真机证据只覆盖上述组合；不为未验证组合提前扩展公共 API。

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

`FitMode` 先定义实际算法名称 `COVER/STRETCH/CONTAIN`，但 Stage 8B-1 公开支持范围建议先限制
为 `COVER`。`ThumbnailMode` 对应真实路径：`AUTO_FROM_MAIN` 和 `PRESERVE_TEMPLATE`；没有
`SEPARATE_IMAGE`，因为冻结实现不支持。

### 16.2 结果模型

`GreenLionStaticBuildResult` 建议包含：

- `status`、`builder_version`、`container`、`firmware_scope`
- 输入/模板/输出路径、大小和 SHA-256
- `main_resource_size=(320, 384)`、`thumbnail_resource_size=(210, 252)`
- `fit_mode`、`thumbnail_mode`、固定编码配置
- `output_size`、`output_sha256`、`output_revalidated`
- `template_sha256`、`template_header_hex`、`changed_regions`
- `input_unchanged`、`template_unchanged`
- `deterministic`、`repeated_build_sha256`
- `exact_golden_match`：仅校准输入+模板命中已知组合时为 true；其他合法输入为 not_applicable
- `external_usage`、`warnings`、`errors`

`template_path` 不能隐藏：完整 BIN 的头部来源于模板。除非下一阶段把经过许可和哈希固定的模板
作为包资源，否则调用者必须显式提供。

### 16.3 异常模型

建议最小层级：

- `BuildError`
- `BuilderInputError`
- `UnsupportedImageFormatError`
- `InvalidImageError`
- `UnsupportedTemplateError`
- `BuildOutputExistsError`
- `BuildInputOutputSamePathError`
- `BuildVerificationError`

不需要为每个 Pillow 异常复制一层；统一映射到可读输入错误即可。

### 16.4 输出、临时文件与复核

- 输入和模板先哈希，不修改。
- 完整 BIN 在内存中生成，仅 351617 bytes。
- 输出使用独占创建，不提供 `--force`。
- 写后重新读取，验证大小、SHA、模板头保留和两段长度。
- JSON/Markdown 由公共核心生成；不得包含不必要的私人绝对路径。
- 任一失败不留下宣称成功的结果；清理由公共核心负责。
- 无随机性、时间戳或机器路径进入 BIN。

## 17. Builder 与 `set_time_position()` 的方案比较

| 方案 | 评价 |
|---|---|
| A：Builder 生成基础 BIN，再调用 `set_time_position()` | 架构边界正确，避免两套字段逻辑；但当前模板 offset 0=`02`，暂不能直接执行 |
| B：Builder 接受 `TimePosition` | 当前证据不足，容易把 `02` 误解释为 `00/01`；不推荐第一版 |

推荐方案 A 的边界，但分两步落地：Stage 8B-1 先精确迁移 Builder 并保持模板头；后续只有在
取得兼容模板/字段证据后，应用现有 `set_time_position()`。不得在 Builder 内写 offset 0。

## 18. CLI 设计（未实现）

基于真实能力，建议第一版为：

```powershell
python -m ultra3_editor build-static-diy `
  --image "<PNG 或 JPEG>" `
  --template "<351617-byte verified template>" `
  --output "<output.bin>" `
  --json "<build.json>" `
  --report "<build.md>"
```

第一版不提供：

- `--thumbnail`：冻结实现没有独立缩略图输入。
- `--time-position`：offset 0 语义不兼容，尚未验证。
- `--wire-profile`、`--quantize`、`--resample`：exact 范围固定。
- `--force`：不得覆盖。

若以后公开已实现但未真机分级的 fit/mode，应在结果中明确 `CODE SUPPORTED` 与
`DEVICE VERIFIED` 的差异。

## 19. 审计脚本和产物

新增：

- `scripts/audit_stage8b0_builder.py`
- `artifacts/stage8b0_builder_audit/builder_file_manifest.json`
- `artifacts/stage8b0_builder_audit/frozen_zip_manifest.json`
- `artifacts/stage8b0_builder_audit/reproduction_results.json`

脚本只枚举/哈希、验证外部根清单、只读分析 ZIP、调用冻结 Builder 到仓库外新目录、比较输出
并生成规范化 JSON。manifest 连续生成结果一致；已有审计输出目录时脚本在创建临时复现目录前
拒绝运行。外部根清单解析拒绝绝对路径、`..`、反斜杠路径、重复声明、非法 SHA 和逃逸
baseline 的解析结果。

## 20. 最终保护与回归

| 检查 | 最终结果 |
|---|---|
| Editor | `206 passed`，3.518 秒 |
| Uploader | `126 passed`，1.959 秒 |
| `git diff -- uploader` | 无输出 |
| `git diff -- editor/src/ultra3_editor/time_position.py editor/src/ultra3_editor/gui` | 无输出 |
| Frozen Builder SHA | `94DCDE7A959B3A9F9F5939AC295C341A7D713DCD9EEBF2A95669F2F7C815A807`，不变 |
| Frozen ZIP SHA | `3581B0FA3D8E0B4BB952848CC45492B157DFFF4B125D57C93611FC89BF711231`，不变 |
| `git diff --check` | 无错误 |

Builder 复现和审计工作负载的外部调用：Bleak initialization 0、BLE scan 0、BLE connect 0、
FF02 writes 0、adb 0、Frida 0、Uploader calls 0、网络请求 0、真实上传 0。开始前另执行了任务明确
要求的 `git fetch origin` 一次，仅用于 Git 一致性审计，不属于 Builder 执行；未隐瞒为总网络
活动 0。

## 21. 未实现与适用范围

本阶段没有实现公共 Builder、生产测试、GUI 图片导入、独立缩略图、RGB565 GUI 逻辑、
时间位置 Builder 参数、上传或 Stage 8B-1。

当前审计结论限定于：GreenLion、ULTRA 3、NJ-LEJ-2.1.7、351617 字节模板、主图
`320×384`、缩略图 `210×252`、冻结 v0.2.4 exact 实现及已记录 Pillow 环境。物理屏幕几何、
可见区域、其他固件和其他图片容器保持 `UNKNOWN`。
