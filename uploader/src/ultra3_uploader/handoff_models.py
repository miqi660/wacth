from dataclasses import dataclass


@dataclass(frozen=True)
class HandoffExternalUsage:
    """离线验证的零副作用统计。"""

    bleak_initializations: int = 0
    ble_scans: int = 0
    ble_connections: int = 0
    ff02_writes: int = 0
    ff03_notifications: int = 0
    adb: int = 0
    frida: int = 0
    network_requests: int = 0
    payloads_generated: int = 0
    c9_frames_generated: int = 0
    real_uploads: int = 0
