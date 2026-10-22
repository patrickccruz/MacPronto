"""Janela principal (pywebview + Edge WebView2)."""

from __future__ import annotations

import logging
import os
import sys

from macpronto import APP_NAME, __version__, logs, paths

log = logging.getLogger(__name__)

WINDOW_SIZE = (1240, 820)
MIN_SIZE = (1000, 680)


def _interface_url() -> str:
    dev_url = os.environ.get("MACPRONTO_DEV_URL")
    if dev_url:
        return dev_url
    index = paths.frontend_dir() / "index.html"
    if not index.exists():
        raise SystemExit(
            f"Interface não encontrada em {index}. Rode 'npm run build' na pasta frontend antes de abrir o MacPronto."
        )
    return str(index)


def run(debug: bool = False) -> int:
    logs.setup(debug=debug)
    log.info("%s %s iniciando (Python %s)", APP_NAME, __version__, sys.version.split()[0])

    import webview

    from macpronto.api import Api

    api = Api()
    window = webview.create_window(
        APP_NAME,
        _interface_url(),
        js_api=api,
        width=WINDOW_SIZE[0],
        height=WINDOW_SIZE[1],
        min_size=MIN_SIZE,
        background_color="#0b0b0f",
        text_select=True,
    )
    api._attach(window)  # noqa: SLF001

    def on_closing() -> None:
        api._shutdown()  # noqa: SLF001

    window.events.closing += on_closing

    webview.start(debug=debug, http_server=True, private_mode=True)
    log.info("Janela fechada")
    return 0
