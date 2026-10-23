"""Ponto de entrada do MacPronto.

macpronto            abre a interface
macpronto --engine   modo worker (uso interno, ver macpronto.engine)
macpronto --debug    abre a interface com registros detalhados e DevTools
macpronto --selftest [arquivo.json] [--full]   autoteste sem janela (ver macpronto.selftest)
"""

from __future__ import annotations

import sys


def main() -> int:
    from macpronto import paths

    if paths.is_frozen():
        # Garante no executável os módulos que o código de terceiros importa em tempo de execução
        from macpronto import _runtime_imports  # noqa: F401

    if "--engine" in sys.argv:
        from macpronto.engine.worker import main as worker_main

        return worker_main()

    if "--selftest" in sys.argv:
        from pathlib import Path

        from macpronto.selftest import run as selftest

        position = sys.argv.index("--selftest")
        target = (
            sys.argv[position + 1]
            if len(sys.argv) > position + 1 and not sys.argv[position + 1].startswith("--")
            else None
        )
        return selftest(Path(target) if target else None)

    from macpronto.app import run

    return run(debug="--debug" in sys.argv)


if __name__ == "__main__":
    sys.exit(main())
