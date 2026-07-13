from ultra3_uploader.ble_transport import TransportKind
from ultra3_uploader.fake_transport import FakeBleTransport


class RealTransportStub(FakeBleTransport):
    """标记为 REAL、但全部行为仅在内存中完成的测试 Transport。"""

    @property
    def kind(self) -> TransportKind:
        return TransportKind.REAL
