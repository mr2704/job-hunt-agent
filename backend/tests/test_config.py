"""
Tests for configuration hardening:
- Placeholder secret rejection in production and warning in development (F5).
- Safe validation error formatting without leaking secret inputs (F6).
- Anthropic model default and environment configurability (F21).
"""
from __future__ import annotations

import os
import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings, validate_config, _repo_dir


class TestConfigHardening:
    """Test placeholder secret rejection and safe error messages."""

    def test_placeholder_secret_rejected_in_production(self, monkeypatch):
        """In production, placeholder SECRET_KEY must cause startup to fail with safe error."""
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("SECRET_KEY", "REPLACE_WITH_RANDOM_SECRET_KEY_64_CHARS")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://jobagent:fake-test-password@localhost:5432/jobagent")
        monkeypatch.setenv("DATABASE_URL_SYNC", "postgresql://jobagent:fake-test-password@localhost:5432/jobagent")

        with pytest.raises(Exception) as exc_info:
            Settings(_env_file=None)

        err_msg = str(exc_info.value)
        # Must name the field
        assert "secret_key" in err_msg.lower()
        # Must NOT echo the placeholder or secret value
        assert "REPLACE_WITH_RANDOM" not in err_msg
        assert "64_CHARS" not in err_msg

    def test_placeholder_secret_allowed_in_development_with_flag(self, monkeypatch):
        """In development, placeholder SECRET_KEY is permitted but flagged."""
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv("SECRET_KEY", "REPLACE_WITH_RANDOM_SECRET_KEY_64_CHARS")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://jobagent:fake-test-password@localhost:5432/jobagent")
        monkeypatch.setenv("DATABASE_URL_SYNC", "postgresql://jobagent:fake-test-password@localhost:5432/jobagent")

        s = Settings(_env_file=None)
        assert s.secret_key_is_placeholder is True

    def test_safe_validation_error_does_not_leak_input_value(self, monkeypatch):
        """Validation errors on secret fields must never echo the input value."""
        secret_leak_candidate = "SUPER_SECRET_LEAK_TOKEN_TOO_SHORT"
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv("SECRET_KEY", secret_leak_candidate)  # len 33 but let's test invalid
        # Let's test a value that triggers validation error (too short)
        short_secret = "LEAK_ME_123"
        monkeypatch.setenv("SECRET_KEY", short_secret)
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://jobagent:fake-test-password@localhost:5432/jobagent")
        monkeypatch.setenv("DATABASE_URL_SYNC", "postgresql://jobagent:fake-test-password@localhost:5432/jobagent")

        with pytest.raises(RuntimeError) as exc_info:
            get_settings.__wrapped__()

        err_msg = str(exc_info.value)
        # Must NOT leak the secret input value
        assert short_secret not in err_msg
        assert "LEAK_ME" not in err_msg
        # Must name the field and reason
        assert "secret_key" in err_msg
        assert "too short" in err_msg.lower() or "length" in err_msg.lower()

    def test_anthropic_model_default_and_override(self, monkeypatch):
        """Anthropic model defaults to documented model and is configurable via env."""
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv("SECRET_KEY", "a" * 64)
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://jobagent:fake-test-password@localhost:5432/jobagent")
        monkeypatch.setenv("DATABASE_URL_SYNC", "postgresql://jobagent:fake-test-password@localhost:5432/jobagent")
        monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)

        s = Settings(_env_file=None)
        assert s.anthropic_model == "claude-sonnet-5-5"

        monkeypatch.setenv("ANTHROPIC_MODEL", "claude-haiku-5-5")
        s2 = Settings(_env_file=None)
        assert s2.anthropic_model == "claude-haiku-5-5"

    def test_database_url_placeholder_accepted_in_development(self, monkeypatch):
        """In development mode, CHANGE_ME_LOCAL_ONLY database placeholder is permitted."""
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv("SECRET_KEY", "b" * 64)
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://jobagent:CHANGE_ME_LOCAL_ONLY@localhost:5432/jobagent")
        monkeypatch.setenv("DATABASE_URL_SYNC", "postgresql://jobagent:CHANGE_ME_LOCAL_ONLY@localhost:5432/jobagent")

        s = Settings(_env_file=None)
        assert s.app_env == "development"

    @pytest.mark.parametrize("env_mode", ["staging", "production"])
    def test_database_url_placeholder_rejected_outside_development(self, monkeypatch, env_mode):
        """In staging or production mode, CHANGE_ME_LOCAL_ONLY database placeholder is rejected."""
        monkeypatch.setenv("APP_ENV", env_mode)
        monkeypatch.setenv("SECRET_KEY", "c" * 64)
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://jobagent:CHANGE_ME_LOCAL_ONLY@localhost:5432/jobagent")
        monkeypatch.setenv("DATABASE_URL_SYNC", "postgresql://jobagent:CHANGE_ME_LOCAL_ONLY@localhost:5432/jobagent")

        with pytest.raises(Exception) as exc_info:
            Settings(_env_file=None)

        err_msg = str(exc_info.value)
        assert "database_url" in err_msg.lower()
        assert "placeholder" in err_msg.lower()

