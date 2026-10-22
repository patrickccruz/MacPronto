from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session", autouse=True)
def isolated_dirs(tmp_path_factory):
    """Pastas de dados e de saída temporárias para não tocar nas do usuário."""
    base = tmp_path_factory.mktemp("macpronto")
    os.environ["MACPRONTO_DATA_DIR"] = str(base / "data")
    os.environ["MACPRONTO_OUTPUT_DIR"] = str(base / "docs")
    yield base


def load_report(name: str) -> dict:
    return json.loads((FIXTURES / "reports" / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture
def report_loader():
    return load_report
