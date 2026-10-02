"""Local server entry point: random token, random free port, 127.0.0.1
only by default (see docs/ARCHITECTURE.md). Prints the URL and token to
stdout so a human (or a wrapping process, see the future start-exe) can
pick them up; nothing is written to a file, the token only exists for
this process's lifetime.

--host lets a deployment bind somewhere reachable from more than just
the same machine, e.g. a Tailscale interface's own IP (see
docs/ARCHITECTURE.md, "Erreichbarkeit ueber Tailscale"): pass that IP
explicitly rather than 0.0.0.0, so the engine is provably unreachable
from anything but the tailnet, independent of and not relying on any
separate firewall/security-group configuration getting it right.
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
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Interface to bind. Default is loopback-only; pass a specific "
        "reachable IP (e.g. a Tailscale interface's own address) to make "
        "the engine reachable from other devices. Never pass 0.0.0.0.",
    )
    args = parser.parse_args()
    if args.host in ("0.0.0.0", "::"):
        # The help text already says not to do this; enforcing it too,
        # not just documenting it, since this is the one flag that can
        # turn a loopback/tailnet-only, bearer-token-only, no-TLS engine
        # into one reachable from the public internet on every interface.
        parser.error(f"--host {args.host} would bind every interface, including the public one. Pass a specific reachable IP instead.")

    token = secrets.token_urlsafe(32)
    port = args.port or _find_free_port()
    settings = Settings(token=token, work_root=args.work_root)
    app = create_app(settings)

    # flush=True: stdout is fully buffered (not line-buffered) when it is
    # not a terminal, e.g. when redirected to a log file. Without an
    # explicit flush here, a reader tailing that file would not see the
    # token until enough other output accumulated to trigger a flush,
    # observed directly while testing this script.
    print(f"FOSAS engine starting on http://{args.host}:{port}", flush=True)
    print(f"Token: {token}", flush=True)
    print(f"Web client: http://{args.host}:{port}/", flush=True)
    print(f"Interactive docs (send the token as 'Authorization: Bearer <token>'): http://{args.host}:{port}/docs", flush=True)

    uvicorn.run(app, host=args.host, port=port, log_level="info")


if __name__ == "__main__":
    main()
