"""Immutable, explicitly loaded OmniScrape configuration."""

from __future__ import annotations

import contextlib
import ipaddress
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from os import environ as process_environ
from urllib.parse import urlsplit

import idna

from ._tasking import MAX_TASK_CAPACITY


def _positive_int(
    raw: str | None,
    default: int,
    *,
    minimum: int = 1,
    maximum: int | None = None,
) -> int:
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= minimum and (maximum is None or value <= maximum) else default


def _positive_float(raw: str | None, default: float, *, maximum: float = 300.0) -> float:
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if 0 < value <= maximum and math.isfinite(value) else default


def _strict_env_bool(name: str, raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    if not isinstance(raw, str) or raw != raw.strip():
        raise ValueError(f"{name} must be exactly 'true' or 'false'.")
    if raw == "true":
        return True
    if raw == "false":
        return False
    raise ValueError(f"{name} must be exactly 'true' or 'false'.")


def _strict_env_int(
    name: str,
    raw: str | None,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    if raw is None:
        return default
    if not isinstance(raw, str) or not raw.isascii() or not raw.isdecimal():
        raise ValueError(f"{name} must be an integer between {minimum} and {maximum}.")
    value = int(raw)
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be an integer between {minimum} and {maximum}.")
    return value


def _require_int(
    name: str,
    value: object,
    *,
    minimum: int,
    maximum: int | None = None,
) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < minimum
        or (maximum is not None and value > maximum)
    ):
        bounds = f">= {minimum}" if maximum is None else f"between {minimum} and {maximum}"
        raise ValueError(f"{name} must be an integer {bounds}.")


def _require_finite_float(
    name: str,
    value: object,
    *,
    minimum_exclusive: float = 0.0,
    maximum: float = 300.0,
) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) <= minimum_exclusive
        or float(value) > maximum
    ):
        raise ValueError(f"{name} must be finite and greater than {minimum_exclusive}.")


