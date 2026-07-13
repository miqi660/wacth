# Stage 7B-1 时间位置编辑记录

- status: `COMPLETE`
- feature: `set-time-position`
- container: `greenlion-static`
- scope: `GreenLion Static DIY / NJ-LEJ-2.1.7 / 351617-byte reconstructed BIN`
- input: `C:\Users\Administrator\Desktop\wacth\editor\samples\stage7a2_diy_root_capture\A0_repeat_1\reconstructed.bin`
- input size: `351617`
- input SHA-256 before: `9305529D6C644C757F6B193671B84153F0ADEBE385E7B3B30552E9BC23513635`
- input SHA-256 after: `9305529D6C644C757F6B193671B84153F0ADEBE385E7B3B30552E9BC23513635`
- input unchanged: `true`
- detected input position: `top`
- requested position: `bottom`
- output position: `bottom`
- output: `C:\Users\Administrator\Desktop\wacth\editor\artifacts\stage7b1_time_position\top_to_bottom.bin`
- output size: `351617`
- output SHA-256: `3B8302F6746AB2B78FA48599328DB7907788FA322D18ADF297280C8A5D3370C0`
- field: offset `0x00000000`, width `1`
- before/after: `00` -> `01`
- changed byte count: `1`
- changed offsets: `[0]`
- unchanged byte count: `351616`
- output revalidated: `true`
- validation passed: `true`
- exact golden match: `true`
- golden target SHA-256: `3B8302F6746AB2B78FA48599328DB7907788FA322D18ADF297280C8A5D3370C0`

## 安全边界

- BLE: `0`
- adb: `0`
- Frida: `0`
- uploader: `0`
- 上传：未执行
- GUI 编辑：未接入
- Builder：未实现、未调用
- 其他组件：未实现
- 输入文件：只读且 SHA-256 复核一致
