# Ultra3 C9 Reconstruction Report

- Status: `COMPLETE`
- Source capture: `C:\Users\Administrator\Desktop\Ultra3-Reverse_Updated_2026-07-13\captures\2026-07-13_bcsdial_ble_direct\raw\capture_light_v2.log`
- Source SHA-256: `CD85A7AADDCC6BD85E108335DA0E0D63AF9FF24A88C5478F6E0BEA7E9CD6AE7F`
- Parsing format: `frida`
- Upload sessions: `1`
- Selected session: `0`

## C8 / C9 validation

- C8: `BCC80207012C990D00230F05`
- Mode: `1`
- Declared file size: `891180`
- Declared packet count: `3875`
- Actual packet count: `3875`
- Sequence: `0..3874`
- Checksum passed: `3875`
- Checksum failed: `0`
- Missing sequences: `[]`
- Duplicate sequences: `[]`
- Out of order: `False`

## Reconstructed BCSDIAL

- Output: `C:\Users\Administrator\Desktop\wacth\Ultra3-Reverse_Updated_2026-07-13\editor\artifacts\stage7a2a_golden_reconstructed.bin`
- Size: `891180`
- SHA-256: `7B25A833D431ED29622EDF4C102F4B555F1E251D1CEC842D848E8E7DCE2C015D`
- BCSDIAL header: `True`
- BCBC footer: `True`

## Capture parsing statistics

- Total lines: `3926`
- Recognized records: `3916`
- FF02 writes: `3877`
- FF03 notifications: `39`
- Unrecognized lines: `10`
- Non-target frames: `0`
- C8/C9/CA: `1/3875/1`

## Errors

- None

## Safety and unknown behavior

- Real BLE usage: `0`（Bleak/scan/connect/FF02 write 均为 0）。
- 输入抓包和重组 BIN 未被修改；工具只按原始 C9 DATA 顺序输出。
- 未实现自动排序、去重、补零、丢包修复、BIN patch 或 GUI。
- 尚未执行 A0_repeat_1/A0_repeat_2 真实 DIY 重复样本采集。
- 尚未确认 DIY 时间位置、颜色字段或生成结果的确定性。