def _parse_host_authority(
    raw: str, *, allow_unbracketed_ip: bool = False
) -> tuple[str, int | None]:
    """Parse one exact HTTP Host authority without accepting URL syntax."""

    value = raw.strip()
    if not value or value != raw or any(character.isspace() for character in value):
        raise ValueError("Invalid Host authority.")
    if allow_unbracketed_ip:
        with contextlib.suppress(ValueError):
            return str(ipaddress.ip_address(value)), None
    # ``urlsplit("//example.test:").port`` is ``None`` rather than an error.
    # Reject an explicitly empty port so a mistaken scoped rule cannot become
    # an unrestricted hostname-only rule.
    if value.endswith(":"):
        raise ValueError("Invalid Host authority.")
    parsed = urlsplit(f"//{value}")
    if (
        parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Invalid Host authority.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Invalid Host authority.") from exc
    host = parsed.hostname.rstrip(".")
    if not host or "*" in host:
        raise ValueError("Invalid Host authority.")
    return _normalize_hostname(host), port


def _normalize_hostname(raw: str) -> str:
    """Canonicalize an IP literal or DNS hostname consistently everywhere."""

    host = raw.rstrip(".")
    if not host:
        raise ValueError("Invalid hostname.")
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        try:
            # UTS-46 processing with non-transitional IDNA2008 semantics keeps
            # characters such as German sharp-s distinct from ASCII ``ss``.
            return idna.encode(host, uts46=True, std3_rules=True).decode("ascii").lower()
        except (idna.IDNAError, UnicodeError) as exc:
            raise ValueError("Invalid hostname.") from exc


def _format_host_authority(host: str, port: int | None) -> str:
    displayed = f"[{host}]" if ":" in host and port is not None else host
    return displayed if port is None else f"{displayed}:{port}"


def _normalize_authorities(
    values: tuple[str, ...], *, setting_name: str, description: str
) -> tuple[str, ...]:
    try:
        normalized = (
            _format_host_authority(*_parse_host_authority(item, allow_unbracketed_ip=True))
            for item in values
        )
        result = tuple(dict.fromkeys(normalized))
    except ValueError as exc:
        raise ValueError(f"{setting_name} must contain explicit {description}.") from exc
    if not result:
        raise ValueError(f"{setting_name} must contain explicit {description}.")
    return result


def _normalize_host_authorities(values: tuple[str, ...]) -> tuple[str, ...]:
    return _normalize_authorities(
        values,
        setting_name="OMNISCRAPE_ALLOWED_HOSTS",
        description="Host authorities",
    )


def _normalize_outbound_host_authorities(values: tuple[str, ...]) -> tuple[str, ...]:
    return _normalize_authorities(
        values,
        setting_name="OMNISCRAPE_OUTBOUND_ALLOWED_HOSTS",
        description="outbound target Host authorities",
    )


def _allowed_hosts(raw: str | None) -> tuple[str, ...] | None:
    if raw is None or not raw.strip():
        return None
    hosts = tuple(item.strip() for item in raw.split(",") if item.strip())
    return _normalize_host_authorities(hosts)


def _outbound_allowed_hosts(raw: str | None) -> tuple[str, ...] | None:
    if raw is None or not raw.strip():
        return None
    hosts = tuple(item.strip() for item in raw.split(",") if item.strip())
    return _normalize_outbound_host_authorities(hosts)


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings; loading reads but never mutates the process environment."""

    api_key: str | None = field(default=None, repr=False)
    allowed_hosts: tuple[str, ...] | None = None
    enable_api_rendering: bool = False
    openai_api_key: str | None = field(default=None, repr=False)
    openai_model: str = "gpt-5.6-luna"
    max_concurrency: int = 8
    max_render_concurrency: int = 2
    queue_timeout_seconds: float = 5.0
    request_body_timeout_seconds: float = 5.0
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 15.0
    fetch_timeout_seconds: float = 30.0
    max_response_bytes: int = 2_000_000
    max_redirects: int = 5
    user_agent: str = "OmniScrape/0.3 (+https://github.com/Z-MarkUs/OmniScrape)"
    render_timeout_ms: int = 15_000
    max_render_requests: int = 128
    max_render_nodes: int = 50_000
    provider_timeout_seconds: float = 30.0
    auto_llm_threshold: float = 0.72
    # Keep new options after the original positional fields for backward
    # compatibility; callers should still prefer keyword arguments.
    outbound_allowed_hosts: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.enable_api_rendering, bool):
            raise ValueError("enable_api_rendering must be a boolean.")
        _require_int(
            "max_concurrency",
            self.max_concurrency,
            minimum=1,
            maximum=MAX_TASK_CAPACITY,
        )
        _require_int(
            "max_render_concurrency",
            self.max_render_concurrency,
            minimum=1,
            maximum=2,
        )
        for name in (
            "queue_timeout_seconds",
            "request_body_timeout_seconds",
            "connect_timeout_seconds",
            "read_timeout_seconds",
            "fetch_timeout_seconds",
            "provider_timeout_seconds",
        ):
            _require_finite_float(name, getattr(self, name))
        _require_int(
            "max_response_bytes",
            self.max_response_bytes,
            minimum=1_024,
            maximum=20_000_000,
        )
        _require_int("max_redirects", self.max_redirects, minimum=0, maximum=20)
        _require_int("render_timeout_ms", self.render_timeout_ms, minimum=100, maximum=120_000)
        _require_int("max_render_requests", self.max_render_requests, minimum=1, maximum=1_024)
        _require_int("max_render_nodes", self.max_render_nodes, minimum=1, maximum=1_000_000)
        if (
            isinstance(self.auto_llm_threshold, bool)
            or not isinstance(self.auto_llm_threshold, (int, float))
            or not math.isfinite(float(self.auto_llm_threshold))
            or not 0 <= float(self.auto_llm_threshold) <= 1
        ):
            raise ValueError("auto_llm_threshold must be finite and between 0 and 1.")
        if not isinstance(self.user_agent, str) or not self.user_agent.strip():
            raise ValueError("user_agent must be a non-empty string.")
        if not isinstance(self.openai_model, str) or not self.openai_model.strip():
            raise ValueError("openai_model must be a non-empty string.")
        if self.allowed_hosts is not None:
            if not isinstance(self.allowed_hosts, tuple):
                raise ValueError("allowed_hosts must be a tuple of explicit authorities.")
            _normalize_host_authorities(self.allowed_hosts)
        if self.outbound_allowed_hosts is not None:
            if not isinstance(self.outbound_allowed_hosts, tuple):
                raise ValueError("outbound_allowed_hosts must be a tuple of explicit authorities.")
            object.__setattr__(
                self,
                "outbound_allowed_hosts",
                _normalize_outbound_host_authorities(self.outbound_allowed_hosts),
            )
        if self.enable_api_rendering and not self.outbound_allowed_hosts:
            raise ValueError(
                "OMNISCRAPE_ENABLE_API_RENDERING requires a non-empty "
                "OMNISCRAPE_OUTBOUND_ALLOWED_HOSTS policy."
            )
        if self.api_key is not None and (
            not isinstance(self.api_key, str)
            or not self.api_key
            or self.api_key != self.api_key.strip()
            or any(ord(character) < 33 or ord(character) > 126 for character in self.api_key)
        ):
            raise ValueError("api_key must contain only printable ASCII without whitespace.")

    @classmethod
    def from_env(cls, values: Mapping[str, str] | None = None) -> Settings:
        env = process_environ if values is None else values
        threshold = _positive_float(env.get("OMNISCRAPE_AUTO_LLM_THRESHOLD"), 0.72)
        if threshold > 1:
            threshold = 0.72
        return cls(
            api_key=env.get("OMNISCRAPE_API_KEY") or None,
            allowed_hosts=_allowed_hosts(env.get("OMNISCRAPE_ALLOWED_HOSTS")),
            outbound_allowed_hosts=_outbound_allowed_hosts(
                env.get("OMNISCRAPE_OUTBOUND_ALLOWED_HOSTS")
            ),
            enable_api_rendering=_strict_env_bool(
                "OMNISCRAPE_ENABLE_API_RENDERING",
                env.get("OMNISCRAPE_ENABLE_API_RENDERING"),
                False,
            ),
            openai_api_key=env.get("OPENAI_API_KEY") or None,
            openai_model=env.get("OMNISCRAPE_OPENAI_MODEL", "gpt-5.6-luna"),
            max_concurrency=_positive_int(
                env.get("OMNISCRAPE_MAX_CONCURRENCY"), 8, maximum=MAX_TASK_CAPACITY
            ),
            max_render_concurrency=_strict_env_int(
                "OMNISCRAPE_MAX_RENDER_CONCURRENCY",
                env.get("OMNISCRAPE_MAX_RENDER_CONCURRENCY"),
                2,
                minimum=1,
                maximum=2,
            ),
            queue_timeout_seconds=_positive_float(env.get("OMNISCRAPE_QUEUE_TIMEOUT_SECONDS"), 5.0),
            request_body_timeout_seconds=_positive_float(
                env.get("OMNISCRAPE_REQUEST_BODY_TIMEOUT_SECONDS"), 5.0
            ),
            connect_timeout_seconds=_positive_float(
                env.get("OMNISCRAPE_CONNECT_TIMEOUT_SECONDS"), 5.0
            ),
            read_timeout_seconds=_positive_float(env.get("OMNISCRAPE_READ_TIMEOUT_SECONDS"), 15.0),
            fetch_timeout_seconds=_positive_float(
                env.get("OMNISCRAPE_FETCH_TIMEOUT_SECONDS"), 30.0
            ),
            max_response_bytes=_positive_int(
                env.get("OMNISCRAPE_MAX_RESPONSE_BYTES"),
                2_000_000,
                minimum=1024,
                maximum=20_000_000,
            ),
            max_redirects=_positive_int(
                env.get("OMNISCRAPE_MAX_REDIRECTS"), 5, minimum=0, maximum=20
            ),
            user_agent=env.get(
                "OMNISCRAPE_USER_AGENT",
                "OmniScrape/0.3 (+https://github.com/Z-MarkUs/OmniScrape)",
            ),
            render_timeout_ms=_positive_int(
                env.get("OMNISCRAPE_RENDER_TIMEOUT_MS"),
                15_000,
                minimum=100,
                maximum=120_000,
            ),
            max_render_requests=_positive_int(
                env.get("OMNISCRAPE_MAX_RENDER_REQUESTS"), 128, maximum=1_024
            ),
            max_render_nodes=_positive_int(
                env.get("OMNISCRAPE_MAX_RENDER_NODES"), 50_000, maximum=1_000_000
            ),
            provider_timeout_seconds=_positive_float(
                env.get("OMNISCRAPE_PROVIDER_TIMEOUT_SECONDS"), 30.0
            ),
            auto_llm_threshold=threshold,
        )
