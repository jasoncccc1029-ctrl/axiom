"""Phase-1 deploy helpers: DB URL normalize + CORS parsing."""

from app.config import normalize_database_url
from app.main import _cors_origins


def test_normalize_postgres_urls():
    assert normalize_database_url("postgres://u:p@h/db").startswith("postgresql+psycopg://")
    assert normalize_database_url("postgresql://u:p@h/db").startswith("postgresql+psycopg://")
    assert "postgresql+psycopg://" in normalize_database_url(
        "postgresql+psycopg://u:p@h/db"
    )
    assert normalize_database_url("sqlite:///tmp/x.db") == "sqlite:///tmp/x.db"


def test_cors_includes_localhost(monkeypatch):
    from app import config

    monkeypatch.setattr(config.settings, "cors_origins", "https://axiom.vercel.app")
    origins = _cors_origins()
    assert "http://localhost:3000" in origins
    assert "https://axiom.vercel.app" in origins
