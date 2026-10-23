"""Gera o MacPronto para distribuição.

Uso:
    python scripts/build.py                 # interface + executável + zip portátil (+ instalador, se houver Inno Setup)
    python scripts/build.py --skip-frontend # reaproveita frontend/dist

Saídas em dist/:
    MacPronto/                       pasta do programa (executável + recursos)
    MacPronto-<versão>-portatil.zip  versão portátil
    MacPronto-<versão>-instalador.exe (com o Inno Setup 6 instalado)
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from macpronto import __version__  # noqa: E402

BUILD = ROOT / "build"
DIST = ROOT / "dist"
APP_DIR = DIST / "MacPronto"
ISCC_CANDIDATES = (
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"),
)


def run(command: list[str], cwd: Path = ROOT) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True, shell=command[0] in ("npm", "npx"))


def build_frontend() -> None:
    frontend = ROOT / "frontend"
    run(["npm", "ci"] if (frontend / "package-lock.json").exists() else ["npm", "install"], cwd=frontend)
    run(["npm", "run", "build"], cwd=frontend)


def version_tuple() -> str:
    parts = (__version__.split("+")[0].split("-")[0].split(".") + ["0", "0", "0"])[:4]
    return ".".join(part if part.isdigit() else "0" for part in parts)


def build_executable() -> Path:
    output = BUILD / "nuitka"
    command = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--assume-yes-for-downloads",
        "--mingw64",
        "--enable-plugin=pywebview",
        "--include-package=macpronto",
        "--include-package-data=macpronto",
        # Scripts e HardwareSniffer são o código de terceiros carregado como fonte na área de trabalho.
        # Sem isto o Nuitka compila a pasta scripts/ do repositório (o Windows ignora maiúsculas)
        # como se fosse o pacote Scripts, e ela esconde o verdadeiro em tempo de execução.
        "--nofollow-import-to=Scripts,HardwareSniffer,pytest,ruff,PIL,tkinter,unittest",
        # ...e eles precisam poder ser importados como fonte, sem a trava do modo de distribuição
        "--no-deployment-flag=excluded-module-usage",
        "--windows-console-mode=disable",
        "--windows-uac-admin",
        f"--windows-icon-from-ico={ROOT / 'assets' / 'macpronto.ico'}",
        "--company-name=MacPronto",
        "--product-name=MacPronto",
        "--file-description=MacPronto",
        f"--file-version={version_tuple()}",
        f"--product-version={version_tuple()}",
        "--copyright=Copyright (c) 2026 Patrick da Costa Cruz. Licença MIT.",
        f"--output-dir={output}",
        "--output-filename=MacPronto.exe",
        str(ROOT / "scripts" / "MacPronto.py"),
    ]
    run(command)
    return output / "MacPronto.dist"


def assemble(nuitka_dist: Path) -> None:
    if APP_DIR.exists():
        shutil.rmtree(APP_DIR)
    shutil.copytree(nuitka_dist, APP_DIR)

    # Código de terceiros, carregado como fonte na área de trabalho do usuário
    shutil.copytree(
        ROOT / "third_party",
        APP_DIR / "third_party",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copytree(ROOT / "frontend" / "dist", APP_DIR / "ui")
    for name in ("LICENSE", "POLITICA-DE-USO.md", "README.md"):
        shutil.copy2(ROOT / name, APP_DIR / name)
    write_notices(APP_DIR / "AVISOS-DE-TERCEIROS.txt")


def write_notices(target: Path) -> None:
    sections = [
        "O MacPronto inclui ou baixa as ferramentas abaixo. Cada uma mantém a própria licença.\n",
    ]
    for folder in sorted((ROOT / "third_party").iterdir()):
        if not folder.is_dir():
            continue
        license_file = next((f for f in folder.iterdir() if f.name.upper().startswith("LICENSE")), None)
        if license_file:
            sections.append(
                f"\n===== {folder.name} =====\n\n{license_file.read_text(encoding='utf-8', errors='replace')}"
            )
    target.write_text("\n".join(sections), encoding="utf-8")


def make_zip() -> Path:
    archive = DIST / f"MacPronto-{__version__}-portatil.zip"
    archive.unlink(missing_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for file in APP_DIR.rglob("*"):
            if file.is_file():
                bundle.write(file, Path("MacPronto") / file.relative_to(APP_DIR))
    return archive


def make_installer() -> Path | None:
    iscc = next((c for c in ISCC_CANDIDATES if os.path.exists(c)), None) or shutil.which("iscc")
    if iscc is None:
        print("Inno Setup não encontrado: instalador não gerado (o zip portátil está pronto).")
        return None
    run(
        [
            iscc,
            f"/DAppVersion={__version__}",
            f"/DSourceDir={APP_DIR}",
            f"/O{DIST}",
            str(ROOT / "installer" / "MacPronto.iss"),
        ]
    )
    return DIST / f"MacPronto-{__version__}-instalador.exe"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skip-frontend", action="store_true")
    parser.add_argument("--skip-installer", action="store_true")
    args = parser.parse_args()

    if not args.skip_frontend:
        build_frontend()
    DIST.mkdir(exist_ok=True)
    nuitka_dist = build_executable()
    assemble(nuitka_dist)
    print("Portátil:", make_zip())
    if not args.skip_installer:
        installer = make_installer()
        if installer:
            print("Instalador:", installer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
