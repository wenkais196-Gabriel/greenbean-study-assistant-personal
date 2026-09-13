"""
一键启动前后端（demo 脚本）。

用法：
    python scripts/run_demo.py            # 启动后端 + 前端
    python scripts/run_demo.py --check    # 只打印要执行的命令，不真正启动

- 后端：`backend-python/.venv` 里的解释器跑 `uvicorn app.main:app` @ http://127.0.0.1:8000
- 前端：`npm run dev` @ http://localhost:5173（vite.config.ts 固定 5173）
- Ctrl+C 同时关闭两个子进程；不引入任何新依赖。
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend-python"

BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000
FRONTEND_URL = "http://localhost:5173"


def _backend_python() -> str:
    for candidate in (
        BACKEND_ROOT / ".venv" / "Scripts" / "python.exe",  # Windows
        BACKEND_ROOT / ".venv" / "bin" / "python",          # macOS / Linux
    ):
        if candidate.exists():
            return str(candidate)
    return sys.executable


def _backend_command() -> list[str]:
    return [
        _backend_python(),
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        BACKEND_HOST,
        "--port",
        str(BACKEND_PORT),
    ]


def _frontend_command() -> list[str]:
    return ["npm", "run", "dev"]


def _spawn_frontend() -> subprocess.Popen:
    if os.name == "nt":  # Windows 需要 shell 才能解析 npm.cmd
        return subprocess.Popen("npm run dev", cwd=str(REPO_ROOT), shell=True)
    return subprocess.Popen(_frontend_command(), cwd=str(REPO_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="一键启动 GreenBean 前后端")
    parser.add_argument("--check", action="store_true", help="只打印要执行的命令，不真正启动")
    args = parser.parse_args()

    if args.check:
        print("[run_demo] 后端命令：", " ".join(_backend_command()), f"(cwd={BACKEND_ROOT})")
        print("[run_demo] 前端命令：", " ".join(_frontend_command()), f"(cwd={REPO_ROOT})")
        return 0

    backend = subprocess.Popen(_backend_command(), cwd=str(BACKEND_ROOT))
    frontend = _spawn_frontend()
    print("GreenBean 演示已启动：")
    print(f"  前端  {FRONTEND_URL}")
    print(
        f"  后端  http://{BACKEND_HOST}:{BACKEND_PORT}"
        f"（API 文档 http://{BACKEND_HOST}:{BACKEND_PORT}/docs）"
    )
    print("按 Ctrl+C 退出。")
    try:
        while True:
            time.sleep(1)
            if backend.poll() is not None and frontend.poll() is not None:
                print("[run_demo] 前后端进程都已退出。")
                break
    except KeyboardInterrupt:
        pass
    finally:
        for process in (frontend, backend):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        print("[run_demo] 已停止。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
