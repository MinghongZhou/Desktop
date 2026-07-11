import pytest

from robinhood_bot.config import DEFAULT_SETTINGS_PATH, load_settings


def test_default_settings_load_and_default_to_shadow():
    settings = load_settings(DEFAULT_SETTINGS_PATH)
    assert settings.mode == "shadow"
    assert settings.live_trading_enabled is False
    assert settings.broker.adapter == "shadow"


def test_live_mode_requires_explicit_flag():
    from robinhood_bot.config import Settings

    base = load_settings(DEFAULT_SETTINGS_PATH).model_dump()
    base["mode"] = "live"
    base["live_trading_enabled"] = False
    with pytest.raises(ValueError, match="live_trading_enabled"):
        Settings.model_validate(base)


def test_live_mode_rejects_mcp_placeholder_adapter():
    from robinhood_bot.config import Settings

    base = load_settings(DEFAULT_SETTINGS_PATH).model_dump()
    base["mode"] = "live"
    base["live_trading_enabled"] = True
    base["broker"]["adapter"] = "mcp_placeholder"
    with pytest.raises(ValueError, match="mcp_placeholder"):
        Settings.model_validate(base)
