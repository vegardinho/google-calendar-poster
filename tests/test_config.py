import config


def test_project_paths_are_relative_to_config_module():
    assert config.GOOGLE_CREDENTIALS_FILE.endswith("/credentials.json")
    assert config.GOOGLE_TOKEN_FILE.endswith("/token.pickle")


def test_env_value_reads_calendar_id_from_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("CALENDAR_ID=calendar@example.test\n", encoding="utf-8")
    monkeypatch.setattr(config, "env_file_path", lambda: str(env_file))
    monkeypatch.delenv("CALENDAR_ID", raising=False)

    assert config._env_value("CALENDAR_ID", "primary") == "calendar@example.test"


def test_env_value_uses_fallback_when_setting_is_missing(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("EVENTOR_API_KEY=key\n", encoding="utf-8")
    monkeypatch.setattr(config, "env_file_path", lambda: str(env_file))

    assert config._env_value("CALENDAR_ID", "primary") == "primary"
