"""Atualização automática, com um servidor local no lugar do GitHub."""

from __future__ import annotations

import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from macpronto import updater

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><link rel="alternate" type="text/html" href="https://github.com/x/MacPronto/releases/tag/v0.2.0-beta.1"/></entry>
  <entry><link rel="alternate" type="text/html" href="https://github.com/x/MacPronto/releases/tag/v0.1.1"/></entry>
  <entry><link rel="alternate" type="text/html" href="https://github.com/x/MacPronto/releases/tag/v0.1.0-beta.1"/></entry>
  <entry><link rel="alternate" type="text/html" href="https://github.com/x/MacPronto/releases/tag/nao-e-versao"/></entry>
</feed>"""


@pytest.mark.parametrize(
    ("older", "newer"),
    [
        ("0.1.0-beta.1", "0.1.0-beta.2"),
        ("0.1.0-beta.2", "0.1.0-beta.10"),
        ("0.1.0-beta.9", "0.1.0-rc.1"),
        ("0.1.0-rc.1", "0.1.0"),
        ("0.1.0", "0.1.1"),
        ("v0.9.9", "1.0.0"),
        ("1.0.0-alpha", "1.0.0-alpha.1"),
    ],
)
def test_ordem_das_versoes(older, newer):
    assert updater.is_newer(newer, older)
    assert not updater.is_newer(older, newer)
    assert not updater.is_newer(older, older)


def test_versoes_invalidas_nunca_sao_novas():
    assert updater.version_key("abc") is None
    assert not updater.is_newer("abc", "0.1.0")
    assert updater.is_prerelease("0.1.0-beta.1") and not updater.is_prerelease("0.1.0")


def test_feed_do_github():
    assert updater.parse_feed(FEED) == ["v0.2.0-beta.1", "v0.1.1", "v0.1.0-beta.1", "nao-e-versao"]


def manifest(version: str, data: bytes) -> dict:
    return {
        "version": version,
        "installer": {
            "name": f"MacPronto-{version}-instalador.exe",
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        },
        "notes": "Novidades",
    }


def test_manifesto_conferido():
    data = b"x" * (2 * 1024**2)
    ok = updater.parse_manifest(manifest("0.1.1", data), "v0.1.1", "https://github.com/x/MacPronto")
    assert ok["url"] == "https://github.com/x/MacPronto/releases/download/v0.1.1/MacPronto-0.1.1-instalador.exe"
    with pytest.raises(ValueError, match="tag"):
        updater.parse_manifest(manifest("0.1.2", data), "v0.1.1", "")
    bad = manifest("0.1.1", data)
    bad["installer"]["name"] = "..\\..\\Windows\\x.exe"
    with pytest.raises(ValueError, match="nome"):
        updater.parse_manifest(bad, "v0.1.1", "")
    bad = manifest("0.1.1", data)
    bad["installer"]["sha256"] = "123"
    with pytest.raises(ValueError, match="SHA"):
        updater.parse_manifest(bad, "v0.1.1", "")


class FakeGitHub:
    """Feed, manifestos e instaladores servidos localmente."""

    def __init__(self) -> None:
        self.installer = b"MZ" + b"\0" * (2 * 1024**2)
        self.files: dict[str, bytes] = {"/releases.atom": FEED.encode()}
        self.feed_requests = 0
        self.not_modified = 0
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:
                pass

            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/releases.atom":
                    fake.feed_requests += 1
                    if self.headers.get("If-None-Match") == '"feed-1"':
                        fake.not_modified += 1
                        self.send_response(304)
                        self.end_headers()
                        return
                body = fake.files.get(self.path)
                if body is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                if self.path == "/releases.atom":
                    self.send_header("ETag", '"feed-1"')
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def publish(self, tag: str, with_manifest: bool = True) -> None:
        version = tag.lstrip("v")
        data = manifest(version, self.installer)
        if with_manifest:
            self.files[f"/releases/download/{tag}/{updater.MANIFEST}"] = json.dumps(data).encode()
        self.files[f"/releases/download/{tag}/{data['installer']['name']}"] = self.installer


@pytest.fixture
def github(monkeypatch, tmp_path):
    monkeypatch.setenv("MACPRONTO_DATA_DIR", str(tmp_path))
    fake = FakeGitHub()
    monkeypatch.setenv("MACPRONTO_UPDATE_URL", fake.url)
    yield fake
    fake.server.shutdown()


def test_beta_recebe_a_maior_versao_e_baixa_conferindo(github, tmp_path):
    github.publish("v0.1.1")
    github.publish("v0.2.0-beta.1")
    notified = []
    checker = updater.Updater(notified.append, current="0.1.0-beta.1")

    status = checker.check()
    assert status["error"] is None
    assert status["available"]["version"] == "0.2.0-beta.1"
    assert len(notified) == 1

    checker.check()  # mesma versão: não avisa de novo e o feed vem do ETag
    assert len(notified) == 1 and github.not_modified == 1

    installer = checker.download(status["available"])
    assert installer.read_bytes() == github.installer
    assert installer.parent == tmp_path / "updates" / "0.2.0-beta.1"


def test_estavel_ignora_versoes_de_teste(github):
    github.publish("v0.1.1")
    github.publish("v0.2.0-beta.1")
    checker = updater.Updater(lambda status: None, current="0.1.0")
    assert checker.check()["available"]["version"] == "0.1.1"


def test_versao_sem_manifesto_e_pulada(github):
    github.publish("v0.1.1")
    github.publish("v0.2.0-beta.1", with_manifest=False)  # ainda recebendo os arquivos
    checker = updater.Updater(lambda status: None, current="0.1.0-beta.1")
    assert checker.check()["available"]["version"] == "0.1.1"

    github.publish("v0.2.0-beta.1")  # o GitHub Actions terminou de publicar
    assert checker.check()["available"]["version"] == "0.1.1"  # a verificação automática espera um pouco
    assert checker.check(force=True)["available"]["version"] == "0.2.0-beta.1"  # "Verificar agora" não espera


def test_atualizado_e_repositorio_privado(github):
    github.publish("v0.2.0-beta.1")
    assert updater.Updater(lambda s: None, current="0.2.0-beta.1").check()["available"] is None
    del github.files["/releases.atom"]
    status = updater.Updater(lambda s: None, current="0.1.0").check()
    assert status["available"] is None and "não está acessível" in status["error"]


def test_download_com_hash_errado_e_recusado(github, monkeypatch):
    monkeypatch.setattr(updater.net.time, "sleep", lambda seconds: None)
    github.publish("v0.1.1")
    checker = updater.Updater(lambda s: None, current="0.1.0")
    info = dict(checker.check()["available"], sha256="0" * 64)
    with pytest.raises(Exception, match="Hash|baixar"):
        checker.download(info)


def test_limpeza_dos_instaladores_antigos(monkeypatch, tmp_path):
    monkeypatch.setenv("MACPRONTO_DATA_DIR", str(tmp_path))
    for version in ("0.1.0-beta.1", "0.1.0", "0.2.0"):
        (tmp_path / "updates" / version).mkdir(parents=True)
    updater.cleanup("0.1.0")
    assert sorted(p.name for p in (tmp_path / "updates").iterdir()) == ["0.2.0"]
