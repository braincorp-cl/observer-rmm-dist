"""Punto de entrada: `python -m observer_mcp --http` (servicio) o `--stdio` (local)."""

from __future__ import annotations

import argparse
import sys

from .config import ConfigError, load_settings
from .server import build_http_app, build_server, configure_logging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="observer-mcp")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--http", action="store_true", help="Streamable HTTP stateless en 127.0.0.1:MCP_PORT")
    mode.add_argument("--stdio", action="store_true", help="stdio con OBSERVER_API_KEY del entorno")
    args = parser.parse_args(argv)

    transport = "stdio" if args.stdio else "http"
    try:
        settings = load_settings(transport=transport)
    except ConfigError as exc:
        print(f"observer-mcp: configuración inválida: {exc}", file=sys.stderr)
        return 2

    if transport == "stdio":
        # En stdio, stdout es el canal del protocolo: los logs van a stderr.
        import logging

        logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
        server, _ = build_server(settings)
        server.run("stdio")
        return 0

    import uvicorn

    configure_logging()
    app, _, _ = build_http_app(settings)
    uvicorn.run(app, host="127.0.0.1", port=settings.port, proxy_headers=False, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
