"""Skill acquisition manager: discover, download, and manage multi-file skill directories from GitHub."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pyscribe_core.cache import LRUCache
from pyscribe_core.config import PyScribeConfig, SkillSource
from pyscribe_core.errors import SkillNotFoundError
from pyscribe_core.http import HttpClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SkillFile:
    """A single file within a skill directory."""

    name: str
    relative_path: str
    size: int
    download_url: str
    is_directory: bool = False


@dataclass
class SkillInfo:
    """Complete information about a skill."""

    name: str
    source: str
    description: str = ""
    files: list[SkillFile] = field(default_factory=list)
    total_size: int = 0
    is_installed: bool = False
    install_path: str = ""


class SkillManager:
    """Manages skill discovery, download, and local storage."""

    def __init__(self, config: PyScribeConfig, skills_dir: Path) -> None:
        self._config = config
        self._skills_dir = skills_dir
        self._skills_dir.mkdir(parents=True, exist_ok=True)
        self._catalog_cache = LRUCache(maxsize=8)
        self._skill_tree_cache = LRUCache(maxsize=256)

    async def list_catalog(self) -> list[dict[str, str]]:
        all_skills: list[dict[str, str]] = []

        for source in self._config.skill_sources:
            skills = await self._fetch_skill_catalog(source)
            all_skills.extend(skills)

        logger.info("Skill catalog: %d skills from %d sources", len(all_skills), len(self._config.skill_sources))
        return all_skills

    async def get_skill_info(self, skill_name: str) -> SkillInfo:
        for source in self._config.skill_sources:
            if info := await self._fetch_skill_detail(skill_name, source):
                local_path = self._skills_dir / skill_name
                info.is_installed = local_path.exists() and (local_path / "SKILL.md").exists()
                if info.is_installed:
                    info.install_path = str(local_path)
                return info

        raise SkillNotFoundError(skill_name)

    async def download(self, skill_name: str) -> dict[str, Any]:
        for source in self._config.skill_sources:
            result = await self._try_download_skill(skill_name, source)
            if result:
                return result

        raise SkillNotFoundError(skill_name, source=str(self._config.skill_sources))

    def list_installed(self) -> list[dict[str, Any]]:
        installed: list[dict[str, Any]] = []

        if not self._skills_dir.exists():
            return installed

        for skill_dir in sorted(self._skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            files = list(skill_dir.rglob("*"))
            file_count = sum(1 for f in files if f.is_file())
            total_size = sum(f.stat().st_size for f in files if f.is_file())

            description = self._extract_description(skill_md)

            installed.append({
                "name": skill_dir.name,
                "path": str(skill_dir),
                "file_count": file_count,
                "total_size": total_size,
                "description": description,
                "files": [str(f.relative_to(skill_dir)) for f in sorted(files) if f.is_file()],
            })

        return installed

    def read_file(self, skill_name: str, file_path: str) -> str | None:
        skill_dir = (self._skills_dir / skill_name).resolve()
        target = (skill_dir / file_path).resolve()

        if not str(target).startswith(str(skill_dir)):
            logger.warning("Path traversal blocked: %s", file_path)
            return None

        if not target.exists() or not target.is_file():
            return None

        try:
            return target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

    def read_skill_main(self, skill_name: str) -> str | None:
        return self.read_file(skill_name, "SKILL.md")

    def get_skill_tree(self, skill_name: str) -> list[str] | None:
        skill_dir = self._skills_dir / skill_name
        if not skill_dir.exists():
            return None

        return [
            str(f.relative_to(skill_dir))
            for f in sorted(skill_dir.rglob("*"))
            if f.is_file()
        ]

    async def _fetch_skill_catalog(self, source: SkillSource) -> list[dict[str, str]]:
        cache_key = f"catalog:{source.name}"
        if cached := self._catalog_cache.get(cache_key):
            return cached

        api_url = source.url.replace("github.com", "api.github.com/repos")
        skills_path = f"{api_url}/contents/skills"

        try:
            async with HttpClient(self._config.http) as client:
                raw = await client.get(skills_path)
                items = json.loads(raw)
        except Exception as e:
            logger.warning("Failed to fetch catalog from %s: %s", source.name, e)
            return []

        skills: list[dict[str, str]] = []
        for item in items:
            if item.get("type") != "dir":
                continue

            name = item["name"]
            if name.startswith("."):
                continue

            desc = self._parse_skill_description_from_name(name)
            skills.append({
                "name": name,
                "source": source.name,
                "description": desc,
                "url": item.get("html_url", ""),
            })

        self._catalog_cache.put(cache_key, skills)
        return skills

    async def _fetch_skill_detail(self, skill_name: str, source: SkillSource) -> SkillInfo | None:
        api_url = source.url.replace("github.com", "api.github.com/repos")
        skill_url = f"{api_url}/contents/skills/{skill_name}"

        try:
            async with HttpClient(self._config.http) as client:
                raw = await client.get(skill_url)
                items = json.loads(raw)
        except Exception as e:
            logger.debug("Skill %s not found in %s: %s", skill_name, source.name, e)
            return None

        files: list[SkillFile] = []
        total_size = 0
        description = ""

        for item in items:
            if item["type"] == "file":
                sf = SkillFile(
                    name=item["name"],
                    relative_path=item["name"],
                    size=item.get("size", 0),
                    download_url=item.get("download_url", ""),
                )
                files.append(sf)
                total_size += sf.size

                if item["name"] == "SKILL.md":
                    try:
                        async with HttpClient(self._config.http) as client:
                            content = await client.get(item["download_url"])
                            description = self._extract_description_from_content(content)
                    except Exception:
                        pass

        return SkillInfo(
            name=skill_name,
            source=source.name,
            description=description,
            files=files,
            total_size=total_size,
        )

    async def _try_download_skill(self, skill_name: str, source: SkillSource) -> dict[str, Any] | None:
        api_url = source.url.replace("github.com", "api.github.com/repos")
        skill_url = f"{api_url}/contents/skills/{skill_name}"

        try:
            async with HttpClient(self._config.http) as client:
                raw = await client.get(skill_url)
                items = json.loads(raw)
        except Exception as e:
            logger.debug("Cannot download %s from %s: %s", skill_name, source.name, e)
            return None

        skill_dir = self._skills_dir / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)

        file_count = 0
        dirs_to_create: list[tuple[Path, dict]] = []

        for item in items:
            if item["type"] == "dir":
                dirs_to_create.append((skill_dir / item["name"], item))
            elif item["type"] == "file":
                try:
                    async with HttpClient(self._config.http) as client:
                        content = await client.get(item["download_url"])
                except Exception as e:
                    logger.warning("Failed to download %s/%s: %s", skill_name, item["name"], e)
                    continue

                target = skill_dir / item["name"]
                target.write_text(content, encoding="utf-8")
                file_count += 1
                logger.info("Downloaded %s/%s", skill_name, item["name"])

        for d, dir_item in dirs_to_create:
            d.mkdir(parents=True, exist_ok=True)
            await self._download_directory_contents(d, dir_item, source)

        self._catalog_cache.invalidate(f"catalog:{source.name}")

        return {
            "status": "success",
            "skill": skill_name,
            "source": source.name,
            "path": str(skill_dir),
            "file_count": file_count,
        }

    async def _download_directory_contents(self, parent_dir: Path, dir_item: dict, source: SkillSource) -> int:
        api_url = source.url.replace("github.com", "api.github.com/repos")
        rel_path = parent_dir.relative_to(self._skills_dir)
        dir_api = f"{api_url}/contents/skills/{rel_path}"

        try:
            async with HttpClient(self._config.http) as client:
                raw = await client.get(dir_api)
                items = json.loads(raw)
        except Exception as e:
            logger.warning("Failed to list directory %s: %s", dir_item["name"], e)
            return 0

        file_count = 0
        for item in items:
            if item["type"] == "dir":
                subdir = parent_dir / item["name"]
                subdir.mkdir(parents=True, exist_ok=True)
                file_count += await self._download_directory_contents(subdir, item, source)
            elif item["type"] == "file":
                try:
                    async with HttpClient(self._config.http) as client:
                        content = await client.get(item["download_url"])
                except Exception as e:
                    logger.warning("Failed to download %s: %s", item["name"], e)
                    continue

                target = parent_dir / item["name"]
                target.write_text(content, encoding="utf-8")
                file_count += 1
                logger.info("Downloaded %s", target.relative_to(self._skills_dir))

        return file_count

    @staticmethod
    def _parse_skill_description_from_name(name: str) -> str:
        return name.replace("-", " ").replace("_", " ").title()

    @staticmethod
    def _extract_description(skill_md: Path) -> str:
        try:
            content = skill_md.read_text(encoding="utf-8")
            return SkillManager._extract_description_from_content(content)
        except Exception:
            return ""

    @staticmethod
    def _extract_description_from_content(content: str) -> str:
        if "description:" in content:
            for line in content.split("\n")[:20]:
                if line.startswith("description:"):
                    return line.split(":", 1)[1].strip().strip('"').strip("'")[:120]
        first_heading = content.find("# ")
        if first_heading != -1:
            end = content.find("\n", first_heading)
            if end != -1:
                return content[first_heading + 2:end].strip()[:120]
        return ""
