"""MCP server for PyScribe Code — code analysis, skills, and sandbox."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.types import CallToolResult, TextContent, Tool

from pyscribe_code import __version__
from pyscribe_code.managers.api_verifier import APIVerifier
from pyscribe_code.managers.graph_analyzer import GraphAnalyzer
from pyscribe_code.managers.sandbox_validator import SandboxValidator
from pyscribe_code.managers.skill_manager import SkillManager
from pyscribe_core.config import PyScribeConfig
from pyscribe_core.errors import PyScribeError

logger = logging.getLogger(__name__)


@dataclass
class CodeContext:
    """Shared context for all code tool handlers."""

    config: PyScribeConfig
    graph_analyzer: GraphAnalyzer
    api_verifier: APIVerifier
    skill_manager: SkillManager
    sandbox_validator: SandboxValidator
    project_root: Path


TOOLS: list[Tool] = [
    Tool(
        name="analyze-codebase-graph",
        description="Build and analyze the codebase call graph. Builds AST-based graph of function/class relationships. MUST be called before analyze-impact or find-callers.",
        inputSchema={
            "type": "object",
            "properties": {
                "scope": {"type": "string", "description": "Analysis scope: 'full' (entire project), 'file' (single file), 'module' (directory)", "enum": ["full", "file", "module"]},
                "path": {"type": "string", "description": "Specific file or directory path (required for file/module scope)", "maxLength": 500},
                "force_rebuild": {"type": "boolean", "description": "Force rebuild even if cached (default: false)"},
            },
            "additionalProperties": False,
        },
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False,
    ),
    Tool(
        name="analyze-impact",
        description="Analyze impact of changing a symbol. Returns transitive dependents, risk level, and affected test files. REQUIRES: analyze-codebase-graph must be called first.",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Symbol name to analyze (function, class, method)", "minLength": 1, "maxLength": 200},
                "change_type": {"type": "string", "description": "Type of change: 'modify', 'delete', 'rename'", "enum": ["modify", "delete", "rename"]},
                "max_depth": {"type": "integer", "description": "Maximum transitive depth to analyze (default: 3, max: 5)", "minimum": 1, "maximum": 5},
            },
            "required": ["symbol"],
            "additionalProperties": False,
        },
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False,
    ),
    Tool(
        name="find-callers",
        description="Find all callers of a specific function or method. REQUIRES: analyze-codebase-graph must be called first.",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Symbol name to find callers for", "minLength": 1, "maxLength": 200},
                "file_path": {"type": "string", "description": "Optional filter by file path", "maxLength": 500},
            },
            "required": ["symbol"],
            "additionalProperties": False,
        },
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False,
    ),
    Tool(
        name="verify-api",
        description="Verify if an API symbol exists in local packages or documentation. Checks local code first, then falls back to doc URLs and known libraries.",
        inputSchema={
            "type": "object",
            "properties": {
                "library": {"type": "string", "description": "Library or package name (e.g., 'fastapi', 'react', 'numpy')", "minLength": 1, "maxLength": 100},
                "symbol": {"type": "string", "description": "Symbol name to verify (function, class, method)", "minLength": 1, "maxLength": 200},
                "symbol_type": {"type": "string", "description": "Expected symbol type", "enum": ["function", "class", "method", "variable"]},
                "import_path": {"type": "string", "description": "Expected import path to validate", "maxLength": 500},
                "doc_url": {"type": "string", "description": "Optional documentation URL to check", "maxLength": 1000},
                "language": {"type": "string", "description": "Programming language. Auto-detected if not provided.", "enum": ["python", "typescript", "javascript"]},
            },
            "required": ["library", "symbol"],
            "additionalProperties": False,
        },
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True,
    ),
    Tool(
        name="list-skill-catalog",
        description="List ALL available skills from the configured GitHub skill repository.",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Maximum number of skills to return (default: 50, max: 200)", "minimum": 1, "maximum": 200},
                "offset": {"type": "integer", "description": "Number of skills to skip for pagination (default: 0)", "minimum": 0},
                "query": {"type": "string", "description": "Optional search query to filter skills by name", "minLength": 1, "maxLength": 100},
            },
            "additionalProperties": False,
        },
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False,
    ),
    Tool(
        name="get-skill-detail",
        description="Get detailed info about a specific skill: files, sizes, description. Use before downloading.",
        inputSchema={
            "type": "object",
            "properties": {
                "skill_name": {"type": "string", "description": "Exact skill name", "minLength": 1, "maxLength": 100, "pattern": "^[a-zA-Z0-9_-]+$"},
            },
            "required": ["skill_name"],
            "additionalProperties": False,
        },
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True,
    ),
    Tool(
        name="download-skill",
        description="Download an entire skill directory from GitHub. Preserves all files, subdirectories.",
        inputSchema={
            "type": "object",
            "properties": {
                "skill_name": {"type": "string", "description": "Skill name to download", "minLength": 1, "maxLength": 100, "pattern": "^[a-zA-Z0-9_-]+$"},
            },
            "required": ["skill_name"],
            "additionalProperties": False,
        },
        readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True,
    ),
    Tool(
        name="list-installed-skills",
        description="List all locally installed skills with file counts, sizes, and file lists.",
        inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False,
    ),
    Tool(
        name="sandbox-validate",
        description="ALWAYS call this before writing Python code to disk. Validates syntax, imports, lint, types, and deprecations. If can_write is false, fix reported issues before writing.",
        inputSchema={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "The Python code to validate"},
                "file_path": {"type": "string", "description": "Intended file path, used for import resolution"},
                "python_version": {"type": "string", "description": "Target Python version, e.g. '3.12'"},
                "checks": {"type": "array", "items": {"type": "string"}, "description": "Which checks to run. Default: all"},
                "dependencies": {"type": "array", "items": {"type": "string"}, "description": "List of import names to verify exist"},
            },
            "required": ["code"],
            "additionalProperties": False,
        },
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False,
    ),
]


def create_server(ctx: CodeContext) -> Server:
    """Create and configure the MCP server with code tool handlers."""

    server = Server("pyscribe-code")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return TOOLS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
        start = time.monotonic()
        logger.info("Tool call: %s", name)
        try:
            handler = _get_handler(name)
            result = await handler(ctx, arguments)
            elapsed = time.monotonic() - start
            logger.info("Tool %s completed in %.2fs", name, elapsed)
            return CallToolResult(content=[TextContent(type="text", text=result)])
        except PyScribeError as e:
            elapsed = time.monotonic() - start
            logger.warning("Tool %s error after %.2fs: %s", name, elapsed, e)
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: {e}")],
                isError=True,
            )
        except Exception as e:
            elapsed = time.monotonic() - start
            logger.exception("Tool %s crashed after %.2fs", name, elapsed)
            return CallToolResult(
                content=[TextContent(type="text", text=f"Internal error: {e}")],
                isError=True,
            )

    return server


def _get_handler(name: str):
    match name:
        case "analyze-codebase-graph":
            return handle_analyze_codebase_graph
        case "analyze-impact":
            return handle_analyze_impact
        case "find-callers":
            return handle_find_callers
        case "verify-api":
            return handle_verify_api
        case "list-skill-catalog":
            return handle_list_skill_catalog
        case "get-skill-detail":
            return handle_get_skill_detail
        case "download-skill":
            return handle_download_skill
        case "list-installed-skills":
            return handle_list_installed_skills
        case "sandbox-validate":
            return handle_sandbox_validate
        case _:
            raise PyScribeError(f"Unknown tool: {name}", recoverable=False)


async def handle_analyze_codebase_graph(ctx: CodeContext, args: dict[str, Any]) -> str:
    scope = args.get("scope", "full")
    path = args.get("path", "")
    force_rebuild = args.get("force_rebuild", False)

    result = ctx.graph_analyzer.build_graph(
        scope=scope,
        path=path if path else None,
        force_rebuild=force_rebuild,
    )

    if "error" in result:
        raise PyScribeError(result["error"], recoverable=True)

    lines = [
        "Codebase Graph Analysis:",
        f"  Total nodes (functions/classes): {result['total_nodes']}",
        f"  Total edges (call relationships): {result['total_edges']}",
    ]

    if result.get("hotspots"):
        lines.append("\nTop Hotspots (most called):")
        for h in result["hotspots"][:5]:
            lines.append(f"  - {h['symbol']} ({h['type']}) in {h['file']} - {h['caller_count']} callers")

    if result.get("module_dependencies"):
        lines.append("\nModule Dependencies:")
        for dep in result["module_dependencies"][:10]:
            lines.append(f"  - {dep['source_file']} -> {dep['target_file']} ({dep['call_count']} calls)")

    return "\n".join(lines)


async def handle_analyze_impact(ctx: CodeContext, args: dict[str, Any]) -> str:
    symbol = args.get("symbol", "").strip()
    change_type = args.get("change_type", "modify")
    max_depth = args.get("max_depth", 3)

    if not symbol:
        raise PyScribeError("'symbol' parameter is required", recoverable=True)

    if ctx.graph_analyzer.is_graph_empty():
        return (
            "Error: The codebase graph is empty. "
            "You MUST call 'analyze-codebase-graph' with scope='full' first "
            "to build the graph before analyzing impact.\n\n"
            "Suggested call: analyze-codebase-graph(scope='full')"
        )

    result = ctx.graph_analyzer.analyze_impact(
        symbol=symbol,
        change_type=change_type,
        max_depth=max_depth,
    )

    lines = [
        f"Impact Analysis: {symbol}",
        f"Change type: {result['change_type']}",
        f"Risk level: {result['risk_level'].upper()}",
        f"Direct callers: {result['direct_callers']}",
        f"Transitive dependents: {result['transitive_dependents']}",
        f"Impact ratio: {result['impact_ratio']:.1%}",
    ]

    if result.get("test_files"):
        lines.append("\nAffected test files:")
        for tf in result["test_files"][:10]:
            lines.append(f"  - {tf}")

    if result.get("dependents"):
        lines.append(f"\nTransitive dependents (depth <= {max_depth}):")
        for dep in result["dependents"][:15]:
            lines.append(f"  - {dep['caller']} (depth {dep['depth']})")

    return "\n".join(lines)


async def handle_find_callers(ctx: CodeContext, args: dict[str, Any]) -> str:
    symbol = args.get("symbol", "").strip()
    file_path = args.get("file_path", "")

    if not symbol:
        raise PyScribeError("'symbol' parameter is required", recoverable=True)

    if ctx.graph_analyzer.is_graph_empty():
        return (
            "Error: The codebase graph is empty. "
            "You MUST call 'analyze-codebase-graph' with scope='full' first."
        )

    result = ctx.graph_analyzer.find_callers(
        symbol=symbol,
        file_path=file_path if file_path else None,
    )

    lines = [
        f"Callers of '{symbol}':",
        f"Total callers: {result['caller_count']}",
    ]

    if result.get("callers"):
        lines.append("\nCallers:")
        for c in result["callers"]:
            lines.append(f"  - {c['caller']} ({c['caller_type']}) in {c['caller_file']}:{c['caller_line']}")

    if not result["callers"]:
        lines.append("\nNo callers found. This symbol may be unused or called dynamically.")

    return "\n".join(lines)


async def handle_verify_api(ctx: CodeContext, args: dict[str, Any]) -> str:
    library = args.get("library", "").strip()
    symbol = args.get("symbol", "").strip()
    symbol_type = args.get("symbol_type", "")
    import_path = args.get("import_path", "")
    doc_url = args.get("doc_url", "")
    language = args.get("language", "")

    if not library:
        raise PyScribeError("'library' parameter is required", recoverable=True)
    if not symbol:
        raise PyScribeError("'symbol' parameter is required", recoverable=True)

    result = ctx.api_verifier.verify(
        library=library,
        symbol=symbol,
        symbol_type=symbol_type,
        import_path=import_path,
        doc_url=doc_url,
        language=language,
    )

    lines = [f"API Verification: {symbol} in {library}", f"Status: {result['status']}", ""]

    if result["status"] == "FOUND":
        lines.append(f"Source: {result.get('source', 'unknown')}")
        if result.get("signature"):
            lines.append(f"Signature: {result['signature']}")
        if result.get("file_path"):
            lines.append(f"File: {result['file_path']}")
        if result.get("line_number"):
            lines.append(f"Line: {result['line_number']}")
        if result.get("import_path"):
            lines.append(f"Import: {result['import_path']}")
    else:
        lines.append(f"Message: {result.get('message', 'Symbol not found')}")
        if result.get("similar"):
            lines.append("\nSimilar symbols:")
            for sim in result["similar"]:
                lines.append(f"  - {sim}")

    return "\n".join(lines)


async def handle_list_skill_catalog(ctx: CodeContext, args: dict[str, Any]) -> str:
    limit = min(args.get("limit", 50), 200)
    offset = max(args.get("offset", 0), 0)
    query = args.get("query", "").strip().lower()

    catalog = await ctx.skill_manager.list_catalog()

    if not catalog:
        raise PyScribeError("Could not fetch skill catalog. Check network and GitHub repo configuration.", recoverable=True)

    installed_names = {s["name"] for s in ctx.skill_manager.list_installed()}

    filtered = catalog
    if query:
        filtered = [s for s in catalog if query in s["name"].lower()]

    total = len(filtered)
    paginated = filtered[offset:offset + limit]

    lines = [f"Available skills ({total} total, showing {len(paginated)}):\n"]
    for skill in sorted(paginated, key=lambda s: s["name"]):
        status = "[INSTALLED]" if skill["name"] in installed_names else "[available]"
        lines.append(f"- **{skill['name']}** {status}")
        if desc := skill.get("description"):
            lines.append(f"  {desc}")

    if offset + limit < total:
        lines.append(f"\n... use offset={offset + limit} to see more skills")

    return "\n".join(lines)


async def handle_get_skill_detail(ctx: CodeContext, args: dict[str, Any]) -> str:
    skill_name = args.get("skill_name", "").strip()
    if not skill_name:
        raise PyScribeError("'skill_name' parameter is required", recoverable=True)

    try:
        info = await ctx.skill_manager.get_skill_info(skill_name)
    except Exception as e:
        raise PyScribeError(f"Could not find skill '{skill_name}': {e}", recoverable=True)

    status = "INSTALLED" if info.is_installed else "NOT INSTALLED"
    lines = [
        f"Skill: {info.name} [{status}]",
        f"Source: {info.source}",
        f"Description: {info.description or 'N/A'}",
        f"Files: {len(info.files)}",
        f"Total size: {info.total_size:,} bytes",
    ]

    if info.is_installed:
        lines.append(f"Location: {info.install_path}")

    if info.files:
        lines.append("\nFiles:")
        for f in info.files:
            lines.append(f"  - {f.relative_path} ({f.size:,} bytes)")

    return "\n".join(lines)


async def handle_download_skill(ctx: CodeContext, args: dict[str, Any]) -> str:
    skill_name = args.get("skill_name", "").strip()
    if not skill_name:
        raise PyScribeError("'skill_name' parameter is required", recoverable=True)

    result = await ctx.skill_manager.download(skill_name)

    return (
        f"Successfully downloaded skill '{result['skill']}'\n"
        f"Source: {result['source']}\n"
        f"Location: {result['path']}\n"
        f"Files downloaded: {result['file_count']}"
    )


async def handle_list_installed_skills(ctx: CodeContext, args: dict[str, Any]) -> str:
    skills = ctx.skill_manager.list_installed()

    if not skills:
        return (
            "No skills installed yet.\n\n"
            "Use 'list-skill-catalog' to see available skills, then 'download-skill <name>' to install.\n\n"
            f"Skills directory: {ctx.project_root / '.agent' / 'skills'}"
        )

    total_files = sum(s["file_count"] for s in skills)
    total_size = sum(s["total_size"] for s in skills)

    lines = [
        f"Installed skills ({len(skills)} total, {total_files} files, {total_size:,} bytes):\n",
        f"Skills directory: {ctx.project_root / '.agent' / 'skills'}\n",
    ]

    for skill in skills:
        lines.append(f"### {skill['name']}")
        lines.append(f"  Files: {skill['file_count']} | Size: {skill['total_size']:,} bytes")
        if desc := skill.get("description"):
            lines.append(f"  Description: {desc}")
        lines.append(f"  Path: {skill['path']}")
        lines.append("  Files:")
        for f in skill["files"]:
            lines.append(f"    - {f}")
        lines.append("")

    return "\n".join(lines)


async def handle_sandbox_validate(ctx: CodeContext, args: dict[str, Any]) -> str:
    code = args.get("code", "")
    file_path = args.get("file_path", "")
    python_version = args.get("python_version", "")
    checks = args.get("checks")
    dependencies = args.get("dependencies")

    if not code:
        raise PyScribeError("'code' parameter is required", recoverable=True)

    result = ctx.sandbox_validator.validate(
        code=code,
        file_path=file_path,
        python_version=python_version if python_version else None,
        checks=checks,
        dependencies=dependencies,
    )

    lines = [
        f"Sandbox Validation: {result['file_path']}",
        f"Status: {result['status'].upper()}",
        f"Can write: {result['can_write']}",
        f"Summary: {result['summary']}",
        "",
    ]

    for check_result in result["results"]:
        status_icon = "PASS" if check_result["status"] == "pass" else ("FAIL" if check_result["status"] == "fail" else "WARN")
        lines.append(f"[{status_icon}] {check_result['check']}")
        for issue in check_result["issues"]:
            sev = "ERROR" if issue["severity"] == "error" else "WARNING"
            loc = f" line {issue['line']}" if issue["line"] else ""
            lines.append(f"  {sev}{loc}: [{issue['code']}] {issue['message']}")
        lines.append("")

    return "\n".join(lines)
