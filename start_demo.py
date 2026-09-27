from __future__ import annotations

import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
STREAMLIT_URL = "http://localhost:8501"


def main() -> None:
    """一键启动 Demo 所需服务并打开 Streamlit 页面。

    参数：无。
    返回值：无。函数会阻塞等待 Streamlit 进程退出。
    """
    if os.getenv("DEMO_USE_DOCKER_MYSQL", "0") == "1":
        subprocess.run(["docker", "compose", "up", "-d", "mysql"], cwd=ROOT, check=True)
    else:
        print("Using local MySQL at the configured host and port.")
    children: list[subprocess.Popen] = []
    commands = [
        [sys.executable, "mcp_server.py"],
        [sys.executable, "agent_server.py"],
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "app.py",
            "--server.headless",
            "true",
        ],
    ]
    try:
        time.sleep(5)
        for command in commands:
            process = subprocess.Popen(command, cwd=ROOT)
            children.append(process)
            time.sleep(2)
            if process.poll() is not None:
                command_text = " ".join(command)
                raise RuntimeError(
                    f"服务启动失败，退出码 {process.returncode}: {command_text}"
                )
        print(f"Sales assistant demo: {STREAMLIT_URL}")
        webbrowser.open(STREAMLIT_URL)
        children[-1].wait()
    except KeyboardInterrupt:
        pass
    finally:
        for process in reversed(children):
            if process.poll() is None:
                process.terminate()


if __name__ == "__main__":
    main()
