"""Ultra3 动态 BCSDIAL 离线协议工具。"""

from .handoff import (
    HandoffValidationIssue,
    HandoffValidationStatus,
    UploaderHandoffValidationResult,
    validate_handoff,
)
from .handoff_models import HandoffExternalUsage

__version__ = "0.3.0"

__all__ = [
    "HandoffExternalUsage",
    "HandoffValidationIssue",
    "HandoffValidationStatus",
    "UploaderHandoffValidationResult",
    "validate_handoff",
]
