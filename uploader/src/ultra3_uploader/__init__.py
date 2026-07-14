"""Ultra3 动态 BCSDIAL 离线协议工具。"""

from .handoff import (
    HandoffValidationIssue,
    HandoffValidationStatus,
    UploaderHandoffValidationResult,
    validate_handoff,
)
from .handoff_models import HandoffExternalUsage
from .static_transfer import (
    StaticC9Frame,
    StaticTransferPlan,
    StaticTransferVerification,
    build_static_transfer_plan,
    inspect_static_plan,
    verify_static_plan,
    verify_static_transfer_frames,
    write_static_transfer_plan,
)

__version__ = "0.3.0"

__all__ = [
    "HandoffExternalUsage",
    "HandoffValidationIssue",
    "HandoffValidationStatus",
    "UploaderHandoffValidationResult",
    "StaticC9Frame",
    "StaticTransferPlan",
    "StaticTransferVerification",
    "build_static_transfer_plan",
    "inspect_static_plan",
    "validate_handoff",
    "verify_static_plan",
    "verify_static_transfer_frames",
    "write_static_transfer_plan",
]
