"""Ferramentas da comunidade que o MacPronto usa e como baixá-las do GitHub.

Usado pelo scripts/update_third_party.py (versões travadas do repositório) e
pela atualização da base de regras feita pelo próprio programa.
"""

from __future__ import annotations

import io
import json
import shutil
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from macpronto import __version__


@dataclass(frozen=True)
class Component:
    name: str
    owner: str
    repo: str
    branch: str
    license: str
    # Caminhos dentro do repositório. "origem" ou "origem=>destino".
    paths: tuple[str, ...]
    # Pode ser atualizado pelo usuário, dentro do programa
    updatable: bool = False

    @property
    def repository(self) -> str:
        return f"https://github.com/{self.owner}/{self.repo}"


COMPONENTS = (
    Component(
        name="OpCore-Simplify",
        owner="lzhoang2801",
        repo="OpCore-Simplify",
        branch="main",
        license="BSD-3-Clause",
        paths=("Scripts", "OpCore-Simplify.py", "updater.py", "LICENSE", "README.md"),
        updatable=True,
    ),
    Component(
        name="Hardware-Sniffer",
        owner="lzhoang2801",
        repo="Hardware-Sniffer",
        branch="main",
        license="BSD-3-Clause",
        paths=("Scripts", "HardwareSniffer.py", "LICENSE", "README.md"),
        updatable=True,
    ),
    Component(
        name="USBToolBox",
        owner="USBToolBox",
        repo="tool",
        branch="master",
        license="MIT",
        paths=("resources/Info.plist", "LICENSE", "README.md"),
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

BY_NAME = {component.name: component for component in COMPONENTS}
USER_AGENT = f"MacPronto/{__version__}"


def _http_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def latest_commit(component: Component) -> dict:
    """Último commit do branch principal: {"sha", "date", "message"}."""
    data = _http_json(f"https://api.github.com/repos/{component.owner}/{component.repo}/commits/{component.branch}")
    commit = data.get("commit", {})
    return {
        "sha": data["sha"],
        "date": commit.get("committer", {}).get("date"),
        "message": (commit.get("message") or "").splitlines()[0] if commit.get("message") else "",
    }


def download_zip(component: Component, sha: str) -> zipfile.ZipFile:
    url = f"https://codeload.github.com/{component.owner}/{component.repo}/zip/{sha}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=300) as response:
        return zipfile.ZipFile(io.BytesIO(response.read()))


def extract(component: Component, archive: zipfile.ZipFile, destination: Path) -> None:
    """Extrai só os caminhos do componente para ``destination`` (que é recriada)."""
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
            raise ValueError(f"Caminho {source!r} não encontrado em {component.owner}/{component.repo}")
