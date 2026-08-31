"""Configuration parsing is explicit, bounded, and side-effect free."""

from __future__ import annotations

import pytest

from omniscrape.config import Settings


def test_defaults_are_stable_for_empty_mapping() -> None:
    settings = Settings.from_env({})
    assert settings.api_key is None
    assert settings.allowed_hosts is None
    assert settings.outbound_allowed_hosts is None
    assert settings.enable_api_rendering is False
    assert settings.openai_api_key is None
    assert settings.openai_model
    assert settings.max_concurrency == 8
    assert settings.max_render_concurrency == 2
    assert settings.request_body_timeout_seconds == 5.0
    assert settings.fetch_timeout_seconds == 30.0
    assert settings.max_response_bytes == 2_000_000
    assert settings.max_redirects == 5
    assert settings.max_render_requests == 128
    assert settings.max_render_nodes == 50_000
    assert settings.provider_timeout_seconds == 30.0
    assert settings.auto_llm_threshold == 0.72


def test_new_outbound_policy_does_not_shift_existing_positional_settings() -> None:
    settings = Settings(None, None, False, None, "positional-model")
    assert settings.enable_api_rendering is False
    assert settings.openai_model == "positional-model"
    assert settings.outbound_allowed_hosts is None


def test_valid_values_are_parsed_without_mutating_input() -> None:
    values = {
        "OMNISCRAPE_API_KEY": "service-key",
        "OMNISCRAPE_ALLOWED_HOSTS": "api.example.test,api.example.test:8443",
        "OMNISCRAPE_OUTBOUND_ALLOWED_HOSTS": (
            "NEWS.Example.Test.,news.example.test,render.example.test:8443"
        ),
        "OMNISCRAPE_ENABLE_API_RENDERING": "true",
        "OPENAI_API_KEY": "provider-key",
        "OMNISCRAPE_OPENAI_MODEL": "fixture-model",
        "OMNISCRAPE_MAX_CONCURRENCY": "3",
        "OMNISCRAPE_MAX_RENDER_CONCURRENCY": "1",
        "OMNISCRAPE_QUEUE_TIMEOUT_SECONDS": "1.25",
        "OMNISCRAPE_REQUEST_BODY_TIMEOUT_SECONDS": "1.5",
        "OMNISCRAPE_CONNECT_TIMEOUT_SECONDS": "2.5",
        "OMNISCRAPE_READ_TIMEOUT_SECONDS": "7.5",
        "OMNISCRAPE_FETCH_TIMEOUT_SECONDS": "12.5",
        "OMNISCRAPE_MAX_RESPONSE_BYTES": "4096",
        "OMNISCRAPE_MAX_REDIRECTS": "0",
        "OMNISCRAPE_USER_AGENT": "FixtureAgent/1",
        "OMNISCRAPE_RENDER_TIMEOUT_MS": "500",
        "OMNISCRAPE_MAX_RENDER_REQUESTS": "9",
        "OMNISCRAPE_MAX_RENDER_NODES": "321",
        "OMNISCRAPE_PROVIDER_TIMEOUT_SECONDS": "8.5",
        "OMNISCRAPE_AUTO_LLM_THRESHOLD": "0.55",
    }
    original = values.copy()
    settings = Settings.from_env(values)

    assert settings.api_key == "service-key"
    assert settings.allowed_hosts == ("api.example.test", "api.example.test:8443")
    assert settings.outbound_allowed_hosts == (
        "news.example.test",
        "render.example.test:8443",
    )
    assert settings.enable_api_rendering is True
    assert settings.openai_api_key == "provider-key"
    assert settings.openai_model == "fixture-model"
    assert settings.max_concurrency == 3
    assert settings.max_render_concurrency == 1
    assert settings.queue_timeout_seconds == 1.25
    assert settings.request_body_timeout_seconds == 1.5
    assert settings.connect_timeout_seconds == 2.5
    assert settings.read_timeout_seconds == 7.5
    assert settings.fetch_timeout_seconds == 12.5
    assert settings.max_response_bytes == 4096
    assert settings.max_redirects == 0
    assert settings.user_agent == "FixtureAgent/1"
    assert settings.render_timeout_ms == 500
    assert settings.max_render_requests == 9
    assert settings.max_render_nodes == 321
    assert settings.provider_timeout_seconds == 8.5
    assert settings.auto_llm_threshold == 0.55
    assert values == original


