"""CLI entrypoint for the local operations web app."""

from __future__ import annotations

import argparse

import uvicorn

from pipeline.web.app import create_app


def main() -> None:
    """Run the operations web app on localhost by default."""

    parser = argparse.ArgumentParser(description="Run the MoneyTrail operations web app.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Defaults to localhost.")
    parser.add_argument("--port", type=int, default=8787, help="Bind port. Defaults to 8787.")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for local development.")
    args = parser.parse_args()

    if args.port < 1 or args.port > 65535:
        raise SystemExit(f"--port must be between 1 and 65535: {args.port}")

    uvicorn.run(create_app(), host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
