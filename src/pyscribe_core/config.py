"""Configuration management with validation and defaults."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Self

import yaml

logger = logging.getLogger(__name__)

DEFAULT_CONFIG: dict[str, Any] = {
    "skills": {
        "sources": [
            {
                "name": "antigravity-awesome-skills",
                "url": "https://github.com/sickn33/antigravity-awesome-skills",
                "branch": "main",
            }
        ],
        "aliases": {},
    },
    "defaults": {
        "author": "Your Name",
        "license": "MIT",
    },
    "http": {
        "timeout_seconds": 15,
        "max_retries": 3,
        "backoff_factor": 1.0,
    },
}


@dataclass(frozen=True)
class SkillSource:
    """GitHub repository source for skills."""

    name: str
    url: str
    branch: str = "main"

    @property
    def api_base_url(self) -> str:
        return self.url.replace("github.com", "api.github.com/repos")

    @property
    def raw_base_url(self) -> str:
        raw_path = self.url.replace("github.com", "raw.githubusercontent.com")
        return f"{raw_path}/{self.branch}"


@dataclass(frozen=True)
class HttpConfig:
    """HTTP client configuration."""

    timeout_seconds: float = 15.0
    max_retries: int = 3
    backoff_factor: float = 1.0


@dataclass
class PyScribeConfig:
    """Root configuration container."""

    skill_sources: list[SkillSource] = field(default_factory=list)
    skill_aliases: dict[str, str] = field(default_factory=dict)
    defaults: dict[str, str] = field(default_factory=dict)
    http: HttpConfig = field(default_factory=HttpConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        skills = data.get("skills", {})
        sources = skills.get("sources", [])
        skill_sources = [
            SkillSource(
                name=s["name"],
                url=s["url"],
                branch=s.get("branch", "main"),
            )
            for s in sources
        ]

        http_data = data.get("http", {})

        return cls(
            skill_sources=skill_sources,
            skill_aliases=skills.get("aliases", {}),
            defaults=data.get("defaults", {}),
            http=HttpConfig(
                timeout_seconds=http_data.get("timeout_seconds", 15),
                max_retries=http_data.get("max_retries", 3),
                backoff_factor=http_data.get("backoff_factor", 1.0),
            ),
        )

    @classmethod
    def from_yaml(cls, path: Path) -> Self:
        if not path.exists():
            logger.debug("Config not found at %s, using defaults", path)
            return cls.from_dict(DEFAULT_CONFIG)

        try:
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            merged = _deep_merge(DEFAULT_CONFIG, data)
            return cls.from_dict(merged)
        except (yaml.YAMLError, OSError) as e:
            logger.warning("Failed to parse config at %s: %s, using defaults", path, e)
            return cls.from_dict(DEFAULT_CONFIG)

    @classmethod
    def defaults(cls) -> Self:
        return cls.from_dict(DEFAULT_CONFIG)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
