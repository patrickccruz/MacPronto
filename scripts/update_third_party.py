"""Baixa as ferramentas da comunidade em versões travadas para third_party/.

Uso:
    python scripts/update_third_party.py            # reinstala as versões de third_party/VERSIONS.json
    python scripts/update_third_party.py --latest   # atualiza para o último commit de cada projeto

O código de terceiros é copiado sem modificações. Toda adaptação fica no
pacote macpronto (src/macpronto/engine).
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THIRD_PARTY = ROOT / "third_party"
VERSIONS_FILE = THIRD_PARTY / "VERSIONS.json"


@dataclass(frozen=True)
class Component:
    name: str
    owner: str
    repo: str
    branch: str
    license: str
    # Caminhos dentro do repositório. "origem" ou "origem=>destino".
    paths: tuple[str, ...]


COMPONENTS = (
    Component(
        name="OpCore-Simplify",
        owner="lzhoang2801",
        repo="OpCore-Simplify",
        branch="main",
        license="BSD-3-Clause",
        paths=("Scripts", "OpCore-Simplify.py", "updater.py", "LICENSE", "README.md"),
    ),
    Component(
        name="Hardware-Sniffer",
        owner="lzhoang2801",
        repo="Hardware-Sniffer",
        branch="main",
        license="BSD-3-Clause",
        paths=("Scripts", "HardwareSniffer.py", "LICENSE", "README.md"),
    ),
    Component(
        name="USBToolBox",
        owner="USBToolBox",
        repo="tool",
        branch="master",
        license="MIT",
        paths=("resources/usbdump.exe", "resources/Info.plist", "LICENSE", "README.md"),
    ),
    Component(
        name="macrecovery",
        owner="acidanthera",
        repo="OpenCorePkg",
        branch="master",
        license="BSD-3-Clause",
        paths=(
            "Utilities/macrecovery/macrecovery.py=>macrecovery.py",
            "Utilities/macrecovery/boards.json=>boards.json",
            "Utilities/macrecovery/recovery_urls.txt=>recovery_urls.txt",
            "LICENSE.txt=>LICENSE.txt",
        ),
    ),
)


def http_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "MacPronto"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def latest_commit(component: Component) -> str:
    data = http_json(f"https://api.github.com/repos/{component.owner}/{component.repo}/commits/{component.branch}")
    return data["sha"]


def download_zip(component: Component, sha: str) -> zipfile.ZipFile:
    url = f"https://codeload.github.com/{component.owner}/{component.repo}/zip/{sha}"
    print(f"  baixando {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "MacPronto"})
    with urllib.request.urlopen(request, timeout=300) as response:
        return zipfile.ZipFile(io.BytesIO(response.read()))


def extract(component: Component, archive: zipfile.ZipFile, destination: Path) -> None:
    prefix = archive.namelist()[0].split("/", 1)[0] + "/"
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)

    for spec in component.paths:
        source, _, target = spec.partition("=>")
        target = target or source
        source_prefix = prefix + source
        matched = False
        for member in archive.infolist():
            if member.is_dir():
                continue
            if member.filename == source_prefix:
                relative = target
            elif member.filename.startswith(source_prefix + "/"):
                relative = target + member.filename[len(source_prefix) :]
            else:
                continue
            matched = True
            output = destination / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(archive.read(member))
        if not matched:
            raise SystemExit(f"Caminho {source!r} não encontrado em {component.owner}/{component.repo}")


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
        sha = latest_commit(component) if args.latest or not pinned else pinned
        archive = download_zip(component, sha)
        extract(component, archive, THIRD_PARTY / component.name)
        versions[component.name] = {
            "repository": f"https://github.com/{component.owner}/{component.repo}",
            "commit": sha,
            "license": component.license,
            "paths": list(component.paths),
        }
        print(f"  ok, commit {sha[:12]}")

    VERSIONS_FILE.write_text(json.dumps(versions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