def test_invalid_and_out_of_range_values_fall_back() -> None:
    settings = Settings.from_env(
        {
            "OMNISCRAPE_MAX_CONCURRENCY": "not-an-int",
            "OMNISCRAPE_QUEUE_TIMEOUT_SECONDS": "not-a-float",
            "OMNISCRAPE_REQUEST_BODY_TIMEOUT_SECONDS": "0",
            "OMNISCRAPE_CONNECT_TIMEOUT_SECONDS": "0",
            "OMNISCRAPE_READ_TIMEOUT_SECONDS": "-2",
            "OMNISCRAPE_FETCH_TIMEOUT_SECONDS": "0",
            "OMNISCRAPE_MAX_RESPONSE_BYTES": "100",
            "OMNISCRAPE_MAX_REDIRECTS": "-1",
            "OMNISCRAPE_RENDER_TIMEOUT_MS": "50",
            "OMNISCRAPE_MAX_RENDER_REQUESTS": "0",
            "OMNISCRAPE_MAX_RENDER_NODES": "0",
            "OMNISCRAPE_PROVIDER_TIMEOUT_SECONDS": "-1",
            "OMNISCRAPE_AUTO_LLM_THRESHOLD": "2",
        }
    )
    assert settings.max_concurrency == 8
    assert settings.queue_timeout_seconds == 5.0
    assert settings.request_body_timeout_seconds == 5.0
    assert settings.connect_timeout_seconds == 5.0
    assert settings.read_timeout_seconds == 15.0
    assert settings.fetch_timeout_seconds == 30.0
    assert settings.max_response_bytes == 2_000_000
    assert settings.max_redirects == 5
    assert settings.render_timeout_ms == 15_000
    assert settings.max_render_requests == 128
    assert settings.max_render_nodes == 50_000
    assert settings.provider_timeout_seconds == 30.0
    assert settings.auto_llm_threshold == 0.72

    assert Settings.from_env({"OMNISCRAPE_MAX_CONCURRENCY": "33"}).max_concurrency == 8


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("OMNISCRAPE_ENABLE_API_RENDERING", ""),
        ("OMNISCRAPE_ENABLE_API_RENDERING", "yes"),
        ("OMNISCRAPE_ENABLE_API_RENDERING", "TRUE"),
        ("OMNISCRAPE_ENABLE_API_RENDERING", " false"),
        ("OMNISCRAPE_ENABLE_API_RENDERING", "1"),
        ("OMNISCRAPE_MAX_RENDER_CONCURRENCY", "0"),
        ("OMNISCRAPE_MAX_RENDER_CONCURRENCY", "3"),
        ("OMNISCRAPE_MAX_RENDER_CONCURRENCY", "1.0"),
        ("OMNISCRAPE_MAX_RENDER_CONCURRENCY", " 1"),
    ],
)
def test_renderer_policy_environment_values_fail_closed(name: str, value: str) -> None:
    with pytest.raises(ValueError, match=name):
        Settings.from_env({name: value})


@pytest.mark.parametrize("value", [1, "true", None])
def test_direct_settings_requires_boolean_api_rendering(value: object) -> None:
    with pytest.raises(ValueError, match="enable_api_rendering must be a boolean"):
        Settings(enable_api_rendering=value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [0, 3, False, 1.0])
def test_direct_settings_bounds_render_concurrency(value: object) -> None:
    with pytest.raises(ValueError, match=r"max_render_concurrency.*between 1 and 2"):
        Settings(max_render_concurrency=value)  # type: ignore[arg-type]


def test_direct_settings_rejects_concurrency_above_global_capacity() -> None:
    with pytest.raises(ValueError, match="between 1 and 32"):
        Settings(max_concurrency=33)


