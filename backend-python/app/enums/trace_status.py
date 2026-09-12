from enum import Enum


class TraceStatus(str, Enum):
    """一条 span 的结局（见 docs/specs/us-stage1-trace.md）。"""

    OK = "ok"
    ERROR = "error"
