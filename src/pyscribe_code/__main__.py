"""Main entry point for PyScribe Code MCP server."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from pathlib import Path

from mcp.server.stdio import stdio_server

from pyscribe_code.managers.api_verifier import APIVerifier
from pyscribe_code.managers.graph_analyzer import GraphAnalyzer
from pyscribe_code.managers.sandbox_validator import SandboxValidator
from pyscribe_code.managers.skill_manager import SkillManager
from pyscribe_code.managers.ts_sandbox_validator import TSSandboxValidator
from pyscribe_code.server import CodeContext, create_server
from pyscribe_core.config import PyScribeConfig

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


def find_project_root() -> Path:
    return Path.cwd()


def find_config(project_root: Path) -> Path:
    return project_root / ".agent" / "config.yaml"


async def run_server(config_path: Path, project_root: Path) -> None:
    config = PyScribeConfig.from_yaml(config_path)
    code_dir = project_root / ".agent" / "code"
    code_dir.mkdir(parents=True, exist_ok=True)
    skills_dir = project_root / ".agent" / "skills"

    graph_db_path = code_dir / "graph.sqlite"
    graph_analyzer = GraphAnalyzer(project_root, graph_db_path)

    skill_manager = SkillManager(config, skills_dir)
    api_verifier = APIVerifier(project_root)
    sandbox_validator = SandboxValidator(project_root=project_root)
    ts_sandbox_validator = TSSandboxValidator(project_root=project_root)

    ctx = CodeContext(
        config=config,
        graph_analyzer=graph_analyzer,
        api_verifier=api_verifier,
        skill_manager=skill_manager,
        sandbox_validator=sandbox_validator,
        ts_sandbox_validator=ts_sandbox_validator,
        project_root=project_root,
    )

    server = create_server(ctx)

    logger.info("PyScribe Code server starting (project: %s)", project_root)
    logger.info("Graph DB: %s", graph_db_path)
    logger.info("Skills dir: %s", skills_dir)

    shutdown_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("Shutdown signal received")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig_name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, sig_name, None)
        if sig:
            try:
                loop.add_signal_handler(sig, _signal_handler)
            except NotImplementedError:
                pass

    async with stdio_server() as (read_stream, write_stream):
        init_options = server.create_initialization_options()
        server_task = asyncio.create_task(
            server.run(read_stream, write_stream, init_options, raise_exceptions=True)
        )

        try:
            await shutdown_event.wait()
        except asyncio.CancelledError:
            pass

        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    logger.info("PyScribe Code server shut down gracefully")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="PyScribe Code MCP Server")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config.yaml (default: .agent/config.yaml in project root)",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Project root directory (default: current working directory)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    project_root = args.project_root or find_project_root()
    config_path = args.config or find_config(project_root)

    try:
        asyncio.run(run_server(config_path, project_root))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
