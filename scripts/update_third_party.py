"""Baixa as ferramentas da comunidade em versões travadas para third_party/.

Uso:
    python scripts/update_third_party.py            # reinstala as versões de third_party/VERSIONS.json
    python scripts/update_third_party.py --latest   # atualiza para o último commit de cada projeto

O código de terceiros é copiado sem modificações. Toda adaptação fica no
pacote macpronto (src/macpronto/engine). A lista de componentes está em
src/macpronto/engine/components.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from macpronto.engine.components import COMPONENTS, download_zip, extract, latest_commit  # noqa: E402

THIRD_PARTY = ROOT / "third_party"
VERSIONS_FILE = THIRD_PARTY / "VERSIONS.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--latest", action="store_true", help="atualiza para o último commit de cada projeto")
    parser.add_argument("--only", help="atualiza só o componente com este nome")
    args = parser.parse_args()

    versions = json.loads(VERSIONS_FILE.read_text(encoding="utf-8")) if VERSIONS_FILE.exists() else {}

    for component in COMPONENTS:
        if args.only and component.name != args.only:
            continue
        print(f"{component.name}:")
        pinned = versions.get(component.name, {}).get("commit")
        sha = latest_commit(component)["sha"] if args.latest or not pinned else pinned
        print(f"  baixando {component.repository} @ {sha[:12]}")
        extract(component, download_zip(component, sha), THIRD_PARTY / component.name)
        versions[component.name] = {
            "repository": component.repository,
            "commit": sha,
            "license": component.license,
            "paths": list(component.paths),
        }
        print("  ok")

    VERSIONS_FILE.write_text(json.dumps(versions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
