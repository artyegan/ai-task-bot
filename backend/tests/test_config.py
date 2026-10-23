from app.core.config import Settings


def test_defaults_match_contracts():
    s = Settings(_env_file=None)
    assert s.transcriber == "local"
    assert s.whisper_model == "small"
    assert s.max_voice_bytes == 20 * 1024 * 1024
    assert s.database_url.startswith("postgresql+asyncpg://")


def test_env_override(monkeypatch):
    monkeypatch.setenv("TRANSCRIBER", "fake")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    s = Settings(_env_file=None)
    assert s.transcriber == "fake"
    assert s.log_level == "debug"


def test_cors_origins_comma_separated(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test")
    assert Settings(_env_file=None).cors_origins_list == ["http://a.test", "http://b.test"]