def test_direct_settings_rejects_non_ascii_api_key() -> None:
    with pytest.raises(ValueError, match="ASCII"):
        Settings(api_key="cl\u00e9")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("queue_timeout_seconds", float("inf")),
        ("request_body_timeout_seconds", float("nan")),
        ("connect_timeout_seconds", 0),
        ("read_timeout_seconds", -1),
        ("fetch_timeout_seconds", True),
        ("provider_timeout_seconds", "slow"),
        ("max_response_bytes", 100),
        ("max_redirects", 21),
        ("render_timeout_ms", 0),
        ("max_render_requests", False),
        ("max_render_nodes", float("inf")),
        ("auto_llm_threshold", float("nan")),
    ],
)
def test_direct_settings_rejects_invalid_resource_limits(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        Settings(**{field: value})  # type: ignore[arg-type]


@pytest.mark.parametrize("api_key", [" secret", "secret ", "has space", "line\nbreak"])
def test_direct_settings_rejects_api_key_whitespace_or_controls(api_key: str) -> None:
    with pytest.raises(ValueError, match="printable ASCII"):
        Settings(api_key=api_key)


def test_non_finite_timeout_values_fall_back_to_finite_defaults() -> None:
    for raw in ("inf", "Infinity", "1e999", "nan"):
        settings = Settings.from_env(
            {
                "OMNISCRAPE_QUEUE_TIMEOUT_SECONDS": raw,
                "OMNISCRAPE_REQUEST_BODY_TIMEOUT_SECONDS": raw,
                "OMNISCRAPE_CONNECT_TIMEOUT_SECONDS": raw,
                "OMNISCRAPE_READ_TIMEOUT_SECONDS": raw,
                "OMNISCRAPE_FETCH_TIMEOUT_SECONDS": raw,
                "OMNISCRAPE_PROVIDER_TIMEOUT_SECONDS": raw,
            }
        )
        assert settings.queue_timeout_seconds == 5.0
        assert settings.request_body_timeout_seconds == 5.0
        assert settings.connect_timeout_seconds == 5.0
        assert settings.read_timeout_seconds == 15.0
        assert settings.fetch_timeout_seconds == 30.0
        assert settings.provider_timeout_seconds == 30.0


def test_process_environment_is_read_only_when_mapping_is_omitted(monkeypatch: object) -> None:
    monkeypatch.setenv("OMNISCRAPE_MAX_CONCURRENCY", "11")  # type: ignore[attr-defined]
    assert Settings.from_env().max_concurrency == 11


def test_allowed_hosts_rejects_wildcards() -> None:
    try:
        Settings.from_env({"OMNISCRAPE_ALLOWED_HOSTS": "*"})
    except ValueError as exc:
        assert "explicit Host authorities" in str(exc)
    else:
        raise AssertionError("A wildcard Host policy must fail closed")


@pytest.mark.parametrize(
    "authority",
    (
        "api.example:notaport",
        "api.example/path",
        "user@api.example",
        "api.example?query=yes",
        "api.example#fragment",
        "api.example:",
        "[2001:db8::1]:",
    ),
)
def test_allowed_hosts_reject_malformed_authorities_at_load_time(authority: str) -> None:
    with pytest.raises(ValueError, match="explicit Host authorities"):
        Settings.from_env({"OMNISCRAPE_ALLOWED_HOSTS": authority})


def test_allowed_hosts_are_normalized_and_deduplicated() -> None:
    settings = Settings.from_env(
        {"OMNISCRAPE_ALLOWED_HOSTS": "API.Example.,api.example,[2001:db8::1]:8443"}
    )
    assert settings.allowed_hosts == ("api.example", "[2001:db8::1]:8443")


def test_outbound_allowed_hosts_are_normalized_and_deduplicated() -> None:
    settings = Settings.from_env(
        {
            "OMNISCRAPE_OUTBOUND_ALLOWED_HOSTS": (
                "EXAMPLE.com.,example.com,xn--fsqu00a.test,例子.test,"
                "example.com:8443,[2606:4700:4700::1111]:443"
            )
        }
    )
    assert settings.outbound_allowed_hosts == (
        "example.com",
        "xn--fsqu00a.test",
        "example.com:8443",
        "[2606:4700:4700::1111]:443",
    )


@pytest.mark.parametrize(
    "authority",
    (
        "*",
        "*.example.test",
        "example.test/path",
        "user@example.test",
        "example.test:notaport",
        "example.test:",
        "[2606:4700:4700::1111]:",
        "example.test?query=yes",
    ),
)
def test_outbound_allowed_hosts_reject_malformed_or_wildcard_entries(
    authority: str,
) -> None:
    with pytest.raises(ValueError, match="OMNISCRAPE_OUTBOUND_ALLOWED_HOSTS"):
        Settings.from_env({"OMNISCRAPE_OUTBOUND_ALLOWED_HOSTS": authority})


def test_direct_outbound_allowed_hosts_are_normalized() -> None:
    settings = Settings(outbound_allowed_hosts=("EXAMPLE.test.", "example.test:8443"))
    assert settings.outbound_allowed_hosts == ("example.test", "example.test:8443")


def test_outbound_allowed_hosts_use_nontransitional_idna() -> None:
    settings = Settings(outbound_allowed_hosts=("faß.de", "xn--fa-hia.de"))
    assert settings.outbound_allowed_hosts == ("xn--fa-hia.de",)


def test_api_rendering_requires_non_empty_outbound_allowlist() -> None:
    with pytest.raises(
        ValueError,
        match=r"OMNISCRAPE_ENABLE_API_RENDERING.*OMNISCRAPE_OUTBOUND_ALLOWED_HOSTS",
    ):
        Settings(enable_api_rendering=True, outbound_allowed_hosts=None)

    with pytest.raises(ValueError, match="OMNISCRAPE_OUTBOUND_ALLOWED_HOSTS"):
        Settings(enable_api_rendering=True, outbound_allowed_hosts=())


def test_outbound_allowlist_does_not_change_default_non_api_policy() -> None:
    settings = Settings.from_env({})
    assert settings.enable_api_rendering is False
    assert settings.outbound_allowed_hosts is None
