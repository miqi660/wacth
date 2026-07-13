# Ultra3 C9 Reconstruction Report

- Status: `COMPLETE`
- Container: `greenlion-static`
- Container validation passed: `True`
- Source capture: `C:\Users\Administrator\Desktop\wacth\Ultra3-Reverse_Updated_2026-07-13\editor\samples\stage7a2_diy_root_capture\A0_repeat_2\capture_raw.log`
- Source SHA-256: `3BD2F45CC39A413DE8EFB6A2A2979EFEE697277B177CBCB459CBCFC2015470F8`
- Parsing format: `frida`
- Upload sessions: `1`
- Selected session: `0`

## C8 / C9 validation

- C8: `BCC8020701815D0500F905E2`
- Mode: `1`
- Declared file size: `351617`
- Declared packet count: `1529`
- Actual packet count: `1529`
- Sequence: `0..1528`
- Checksum passed: `1529`
- Checksum failed: `0`
- Missing sequences: `[]`
- Duplicate sequences: `[]`
- Out of order: `False`

## Reconstructed container

- Output: `C:\Users\Administrator\Desktop\wacth\Ultra3-Reverse_Updated_2026-07-13\editor\samples\stage7a2_diy_root_capture\A0_repeat_2\reconstructed.bin`
- Size: `351617`
- SHA-256: `9305529D6C644C757F6B193671B84153F0ADEBE385E7B3B30552E9BC23513635`
- Raw DATA size: `351617`
- Raw DATA SHA-256: `9305529D6C644C757F6B193671B84153F0ADEBE385E7B3B30552E9BC23513635`
- Transformation: `none`
- First packet DATA length: `230`
- Last packet DATA length: `177`
- Header requirement: `None`
- Footer requirement: `None`
- Header check: `NOT_REQUIRED`
- Footer check: `NOT_REQUIRED`
- Header observed HEX: `000000FFFFFF00`
- Footer observed HEX: `00000000`

## Capture parsing statistics

- Total lines: `1583`
- Recognized records: `1575`
- FF02 writes: `1531`
- FF03 notifications: `44`
- Unrecognized lines: `8`
- Non-target frames: `0`
- C8/C9/CA: `1/1529/1`

## Errors

- None

## Safety and unknown behavior

- Real BLE usage: `0`（Bleak/scan/connect/FF02 write 均为 0）。
- 输入抓包和重组 BIN 未被修改；工具只按原始 C9 DATA 顺序输出。
- 未实现自动排序、去重、补零、丢包修复、BIN patch 或 GUI。
- 尚未执行 A0_repeat_1/A0_repeat_2 真实 DIY 重复样本采集。
- 尚未确认 DIY 时间位置、颜色字段或生成结果的确定性。
