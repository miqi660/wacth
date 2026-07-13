# Ultra3 仓库扁平化报告

日期：2026-07-13

## 结果

仓库内容已从 `Ultra3-Reverse_Updated_2026-07-13/` 移至 Git 根目录。根目录现在直接包含 `archives/`、`editor/`、`uploader/`、`.gitignore` 和 `README.md`；旧包装目录已不存在。

未进入 Stage 7B-1，未执行 BLE、ADB、Frida 或真实上传操作。

## 开始前审计

- 分支：`main`
- 远程：`https://github.com/miqi660/wacth.git`
- 原 HEAD：`bf60da56875e54458526c8868fadd824e9aabfca`
- 原 `origin/main`：`bf60da56875e54458526c8868fadd824e9aabfca`
- 开始前工作区：干净
- 现有标签：11 个，未修改、删除或重建
- 根目标冲突：0
- 未跟踪或 ignored 项目内容：0

## 结构变化

移动前：

```text
wacth/
└─ Ultra3-Reverse_Updated_2026-07-13/
   ├─ archives/
   ├─ editor/
   ├─ uploader/
   └─ .gitignore
```

移动后：

```text
wacth/
├─ archives/
├─ editor/
├─ uploader/
├─ .gitignore
├─ README.md
└─ REPOSITORY_FLATTEN_REPORT_2026-07-13.md
```

## 文件清单与 Git rename

- 迁移 tracked 文件：156
- 移动前文件数：156
- 移动后文件数：156
- 移动前总大小：16,847,674 字节
- 移动后总大小：16,847,674 字节
- 移动前归一化内容清单 SHA-256：`D414ABD96ECD723A1735B9BDE4DF2BFC7BAC93FD1B19889C138C5AE520F58270`
- 移动后归一化内容清单 SHA-256：`D414ABD96ECD723A1735B9BDE4DF2BFC7BAC93FD1B19889C138C5AE520F58270`
- `git diff --cached --summary` rename：156
- 内容改写：0 insertions，0 deletions（仅迁移阶段）

`archives`、`uploader` 和 `.gitignore` 直接使用 `git mv`。`editor` 顶层目录因 Windows 句柄无法整体重命名，剩余 tracked 文件仍逐项使用 `git mv` 移动；没有采用复制后删除。

## 旧包装空目录清理

逐文件移动后旧路径仅剩 14 个物理空目录。删除前确认：

- 文件：0
- tracked：0
- untracked：0
- ignored：0
- symlink、junction、reparse point：0

清理严格按路径深度由深到浅执行，每次只使用不带 `-Recurse`、不带 `-Force` 的 `Remove-Item -LiteralPath`，并在每次删除前再次确认当前目录为空。13 个子目录和最外层包装目录均已删除，仓库根目录未被纳入删除清单。

## 活动路径修订

- 新建根 `README.md`，提供项目导航、验证范围和测试命令。
- `uploader/README.md` 的安装目录由 `cd .\Ultra3-Reverse_Updated_2026-07-13\uploader` 修订为 `cd .\uploader`。
- 源码、测试中的外部 Frozen 归档候选路径继续保留。
- 阶段报告、重组 JSON、JSONL、metadata 和历史绝对路径证据未批量改写。

## 回归测试

| 项目 | 结果 |
| --- | --- |
| Editor | 134 passed |
| Uploader | 126 passed |
| 合计 | 260 passed |

测试使用 `PYTHONDONTWRITEBYTECODE=1` 和 `-p no:cacheprovider`；Editor GUI 测试使用 `QT_QPA_PLATFORM=offscreen`。

## 证据与哈希保护

- `Ultra3_v0.2.4_Frozen_Baseline_2026-07-11.zip`：`3581B0FA3D8E0B4BB952848CC45492B157DFFF4B125D57C93611FC89BF711231`
- `archives/editor/Ultra3_Editor_Stage7A1_Frozen_2026-07-13.zip`：`D5D3A9BB55D245C2AE38D41318C6311EAB57424B603575E9D8B3667D60721D7C`
- 黄金 BCSDIAL：`7B25A833D431ED29622EDF4C102F4B555F1E251D1CEC842D848E8E7DCE2C015D`
- A0_repeat_1 capture：`78734E68052D25FA9E09DD709134B288814A1162F4B3174987B3DD0C4D16C38E`
- A0_repeat_1 reconstructed：`9305529D6C644C757F6B193671B84153F0ADEBE385E7B3B30552E9BC23513635`

Frozen ZIP、BIN、抓包、JSONL、样本和历史报告内容均未修改。Uploader `src/` 内容变化为 0。

## 外部调用统计

- Bleak 初始化：0
- BLE scan：0
- BLE connect：0
- FF02 writes：0
- ADB：0
- Frida：0
- 真实上传：0

## 结论

本次变更仅包含目录扁平化、根 README、扁平化报告和一处必要的当前路径修订。未修改协议实现、测试逻辑、历史标签或冻结证据。
