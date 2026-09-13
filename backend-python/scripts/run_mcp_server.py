"""
MCP stdio 入口：`python backend-python/scripts/run_mcp_server.py`

入口放在 scripts/（而不是 app/），是因为启动 stdio 会阻塞进程 —— 不该成为
`app/` 里需要覆盖率的代码路径。业务与协议封装都在 `app/mcp_server.py`。
"""
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.mcp_server import build_server  # noqa: E402

if __name__ == "__main__":
    build_server().run(transport="stdio")
