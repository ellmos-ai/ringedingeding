from __future__ import annotations

import json

import pytest

from ringedingeding.calle_credentials import (
    API_KEY_ENV,
    CONFIG_FILE_ENV,
    ENV_FILE_ENV,
    CalleCredentialError,
    load_calle_settings,
    save_project_api_key,
)


def test_key_priority_is_environment_then_dotenv_then_config(tmp_path):
    env_file = tmp_path / ".env"
    config_file = tmp_path / "config.local.json"
    env_file.write_text("CALLE_API_KEY=from-dotenv\n", encoding="utf-8")
    config_file.write_text('{"CALLE_API_KEY": "from-config"}\n', encoding="utf-8")

    settings = load_calle_settings(
        environ={API_KEY_ENV: "from-environment"},
        env_file=env_file,
        config_file=config_file,
    )
    assert settings.api_key == "from-environment"
    assert settings.source == "environment"

    settings = load_calle_settings(environ={}, env_file=env_file, config_file=config_file)
    assert settings.api_key == "from-dotenv"
    assert settings.source == ".env"

    env_file.unlink()
    settings = load_calle_settings(environ={}, env_file=env_file, config_file=config_file)
    assert settings.api_key == "from-config"
    assert settings.source == "project config"


def test_missing_key_lists_every_supported_path(tmp_path):
    env_file = tmp_path / ".env"
    config_file = tmp_path / "config.local.json"
    with pytest.raises(CalleCredentialError) as caught:
        load_calle_settings(environ={}, env_file=env_file, config_file=config_file)
    message = str(caught.value)
    assert "CALLE_API_KEY" in message
    assert "CALLE_ENV_FILE" in message
    assert "CALLE_CONFIG_FILE" in message
    assert "Dry runs work without a key" in message


def test_settings_page_masks_and_never_echoes_the_submitted_key(tmp_path, monkeypatch, caplog):
    pytest.importorskip("fastapi", reason="the web interface is an optional extra")
    from fastapi.testclient import TestClient

    from ringedingeding.web.app import create_app

    env_file = tmp_path / "absent.env"
    config_file = tmp_path / "config.local.json"
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    monkeypatch.setenv(ENV_FILE_ENV, str(env_file))
    monkeypatch.setenv(CONFIG_FILE_ENV, str(config_file))
    submitted = "unit-test-private-7824"

    with TestClient(create_app(tmp_path / "web.db")) as client:
        response = client.post("/settings", data={"api_key": submitted})

    assert response.status_code == 200
    assert submitted not in response.text
    assert "••••7824" in response.text
    assert submitted not in caplog.text
    assert json.loads(config_file.read_text(encoding="utf-8"))[API_KEY_ENV] == submitted


def test_save_uses_config_path_override(tmp_path):
    target = tmp_path / "custom" / "settings.json"
    saved = save_project_api_key(
        "local-test-value", environ={CONFIG_FILE_ENV: str(target)}
    )
    assert saved == target.resolve()
    assert json.loads(target.read_text(encoding="utf-8"))[API_KEY_ENV] == "local-test-value"
