# Stage 8C-2 — GreenLion Static Real-Device Capture Evidence

**Result: PASS**

## Scope

This stage records a successful real-device static watchface transfer using
GreenLion on an Ultra3 running firmware NJ-LEJ-2.1.7.

The public report contains only sanitized technical conclusions and hashes.
Raw HCI, bugreport, Bluetooth addresses, complete binaries, and device-specific
logs remain private local evidence.

## Frozen input

| Item | Value |
|---|---|
| Source watchface size | 351617 bytes |
| Source SHA-256 | `44b4893acf6244119de655b32c1ce760048f3128a24489b49ff24f7bb60fa664` |
| C9 payload size | 353146 bytes |
| C9 payload SHA-256 | `19c1b72da080c5f23d0978ff7c93dbd10f8e07d6eaaeff4e3c4d08608e31bcf5` |

## BLE transport evidence

| Item | Result |
|---|---|
| Service | `000001ff-3c17-d293-8e48-14fe2e4da212` |
| APP → watch characteristic | FF02 |
| Watch → APP characteristic | FF03 |
| ATT handle | `0x0062` |
| ATT operation | Write Command / `0x52` |
| MTU | 247 |
| C9 prefix | `BC C9 02` |
| CA observed after C9 | Yes |

## Final Binder-layer capture

The final byte stream entering Android's Bluetooth Binder layer was captured at:

`android.bluetooth.IBluetoothGatt$Stub$Proxy.writeCharacteristic`

| Verification | Result |
|---|---:|
| C9 writes | 1529 |
| Unique sequence numbers | 1529 |
| Sequence range | 0..1528 |
| Missing packets | 0 |
| Duplicate packets | 0 |
| Differing duplicate packets | 0 |
| Checksum failures | 0 |
| Reconstructed size | 353146 bytes |
| Exact match with expected payload | True |
| First differing offset | -1 |
| Differing bytes | 0 |

The reconstructed Binder-layer stream has SHA-256:

`19c1b72da080c5f23d0978ff7c93dbd10f8e07d6eaaeff4e3c4d08608e31bcf5`

This exactly matches the frozen expected C9 payload.

## Packet sizing

- C9 sequences 0..1527: 237-byte Binder frame, containing a 231-byte reconstructed region.
- C9 sequence 1528: 184-byte Binder frame, containing a 178-byte reconstructed region.
- Reconstruction:

```text
1528 × 231 + 178 = 353146
```

## HCI confirmation

The extracted standard btsnoop capture confirmed:

- 3821 total records.
- 2607 ACL records.
- 1600 FF02 Write Commands.
- 1529 C9 markers.
- C9 packets were sent with ATT opcode `0x52` to handle `0x0062`.
- CA was observed after the final C9 transfer.

## Real-device result

- GreenLion reported upload success.
- The Ultra3 displayed the expected Golden static watchface.
- Firmware tested: NJ-LEJ-2.1.7.

## Publication policy

The following evidence is intentionally excluded from the public repository:

- Raw HCI captures.
- Android bugreports.
- Bluetooth device addresses.
- Complete proprietary application logs.
- Complete watchface binaries and reconstructed payloads.
- Device-identifying information.

Those files remain in the private local evidence archive.
