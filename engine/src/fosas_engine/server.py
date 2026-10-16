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

--public-password (or FOSAS_PUBLIC_PASSWORD) is the one exception to
"the tailnet is the only real access control": set it before exposing
the engine beyond the tailnet (e.g. via "tailscale funnel", which stays
compatible with --host 127.0.0.1 - Funnel proxies into the local port,
it does not need the app itself to bind anywhere but loopback), see
fosas_engine.app's module docstring and docs/RISKS.md R23.
"""

from __future__ import annotations

import argparse
import os
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
    parser.add_argument(
        "--public-password",
        type=str,
        default=None,
        help="Gate '/', '/viewer', '/app.js' and the docs routes behind a "
        "/login session cookie instead of serving them (and the real bearer "
        "token they embed) to anyone who can reach the port - required "
        "before exposing the engine beyond the tailnet, e.g. via "
        "'tailscale funnel', see docs/RISKS.md R23. Prefer the "
        "FOSAS_PUBLIC_PASSWORD environment variable over this flag: a "
        "command-line argument is visible in the shell history and process "
        "list, which an env var is not. Not set by default (no change from "
        "before).",
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
    public_password = args.public_password or os.environ.get("FOSAS_PUBLIC_PASSWORD")
    settings = Settings(token=token, work_root=args.work_root, public_password=public_password)
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
    if public_password is not None:
        print("Login gate is ACTIVE: '/', '/viewer', '/app.js' and the docs routes now require the public password below (POST to /login), not just network access.", flush=True)
        print(f"Public password: {public_password}", flush=True)

    uvicorn.run(app, host=args.host, port=port, log_level="info")


if __name__ == "__main__":
    main()
