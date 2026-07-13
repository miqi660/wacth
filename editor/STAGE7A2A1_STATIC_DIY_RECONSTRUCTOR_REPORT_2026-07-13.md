# Ultra3 Stage 7A-2A.1 GreenLion 静态 DIY C9 重组报告

## 结论

Stage 7A-2A.1 已按真实抓包证据修正并完成。`E8` 被保留为 C9 `LEN` 字段，不再被解释为 DATA 前缀；重组过程对全部 C9 DATA 只做原序拼接，`transformation = none`。

现有 A0_repeat_1 抓包已离线重组成功：状态 `COMPLETE`，输出大小 `351617`，SHA-256 为 `9305529D6C644C757F6B193671B84153F0ADEBE385E7B3B30552E9BC23513635`。

## 实现范围

- 为现有公共 C8/C9 重组器增加 `ContainerKind.BCSDIAL` 与 `ContainerKind.GREENLION_STATIC`。
- `reconstruct-c9` 默认仍使用 `bcsdial`，继续要求 `BCSDIAL` 头和 `BCBC` 尾。
- `greenlion-static` 仅将头尾检查设为 `NOT_REQUIRED`，仍严格执行 C8/C9、LEN、checksum、sequence、包数和声明大小校验。
- `reconstruct-static-diy` 只是同一 CLI 和 `reconstruct_capture()` 的静态容器别名，没有第二套解析或重组循环。
- 未实现 DATA 字节删除、自动修复、补头、补尾、排序、去重或补零。

## 文件职责

| 文件 | 职责 |
|---|---|
| `src/ultra3_editor/models.py` | 定义容器类型、头尾检查状态及重组结果字段。 |
| `src/ultra3_editor/reconstructor.py` | 维持唯一 C8/C9 会话解析与 DATA 拼接路径，在末端应用容器校验策略。 |
| `src/ultra3_editor/reconstruction_reports.py` | 输出容器、头尾要求、原始 DATA、零变换和首末包 DATA 长度。 |
| `src/ultra3_editor/cli.py` | 增加 `--container` 和共享底层函数的 `reconstruct-static-diy` 别名。 |
| `tests/test_static_container.py` | 覆盖静态容器成功、错误路径、CLI、实样本哈希和输入不变性。 |
| `README.md` | 记录两种容器的命令和校验边界。 |

## 唯一重组流程

1. 只读抓包并提取 App→手表 FF02 记录。
2. 定位独立 C8/C9 会话。
3. 校验 C8 结构和 checksum。
4. 使用现有 `parse_c9()` 校验帧结构、`LEN = 2-byte sequence + DATA` 和 checksum。
5. 按抓包原始顺序校验 sequence 连续，不排序、不去重、不补包。
6. 原序拼接每个 C9 的完整 DATA，零字节变换。
7. 校验拼接大小严格等于 C8 declared size。
8. 最后按 container 执行文件级策略：`bcsdial` 检查头尾，`greenlion-static` 将头尾标记为 `NOT_REQUIRED`。

## E8/B3 逐包结论

| 帧 | 完整帧大小 | LEN | sequence 字节 | DATA 大小 | checksum 字节 |
|---|---:|---:|---:|---:|---:|
| 前 1528 帧 | 237 | `E8` | 2 | 230 | 1 |
| 最后一帧 | 184 | `B3` | 2 | 177 | 1 |

- `0xE8 = 2 + 230`。
- `0xB3 = 2 + 177`。
- DATA 首字节为 `E8`：`0 / 1529`。
- DATA 总大小：`1528 × 230 + 177 = 351617`。
- raw DATA 与 reconstructed 完全相同，不生成或需要第二份重复 raw payload 文件。

## 离线测试

- Editor：`96 passed in 1.04s`，原有 84 项全部保留，新增 12 项测试（参数化后覆盖 15 条执行路径）。
- Uploader：`126 passed in 1.48s`，未修改 uploader 源码或状态机。
- 覆盖范围：默认 BCSDIAL 头尾策略、动态黄金回归、静态头尾免检、完整 DATA 保留、E8/B3 LEN、声明大小、缺包、重复、乱序、checksum、LEN、独占输出、共享底层函数、实样本 SHA、输入抓包不变和零 BLE 源码约束。

## A0_repeat_1 离线验证

执行命令：

```powershell
python -m ultra3_editor reconstruct-c9 `
  ".\samples\stage7a2_diy_root_capture\A0_repeat_1\capture_raw.log" `
  --format auto `
  --container greenlion-static `
  --output ".\samples\stage7a2_diy_root_capture\A0_repeat_1\reconstructed.bin" `
  --json ".\samples\stage7a2_diy_root_capture\A0_repeat_1\reconstruction.json" `
  --report ".\samples\stage7a2_diy_root_capture\A0_repeat_1\reconstruction.md"
```

结果：

| 项目 | 结果 |
|---|---|
| Status | `COMPLETE` |
| Container | `greenlion-static` |
| C8 | `BCC8020701815D0500F905E2` |
| C8 checksum | 通过 |
| Declared/actual packet count | `1529 / 1529` |
| Sequence | `0..1528` |
| C9 checksum | `1529 / 1529` |
| First/last DATA size | `230 / 177` |
| Missing/duplicate/out of order | `[] / [] / false` |
| Raw DATA size | `351617` |
| Reconstructed size | `351617` |
| Transformation | `none` |
| Header/footer check | `NOT_REQUIRED / NOT_REQUIRED` |
| Raw/Reconstructed SHA-256 | `9305529D6C644C757F6B193671B84153F0ADEBE385E7B3B30552E9BC23513635` |

## 证据文件

| 文件 | 大小 | SHA-256 |
|---|---:|---|
| `capture_raw.log` | 1234849 | `78734E68052D25FA9E09DD709134B288814A1162F4B3174987B3DD0C4D16C38E` |
| `reconstructed.bin` | 351617 | `9305529D6C644C757F6B193671B84153F0ADEBE385E7B3B30552E9BC23513635` |
| `reconstruction.json` | 2418 | `C53CA9C650F7A71F8E609C535B7705AF3658A6C903E51919CD634C0567869E4D` |
| `reconstruction.md` | 2074 | `85BC1862A299BED83DE4BED8229C2915153C6F5100C27B1C3A38514E8970C8B2` |

原 BCSDIAL 拒绝结果已原样保留为：

- `reconstruction_bcsdial_rejected.json`，SHA-256 `0CCBEF1660D6D19E22BFC26BE21063DC265131C6163A55E93BB5A154B2B84E8D`。
- `reconstruction_bcsdial_rejected.md`，SHA-256 `ABCE0EE362172EE54B73637C20D6AE1D50EE231244DE38C92F943E1EFD3EE03B`。

它们证明同一会话已正确拼接到 351617 字节，但默认 BCSDIAL 容器策略不适用于静态 DIY 文件。

## 安全与边界

- `capture_raw.log` 执行前后 SHA-256 保持 `78734E68052D25FA9E09DD709134B288814A1162F4B3174987B3DD0C4D16C38E`。
- Bleak 初始化：`0`。
- BLE scan：`0`。
- BLE connect：`0`。
- FF02 writes：`0`。
- 未采集 A0_repeat_2，未执行上传，未编辑 BIN，未开发 GUI。
