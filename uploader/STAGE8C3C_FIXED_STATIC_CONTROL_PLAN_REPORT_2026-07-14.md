# Stage 8C-3C — NJLEJ 2.1.7 Fixed Static Control Plan

日期：2026-07-14
状态：**PASS / OFFLINE ONLY**

## 1. 范围与证据

本阶段依据 Stage 8C-3B 两次成功的 root 手机最终 Binder 抓取，实现 NJLEJ 2.1.7 固定 Profile
的 C8/CA 构建、严格解析、完整离线计划和复核。两次证据均为 App 安装 PASS、手表显示 PASS，
且写入统计均为 C8=1、C9=1529、CA=1、sequence `0..1528`。

本阶段没有连接 BLE，没有执行 FF02 写入，没有启用 FF03，也没有运行真实上传。

## 2. 修改文件与职责

| 文件 | 职责 |
|---|---|
| `uploader/src/ultra3_uploader/fixed_static.py` | 固定 Profile、C8/CA exact API、计划构建/复核及独占输出 |
| `uploader/src/ultra3_uploader/errors.py` | 固定 Profile、控制帧、复核和输出的明确异常 |
| `uploader/src/ultra3_uploader/cli.py` | `build-fixed-static-plan` 离线入口 |
| `uploader/src/ultra3_uploader/__init__.py` | 导出新增公共 API |
| `uploader/tests/test_fixed_static.py` | 固定帧、Profile guard、计划顺序、损坏路径与写盘测试 |
| `uploader/tests/test_fixed_static_cli.py` | CLI、输出大小、错误输入和零 BLE 参数测试 |
| `uploader/README.md` | 使用方法与安全边界 |
| `docs/handoff/README.md` | Handoff 与固定控制计划的职责边界 |

## 3. 固定 Profile

`NJLEJ_217_FIXED_STATIC` 仅允许：

- firmware：`NJ-LEJ-2.1.7`
- static container：351617 bytes
- C9 DATA：常规 230 bytes，末帧 177 bytes
- C9 count：1529
- sequence：`0..1528`
- total write count：1531

非 351617-byte 输入、非 1529 C9 或未知 Profile 均明确拒绝。不提供通用
`build_static_c8()` 或 `build_static_ca()`。

## 4. Exact 控制帧

| 帧 | HEX | 长度 |
|---|---|---:|
| C8 | `BCC8020701815D0500F905E2` | 12 |
| CA | `BCCA02010505` | 6 |

C8 解析复核 command、direction、LEN、profile/mode、LE32 size、LE16 count 和现有
`c8_checksum()`。CA 只接受完整 6 字节 exact match；任意字节变化均拒绝。

## 5. 字节流术语与大小

| 层 | 定义 | 大小 |
|---|---|---:|
| `input_image` | 原始 JPG/PNG，仅为 Builder 输入 | 不固定 |
| `static_container` | 表盘 BIN / 所有 C9 DATA 拼接 | 351617 |
| `region_stream` | 每块 DATA+checksum 拼接 | 353146 |
| `c9_frame_stream` | 1529 个完整 C9 帧拼接 | 362320 |
| `full_transfer_stream` | C8+c9_frame_stream+CA | 362338 |

C9 没有复制实现，仍逐帧调用已验证的 `build_c9()`；复核使用现有 `parse_c9()` 和 checksum。

## 6. 完整计划与输出

严格顺序为：

`C8 -> C9 seq 0 -> ... -> C9 seq 1528 -> CA`

总帧数为 1531。CLI 独占创建以下文件，不覆盖已有路径：

| 文件 | 大小 |
|---|---:|
| `c8.bin` | 12 |
| `c9_frames.bin` | 362320 |
| `ca.bin` | 6 |
| `full_transfer_stream.bin` | 362338 |
| `manifest.json` | 确定性元数据 |

Manifest 明确记录 `offline_only=true`、`ble_supported=false`、固定证据范围及四层字节流，
不含设备地址或已发送声明。

## 7. 测试结果

- 修改前 Uploader：231 项通过。
- 新增固定 Profile 测试：45 项通过。
- 修改后 Uploader：276 项通过。
- Editor 回归：288 项通过。
- 旧 Stage 8C-3A 测试：全部保留并通过。
- `git diff --check`：PASS。

异常测试覆盖 C8 size/count/checksum/字段损坏、CA 每个单字节损坏、错误 static container 大小、
C9 缺失/重复/乱序/LEN/checksum 损坏、输出已存在和 CLI 错误输入。

## 8. 外部调用与安全统计

- Bleak initialization：0
- BLE scan：0
- BLE connect：0
- FF02 writes：0
- FF03 notifications：0
- adb：0
- Frida：0
- network：0
- real uploads：0

Stage 8C-3B raw Binder 日志未加入 Git，本阶段未修改 Builder、已有 C9/checksum 或 Editor 源码。

## 9. 尚未证明与下一阶段

两组 Binder 样本具有相同 static container size 和 C9 count，因此 C8 字段在可变大小下的通用
生成语义仍未证明；CA 末尾 `05` 的完整语义也仍未知。本阶段不支持可变大小或其他固件。

下一阶段才可进入 BLE transport dry-run；本报告不授权扫描、连接、通知订阅或真实写入。

## 10. Git 状态

按阶段要求未 commit、未创建 tag、未 push，等待人工验收。
