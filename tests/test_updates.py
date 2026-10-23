"""Atualização da base de regras: só ativa versões que passam no autoteste."""

from __future__ import annotations

import io
import zipfile

import pytest

from macpronto import paths
from macpronto.engine import components, updates, workspace
from macpronto.engine.errors import EngineError


def fake_release(monkeypatch, sha: str, broken: bool = False) -> None:
    """Simula o GitHub com um zip feito a partir da cópia travada do OpCore Simplify."""
    source = paths.third_party_dir() / "OpCore-Simplify"

    def build_zip(_component, _sha):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for file in source.rglob("*"):
                if not file.is_file() or "__pycache__" in file.parts:
                    continue
                relative = file.relative_to(source).as_posix()
                data = file.read_bytes()
                if broken and relative == "Scripts/compatibility_checker.py":
                    data = b"raise RuntimeError('quebrado de proposito')\n"
                archive.writestr(f"OpCore-Simplify-{sha}/{relative}", data)
        buffer.seek(0)
        return zipfile.ZipFile(buffer)

    monkeypatch.setattr(
        components, "latest_commit", lambda _c: {"sha": sha, "date": "2026-10-23T00:00:00Z", "message": "teste"}
    )
    monkeypatch.setattr(components, "download_zip", build_zip)


@pytest.fixture(autouse=True)
def clean_state():
    workspace.set_active_update("OpCore-Simplify", None)
    yield
    workspace.set_active_update("OpCore-Simplify", None)


def test_atualizacao_valida_e_ativada_e_pode_voltar(monkeypatch):
    fake_release(monkeypatch, "a" * 40)
    result = updates.install("OpCore-Simplify")
    assert result["commit"] == "a" * 40
    assert "kexts" in result["selftest"]
    source, commit, origin = workspace.active_source("OpCore-Simplify")
    assert (commit, origin) == ("a" * 40, "atualizada")
    assert (source / "Scripts" / "compatibility_checker.py").exists()

    updates.revert("OpCore-Simplify")
    assert workspace.active_source("OpCore-Simplify")[2] == "travada"
    assert not any(workspace.updates_dir().glob("OpCore-Simplify-*"))


def test_atualizacao_quebrada_nao_e_ativada(monkeypatch):
    fake_release(monkeypatch, "b" * 40, broken=True)
    with pytest.raises(EngineError) as error:
        updates.install("OpCore-Simplify")
    assert error.value.code == "update-selftest"
    assert workspace.active_source("OpCore-Simplify")[2] == "travada"
    assert not (workspace.updates_dir() / f"OpCore-Simplify-{'b' * 12}").exists()


def test_componente_que_nao_atualiza():
    with pytest.raises(ValueError):
        updates.install("macrecovery")
