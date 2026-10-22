"""Ponto de entrada do MacPronto.

macpronto            abre a interface
macpronto --engine   modo worker (uso interno, ver macpronto.engine)
macpronto --debug    abre a interface com registros detalhados e DevTools
"""

from __future__ import annotations

import sys


def main() -> int:
    if "--engine" in sys.argv:
        from macpronto.engine.worker import main as worker_main

        return worker_main()

    from macpronto.app import run

    return run(debug="--debug" in sys.argv)


if __name__ == "__main__":
    sys.exit(main())
