"""Compartilha o guia com o celular pela rede local, com um QR code.

O QR code abre uma página só com os botões para baixar os PDFs (guia, Bem-vindo ao Mac e
Ajuda para IA): depois que o computador é desligado ou formatado, este endereço deixa de
existir, e o que fica é o que a pessoa baixou. O servidor só entrega esses arquivos, só
para leitura, e desliga sozinho depois de 30 minutos.
"""

from __future__ import annotations

import http.server
import logging
import socket
import threading
from functools import partial
from pathlib import Path

import segno

log = logging.getLogger(__name__)

ALLOWED = {
    "/Guia.pdf": "Guia.pdf",
    "/Bem-vindo-ao-Mac.pdf": "Bem-vindo-ao-Mac.pdf",
    "/AJUDA-IA.pdf": "AJUDA-IA.pdf",
    # Sem o Edge não há PDF: a página de downloads oferece as versões em HTML e texto
    "/Guia.html": "Guia.html",
    "/Bem-vindo-ao-Mac.html": "Bem-vindo-ao-Mac.html",
    "/AJUDA-IA.md": "AJUDA-IA.md",
}
TIMEOUT_SECONDS = 30 * 60


class _GuideHandler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".md": "text/plain; charset=utf-8"}

    def __init__(self, *args, page: bytes = b"", **kwargs) -> None:
        self.page = page  # antes do super(): ele já atende o pedido
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:  # noqa: N802 - nome da API do http.server
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(self.page)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command == "GET":
                self.wfile.write(self.page)
            return
        if path not in ALLOWED or not (Path(self.directory) / ALLOWED[path]).exists():
            self.send_error(404, "Não encontrado")
            return
        self.path = "/" + ALLOWED[path]
        super().do_GET()

    def end_headers(self) -> None:
        # PDF baixa direto para o celular, em vez de só abrir na aba (que se perde com o computador desligado)
        if self.path.endswith(".pdf"):
            self.send_header("Content-Disposition", f'attachment; filename="MacPronto-{self.path.lstrip("/")}"')
        super().end_headers()

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def list_directory(self, path):  # noqa: ANN001 - nunca lista pastas
        self.send_error(404, "Não encontrado")
        return None

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        log.debug("Guia compartilhado: " + format, *args)


def local_ip() -> str:
    """IP desta máquina na rede local (não envia pacotes: o UDP só escolhe a rota)."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.168.0.1", 9))
        return probe.getsockname()[0]
    except OSError:
        return socket.gethostbyname(socket.gethostname())
    finally:
        probe.close()


class GuideShare:
    def __init__(self) -> None:
        self._server: http.server.ThreadingHTTPServer | None = None
        self._timer: threading.Timer | None = None
        self.url: str | None = None

    def start(self, folder: Path) -> dict:
        from macpronto.guide import render

        self.stop()
        page = render.render_downloads(folder).encode("utf-8")
        handler = partial(_GuideHandler, page=page, directory=str(folder))
        server = http.server.ThreadingHTTPServer(("0.0.0.0", 0), handler)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self._server = server
        self._timer = threading.Timer(TIMEOUT_SECONDS, self.stop)
        self._timer.daemon = True
        self._timer.start()
        self.url = f"http://{local_ip()}:{port}/"
        log.info("Guia disponível na rede local em %s", self.url)
        return {"url": self.url, "qr_svg": qr_svg(self.url), "minutes": TIMEOUT_SECONDS // 60}

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            log.info("Compartilhamento do guia encerrado")
        self.url = None


def qr_svg(data: str) -> str:
    qr = segno.make(data, error="m")
    return qr.svg_inline(scale=6, border=2, dark="#111827", light="#ffffff")
