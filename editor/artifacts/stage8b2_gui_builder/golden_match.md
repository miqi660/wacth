# GreenLion Static DIY 构建记录

- status: `COMPLETE`
- builder version: `0.2.4-greenlion-exact`
- container: `greenlion-static`
- firmware scope: `NJ-LEJ-2.1.7`
- image: `1.JPG`
- image format: `JPEG`
- image SHA-256: `9FDBB04E9DD910296B44BECB98C25A0C988A4B1B98EC0DAE12A0E831BC747CB4`
- template: `official_calibration_351617.bin`
- template SHA-256: `5D04DE76C94DA9D7F7069AF3E6038E1575D3B42E5E009EAD590CE4DD33F5E1CC`
- template unchanged: `true`
- template header preserved: `true`
- template offset 0: `02`
- output: `golden_match.bin`
- output size: `351617`
- output SHA-256: `44B4893ACF6244119DE655B32C1CE760048F3128A24489B49FF24F7BB60FA664`
- output revalidated: `true`
- main resource: `320x384`
- thumbnail resource: `210x252`
- fit: `cover`
- resample: `bilinear`
- quantize: `truncate`
- wire profile: `greenlion-next-high`
- determinism status: `not_evaluated`
- repeated build SHA-256: `NOT_EVALUATED`
- golden status: `match`
- exact golden match: `true`
- golden target SHA-256: `44B4893ACF6244119DE655B32C1CE760048F3128A24489B49FF24F7BB60FA664`

## 安全边界

- 外部设备调用：`0`
- 网络请求：`0`
- 真实上传：`0`
- GUI：未接入
- 时间位置编辑：未调用
- 输入图片与模板：只读并复核 SHA-256
