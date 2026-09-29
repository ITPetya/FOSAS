"""Local server entry point: random token, random free port, 127.0.0.1
only (see docs/ARCHITECTURE.md). Prints the URL and token to stdout so a
human (or a wrapping process, see the future start-exe) can pick them up;
nothing is written to a file, the token only exists for this process's
lifetime.
"""

from __future__ import annotations

import argparse
import secrets
import socket
from pathlib import Path

import uvicorn

from fosas_engine.app import create_app
from fosas_engine.settings import Settings


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the FOSAS engine locally.")
    parser.add_argument("--port", type=int, default=None, help="Fixed port (default: pick a free one)")
    parser.add_argument("--work-root", type=Path, default=Path.home() / ".fosas" / "cases")
    args = parser.parse_args()

    token = secrets.token_urlsafe(32)
    port = args.port or _find_free_port()
    settings = Settings(token=token, work_root=args.work_root)
    app = create_app(settings)

    print(f"FOSAS engine starting on http://127.0.0.1:{port}")
    print(f"Token: {token}")
    print(f"Interactive docs (send the token as 'Authorization: Bearer <token>'): http://127.0.0.1:{port}/docs")

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
