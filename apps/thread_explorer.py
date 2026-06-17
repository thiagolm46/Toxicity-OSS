from __future__ import annotations

import argparse
import http.server
import socketserver
import webbrowser
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Abre ou serve o HTML local gerado pelo pipeline de thread disentanglement."
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("data/processed/neo4j_threads"),
        help="Diretorio de saida do pipeline.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Servir reports/ em um servidor HTTP local.",
    )
    parser.add_argument("--port", type=int, default=8501, help="Porta do servidor local.")
    args = parser.parse_args()

    report = args.data / "reports" / "neo4j_threads.html"
    if not report.exists():
        raise SystemExit(f"Relatorio nao encontrado: {report}")

    if not args.serve:
        webbrowser.open(report.resolve().as_uri())
        print(f"Aberto no navegador: {report}")
        return

    reports_dir = (args.data / "reports").resolve()
    handler = lambda *handler_args, **handler_kwargs: http.server.SimpleHTTPRequestHandler(
        *handler_args,
        directory=str(reports_dir),
        **handler_kwargs,
    )
    with socketserver.TCPServer(("127.0.0.1", args.port), handler) as httpd:
        url = f"http://127.0.0.1:{args.port}/neo4j_threads.html"
        print(f"Thread Explorer em {url}")
        webbrowser.open(url)
        httpd.serve_forever()


if __name__ == "__main__":
    main()

