"""Tests for documentation files added/modified in PR: refactor README into separate docs."""

from __future__ import annotations

import re
from pathlib import Path

import pytest


# Root of the repository (one level up from the tests/ directory)
REPO_ROOT = Path(__file__).parent.parent


@pytest.fixture
def readme_content() -> str:
    """Read README.md content."""
    return (REPO_ROOT / "README.md").read_text(encoding="utf-8")


@pytest.fixture
def vulnerabilities_content() -> str:
    """Read VULNERABILITIES.md content."""
    return (REPO_ROOT / "VULNERABILITIES.md").read_text(encoding="utf-8")


@pytest.fixture
def agents_content() -> str:
    """Read docs/agents.md content."""
    return (REPO_ROOT / "docs" / "agents.md").read_text(encoding="utf-8")


@pytest.fixture
def tools_content() -> str:
    """Read docs/tools.md content."""
    return (REPO_ROOT / "docs" / "tools.md").read_text(encoding="utf-8")


@pytest.fixture
def installation_content() -> str:
    """Read docs/installation.md content."""
    return (REPO_ROOT / "docs" / "installation.md").read_text(encoding="utf-8")


@pytest.fixture
def architecture_content() -> str:
    """Read docs/architecture.md content."""
    return (REPO_ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")


@pytest.fixture
def development_content() -> str:
    """Read docs/development.md content."""
    return (REPO_ROOT / "docs" / "development.md").read_text(encoding="utf-8")


class TestDocumentationFilesExist:
    """Verify all documentation files introduced in this PR exist on disk."""

    def test_readme_exists(self) -> None:
        """README.md must exist at the repository root."""
        assert (REPO_ROOT / "README.md").is_file()

    def test_vulnerabilities_exists(self) -> None:
        """VULNERABILITIES.md must exist at the repository root."""
        assert (REPO_ROOT / "VULNERABILITIES.md").is_file()

    def test_docs_directory_exists(self) -> None:
        """docs/ directory must exist."""
        assert (REPO_ROOT / "docs").is_dir()

    def test_agents_doc_exists(self) -> None:
        """docs/agents.md must exist."""
        assert (REPO_ROOT / "docs" / "agents.md").is_file()

    def test_tools_doc_exists(self) -> None:
        """docs/tools.md must exist."""
        assert (REPO_ROOT / "docs" / "tools.md").is_file()

    def test_installation_doc_exists(self) -> None:
        """docs/installation.md must exist."""
        assert (REPO_ROOT / "docs" / "installation.md").is_file()

    def test_architecture_doc_exists(self) -> None:
        """docs/architecture.md must exist."""
        assert (REPO_ROOT / "docs" / "architecture.md").is_file()

    def test_development_doc_exists(self) -> None:
        """docs/development.md must exist."""
        assert (REPO_ROOT / "docs" / "development.md").is_file()

    def test_all_docs_are_nonempty(self) -> None:
        """Every documentation file must have non-zero content."""
        doc_files = [
            REPO_ROOT / "README.md",
            REPO_ROOT / "VULNERABILITIES.md",
            REPO_ROOT / "docs" / "agents.md",
            REPO_ROOT / "docs" / "tools.md",
            REPO_ROOT / "docs" / "installation.md",
            REPO_ROOT / "docs" / "architecture.md",
            REPO_ROOT / "docs" / "development.md",
        ]
        for path in doc_files:
            assert path.stat().st_size > 0, f"{path.name} is unexpectedly empty"


class TestReadme:
    """Tests for the refactored README.md."""

    def test_readme_has_documentation_section(self, readme_content: str) -> None:
        """README must contain a Documentation section heading."""
        assert "## Documentation" in readme_content

    def test_readme_links_to_agents_doc(self, readme_content: str) -> None:
        """README must link to docs/agents.md."""
        assert "docs/agents.md" in readme_content

    def test_readme_links_to_tools_doc(self, readme_content: str) -> None:
        """README must link to docs/tools.md."""
        assert "docs/tools.md" in readme_content

    def test_readme_links_to_installation_doc(self, readme_content: str) -> None:
        """README must link to docs/installation.md."""
        assert "docs/installation.md" in readme_content

    def test_readme_links_to_architecture_doc(self, readme_content: str) -> None:
        """README must link to docs/architecture.md."""
        assert "docs/architecture.md" in readme_content

    def test_readme_links_to_development_doc(self, readme_content: str) -> None:
        """README must link to docs/development.md."""
        assert "docs/development.md" in readme_content

    def test_readme_links_resolve_to_existing_files(self, readme_content: str) -> None:
        """Every markdown link target in README that points to docs/ must exist on disk."""
        # Extract markdown links of the form [text](path)
        link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
        for _text, target in link_pattern.findall(readme_content):
            if target.startswith("docs/"):
                resolved = REPO_ROOT / target
                assert resolved.is_file(), f"README links to '{target}' which does not exist"

    def test_readme_has_five_doc_links(self, readme_content: str) -> None:
        """README Documentation section must list exactly 5 doc links."""
        doc_links = re.findall(r"\(docs/[^)]+\.md\)", readme_content)
        assert len(doc_links) == 5

    def test_readme_has_quick_start_section(self, readme_content: str) -> None:
        """README must retain the Quick Start section."""
        assert "## Quick Start" in readme_content

    def test_readme_does_not_contain_old_tool_tables(self, readme_content: str) -> None:
        """Old verbose tool tables should have been moved to docs/tools.md, not remain in README."""
        # The old README contained inline tool parameter tables; they should now live in docs/
        assert "analyze-codebase-graph" not in readme_content or "docs/" in readme_content

    def test_readme_mentions_pyscribe_code(self, readme_content: str) -> None:
        """README must mention pyscribe-code (the package name)."""
        assert "pyscribe-code" in readme_content.lower() or "pyscribe_code" in readme_content.lower()


class TestVulnerabilitiesFile:
    """Tests for VULNERABILITIES.md bandit scan output."""

    def test_vulnerabilities_contains_run_header(self, vulnerabilities_content: str) -> None:
        """VULNERABILITIES.md must start with the bandit run header."""
        assert "Run started:" in vulnerabilities_content

    def test_vulnerabilities_has_test_results_section(self, vulnerabilities_content: str) -> None:
        """VULNERABILITIES.md must contain a Test results section."""
        assert "Test results:" in vulnerabilities_content

    def test_vulnerabilities_has_no_high_severity_issues(self, vulnerabilities_content: str) -> None:
        """There must be zero High severity issues in the scan results."""
        match = re.search(r"High:\s*(\d+)", vulnerabilities_content)
        assert match is not None, "Could not find High severity count in VULNERABILITIES.md"
        assert int(match.group(1)) == 0

    def test_vulnerabilities_has_two_medium_severity_issues(self, vulnerabilities_content: str) -> None:
        """There must be exactly 2 Medium severity issues."""
        match = re.search(r"Medium:\s*(\d+)", vulnerabilities_content)
        assert match is not None, "Could not find Medium severity count in VULNERABILITIES.md"
        assert int(match.group(1)) == 2

    def test_vulnerabilities_has_five_low_severity_issues(self, vulnerabilities_content: str) -> None:
        """There must be exactly 5 Low severity issues."""
        match = re.search(r"Low:\s*(\d+)", vulnerabilities_content)
        assert match is not None, "Could not find Low severity count in VULNERABILITIES.md"
        assert int(match.group(1)) == 5

    def test_vulnerabilities_references_graph_db(self, vulnerabilities_content: str) -> None:
        """VULNERABILITIES.md must reference graph_db.py as a flagged file."""
        assert "graph_db.py" in vulnerabilities_content

    def test_vulnerabilities_references_sandbox_validator(self, vulnerabilities_content: str) -> None:
        """VULNERABILITIES.md must reference sandbox_validator.py as a flagged file."""
        assert "sandbox_validator.py" in vulnerabilities_content

    def test_vulnerabilities_references_skill_manager(self, vulnerabilities_content: str) -> None:
        """VULNERABILITIES.md must reference skill_manager.py as a flagged file."""
        assert "skill_manager.py" in vulnerabilities_content

    def test_vulnerabilities_references_retry(self, vulnerabilities_content: str) -> None:
        """VULNERABILITIES.md must reference retry.py as a flagged file."""
        assert "retry.py" in vulnerabilities_content

    def test_vulnerabilities_mentions_sql_injection(self, vulnerabilities_content: str) -> None:
        """VULNERABILITIES.md must document the SQL injection finding (B608)."""
        assert "B608" in vulnerabilities_content
        assert "SQL" in vulnerabilities_content.upper() or "sql" in vulnerabilities_content

    def test_vulnerabilities_mentions_subprocess(self, vulnerabilities_content: str) -> None:
        """VULNERABILITIES.md must document subprocess-related findings (B603/B404)."""
        assert "B603" in vulnerabilities_content
        assert "B404" in vulnerabilities_content

    def test_vulnerabilities_has_code_scanned_metrics(self, vulnerabilities_content: str) -> None:
        """VULNERABILITIES.md must include the Code scanned metrics block."""
        assert "Code scanned:" in vulnerabilities_content
        assert "Total lines of code:" in vulnerabilities_content

    def test_vulnerabilities_has_run_metrics(self, vulnerabilities_content: str) -> None:
        """VULNERABILITIES.md must include the Run metrics summary."""
        assert "Run metrics:" in vulnerabilities_content
        assert "Total issues (by severity):" in vulnerabilities_content

    def test_vulnerabilities_zero_nosec_suppressions(self, vulnerabilities_content: str) -> None:
        """There must be zero #nosec suppressions in the scanned code."""
        match = re.search(r"Total lines skipped \(#nosec\):\s*(\d+)", vulnerabilities_content)
        assert match is not None
        assert int(match.group(1)) == 0

    def test_vulnerabilities_no_files_skipped(self, vulnerabilities_content: str) -> None:
        """No files should have been skipped during the scan."""
        assert "Files skipped (0):" in vulnerabilities_content

    # Boundary / negative regression test
    def test_vulnerabilities_does_not_report_undefined_severity(self, vulnerabilities_content: str) -> None:
        """Undefined severity count must be zero — no unclassified issues."""
        match = re.search(r"Undefined:\s*(\d+)", vulnerabilities_content)
        # There may be multiple Undefined lines; all should be 0
        all_matches = re.findall(r"Undefined:\s*(\d+)", vulnerabilities_content)
        assert all(int(v) == 0 for v in all_matches), "Found non-zero Undefined severity counts"


class TestAgentsDoc:
    """Tests for docs/agents.md MCP agent configuration documentation."""

    def test_agents_has_connect_your_agent_heading(self, agents_content: str) -> None:
        """agents.md must have a 'Connect Your Agent' heading."""
        assert "Connect Your Agent" in agents_content

    def test_agents_documents_cursor(self, agents_content: str) -> None:
        """agents.md must include a Cursor section."""
        assert "Cursor" in agents_content

    def test_agents_documents_claude_code(self, agents_content: str) -> None:
        """agents.md must include a Claude Code section."""
        assert "Claude Code" in agents_content

    def test_agents_documents_windsurf_cline(self, agents_content: str) -> None:
        """agents.md must include a Windsurf/Cline section."""
        assert "Windsurf" in agents_content
        assert "Cline" in agents_content

    def test_agents_documents_opencode(self, agents_content: str) -> None:
        """agents.md must include an OpenCode section."""
        assert "OpenCode" in agents_content

    def test_agents_documents_generic_mcp_agent(self, agents_content: str) -> None:
        """agents.md must include a section for any MCP-compatible agent."""
        assert "MCP-Compatible" in agents_content or "MCP Compatible" in agents_content

    def test_agents_all_configs_use_pyscribe_code_module(self, agents_content: str) -> None:
        """Every MCP config in agents.md must invoke the pyscribe_code module."""
        assert "pyscribe_code" in agents_content

    def test_agents_all_json_configs_use_python_command(self, agents_content: str) -> None:
        """All JSON MCP configurations must use 'python' as the command."""
        # Extract JSON code blocks
        json_blocks = re.findall(r"```json\n(.*?)```", agents_content, re.DOTALL)
        assert len(json_blocks) >= 3, "Expected at least 3 JSON config blocks in agents.md"
        for block in json_blocks:
            assert '"python"' in block or '"command"' in block

    def test_agents_cursor_config_has_workspace_folder(self, agents_content: str) -> None:
        """Cursor config must use ${workspaceFolder} as the cwd."""
        assert "${workspaceFolder}" in agents_content

    def test_agents_mentions_stdio_transport(self, agents_content: str) -> None:
        """agents.md must mention the stdio transport."""
        assert "stdio" in agents_content

    def test_agents_windsurf_config_has_required_fields(self, agents_content: str) -> None:
        """Windsurf/Cline config must include disabled and autoApprove fields."""
        assert '"disabled"' in agents_content
        assert '"autoApprove"' in agents_content

    # Negative / boundary test
    def test_agents_does_not_reference_nonexistent_modules(self, agents_content: str) -> None:
        """agents.md must not accidentally reference a wrong module name like 'pyscribe-code' in args."""
        # The args should use pyscribe_code (underscore), not pyscribe-code (hyphen)
        # Extract args arrays from JSON blocks
        args_matches = re.findall(r'"args":\s*\[([^\]]+)\]', agents_content)
        for args_str in args_matches:
            assert "pyscribe-code" not in args_str or "-m" not in args_str


class TestToolsDoc:
    """Tests for docs/tools.md tool descriptions and usage examples."""

    EXPECTED_TOOLS = [
        "analyze-codebase-graph",
        "analyze-impact",
        "find-callers",
        "verify-api",
        "sandbox-validate",
        "list-skill-catalog",
        "get-skill-detail",
        "download-skill",
        "list-installed-skills",
    ]

    def test_tools_claims_nine_tools(self, tools_content: str) -> None:
        """docs/tools.md must advertise exactly 9 tools."""
        assert "9" in tools_content
        assert "9 powerful tools" in tools_content

    def test_tools_lists_all_nine_tool_names(self, tools_content: str) -> None:
        """Every one of the 9 tool names must appear in docs/tools.md."""
        for tool in self.EXPECTED_TOOLS:
            assert tool in tools_content, f"Tool '{tool}' not documented in docs/tools.md"

    def test_tools_has_code_analysis_section(self, tools_content: str) -> None:
        """docs/tools.md must have a Code Analysis section."""
        assert "Code Analysis" in tools_content

    def test_tools_has_api_verification_section(self, tools_content: str) -> None:
        """docs/tools.md must have an API Verification section."""
        assert "API Verification" in tools_content

    def test_tools_has_code_validation_section(self, tools_content: str) -> None:
        """docs/tools.md must have a Code Validation section."""
        assert "Code Validation" in tools_content

    def test_tools_has_skill_management_section(self, tools_content: str) -> None:
        """docs/tools.md must have a Skill Management section."""
        assert "Skill Management" in tools_content

    def test_tools_has_usage_examples_section(self, tools_content: str) -> None:
        """docs/tools.md must include a Tool Usage Examples section."""
        assert "Tool Usage Examples" in tools_content or "Usage Examples" in tools_content

    def test_tools_has_typical_workflow_section(self, tools_content: str) -> None:
        """docs/tools.md must include a Typical Workflow section."""
        assert "Typical Workflow" in tools_content

    def test_tools_workflow_references_analyze_codebase_graph(self, tools_content: str) -> None:
        """Typical workflow must start with analyze-codebase-graph."""
        workflow_section = tools_content[tools_content.find("Typical Workflow"):]
        assert "analyze-codebase-graph" in workflow_section

    def test_tools_workflow_ends_with_write_guard(self, tools_content: str) -> None:
        """Typical workflow must include the can_write=true guard before writing."""
        assert "can_write" in tools_content

    def test_tools_verify_api_example_shows_language_param(self, tools_content: str) -> None:
        """verify-api usage example must show the optional language parameter."""
        assert '"language"' in tools_content or "language" in tools_content

    def test_tools_sandbox_validate_example_shows_checks_param(self, tools_content: str) -> None:
        """sandbox-validate usage example must show the checks parameter."""
        assert '"checks"' in tools_content

    def test_tools_analyze_codebase_graph_scope_values(self, tools_content: str) -> None:
        """Usage examples for analyze-codebase-graph must show full, file, and module scopes."""
        assert '"full"' in tools_content
        assert '"file"' in tools_content
        assert '"module"' in tools_content

    # Boundary: skill management tools each appear exactly as documented
    def test_tools_skill_management_tools_count(self, tools_content: str) -> None:
        """Exactly 4 skill management tools must be listed in the Skill Management table."""
        skill_tools = [
            "list-skill-catalog",
            "get-skill-detail",
            "download-skill",
            "list-installed-skills",
        ]
        for tool in skill_tools:
            assert tools_content.count(tool) >= 1


class TestInstallationDoc:
    """Tests for docs/installation.md installation and configuration documentation."""

    def test_installation_has_installation_heading(self, installation_content: str) -> None:
        """docs/installation.md must have an Installation heading."""
        assert "## Installation" in installation_content

    def test_installation_has_from_source_section(self, installation_content: str) -> None:
        """docs/installation.md must include a From Source section."""
        assert "From Source" in installation_content

    def test_installation_has_direct_install_section(self, installation_content: str) -> None:
        """docs/installation.md must include a Direct Install section."""
        assert "Direct Install" in installation_content or "pip install pyscribe" in installation_content

    def test_installation_pip_install_command(self, installation_content: str) -> None:
        """docs/installation.md must document pip install commands."""
        assert "pip install" in installation_content

    def test_installation_has_running_server_section(self, installation_content: str) -> None:
        """docs/installation.md must describe how to run the server."""
        assert "Running the Server" in installation_content

    def test_installation_dev_mode_uses_verbose_flag(self, installation_content: str) -> None:
        """Development mode section must reference the --verbose flag."""
        assert "--verbose" in installation_content

    def test_installation_production_mode_uses_entry_point(self, installation_content: str) -> None:
        """Production mode must document the pyscribe-code entry point."""
        assert "pyscribe-code" in installation_content

    def test_installation_has_config_reference_section(self, installation_content: str) -> None:
        """docs/installation.md must include a Configuration Reference section."""
        assert "Configuration Reference" in installation_content

    def test_installation_env_var_max_retries(self, installation_content: str) -> None:
        """PYSCRIBE_MAX_RETRIES env var must be documented with default 3."""
        assert "PYSCRIBE_MAX_RETRIES" in installation_content
        # Check default is 3
        idx = installation_content.find("PYSCRIBE_MAX_RETRIES")
        context = installation_content[idx : idx + 100]
        assert "3" in context

    def test_installation_env_var_cache_ttl(self, installation_content: str) -> None:
        """PYSCRIBE_CACHE_TTL env var must be documented with default 3600."""
        assert "PYSCRIBE_CACHE_TTL" in installation_content
        idx = installation_content.find("PYSCRIBE_CACHE_TTL")
        context = installation_content[idx : idx + 100]
        assert "3600" in context

    def test_installation_env_var_log_level(self, installation_content: str) -> None:
        """PYSCRIBE_LOG_LEVEL env var must be documented with default INFO."""
        assert "PYSCRIBE_LOG_LEVEL" in installation_content
        idx = installation_content.find("PYSCRIBE_LOG_LEVEL")
        context = installation_content[idx : idx + 100]
        assert "INFO" in context

    def test_installation_documents_three_env_vars(self, installation_content: str) -> None:
        """Exactly 3 environment variables must be documented."""
        env_vars = re.findall(r"`PYSCRIBE_[A-Z_]+`", installation_content)
        assert len(env_vars) == 3

    def test_installation_analyze_codebase_graph_params(self, installation_content: str) -> None:
        """Tool parameter table for analyze-codebase-graph must document scope, path, force_rebuild."""
        assert "analyze-codebase-graph" in installation_content
        for param in ("scope", "path", "force_rebuild"):
            assert param in installation_content

    def test_installation_analyze_impact_params(self, installation_content: str) -> None:
        """Tool parameter table for analyze-impact must document symbol, change_type, max_depth."""
        assert "analyze-impact" in installation_content
        for param in ("symbol", "change_type", "max_depth"):
            assert param in installation_content

    def test_installation_sandbox_validate_params(self, installation_content: str) -> None:
        """Tool parameter table for sandbox-validate must document code, file_path, checks."""
        assert "sandbox-validate" in installation_content
        for param in ("code", "file_path", "checks", "dependencies"):
            assert param in installation_content

    def test_installation_config_yaml_example_has_cache_section(self, installation_content: str) -> None:
        """The .pyscribe/config.yaml example must include a cache section."""
        assert "cache:" in installation_content

    def test_installation_config_yaml_ttl_matches_env_default(self, installation_content: str) -> None:
        """The config.yaml cache.ttl must match the documented PYSCRIBE_CACHE_TTL default of 3600."""
        assert "ttl: 3600" in installation_content

    # Negative / boundary test
    def test_installation_analyze_impact_symbol_is_required(self, installation_content: str) -> None:
        """The symbol parameter for analyze-impact must be marked as required (Yes)."""
        # Find the analyze-impact param table section
        idx = installation_content.find("analyze-impact")
        section = installation_content[idx : idx + 500]
        assert "**Yes**" in section or "Yes" in section


class TestArchitectureDoc:
    """Tests for docs/architecture.md system architecture and performance documentation."""

    def test_architecture_has_architecture_heading(self, architecture_content: str) -> None:
        """docs/architecture.md must have an Architecture heading."""
        assert "## Architecture" in architecture_content

    def test_architecture_diagram_mentions_mcp_protocol(self, architecture_content: str) -> None:
        """Architecture diagram must reference the MCP Protocol."""
        assert "MCP Protocol" in architecture_content

    def test_architecture_diagram_mentions_stdio(self, architecture_content: str) -> None:
        """Architecture diagram must mention stdio transport."""
        assert "stdio" in architecture_content

    def test_architecture_mentions_graph_analyzer(self, architecture_content: str) -> None:
        """Architecture diagram must mention the Graph Analyzer component."""
        assert "Graph" in architecture_content and "Analyzer" in architecture_content

    def test_architecture_mentions_api_verifier(self, architecture_content: str) -> None:
        """Architecture diagram must mention the API Verifier component."""
        assert "API" in architecture_content and "Verifier" in architecture_content

    def test_architecture_mentions_sandbox_validator(self, architecture_content: str) -> None:
        """Architecture diagram must mention the Sandbox Validator component."""
        assert "Sandbox" in architecture_content and "Validator" in architecture_content

    def test_architecture_mentions_sqlite(self, architecture_content: str) -> None:
        """Architecture must reference SQLite as the graph database backend."""
        assert "SQLite" in architecture_content

    def test_architecture_mentions_lru_cache(self, architecture_content: str) -> None:
        """Architecture must reference the LRU cache."""
        assert "LRU" in architecture_content

    def test_architecture_mentions_skill_manager(self, architecture_content: str) -> None:
        """Architecture diagram must include the Skill Manager component."""
        assert "Skill Manager" in architecture_content

    def test_architecture_has_key_features_section(self, architecture_content: str) -> None:
        """docs/architecture.md must include a Key Features section."""
        assert "Key Features" in architecture_content

    def test_architecture_documents_ast_powered_analysis(self, architecture_content: str) -> None:
        """Key Features must include AST-Powered Analysis."""
        assert "AST-Powered Analysis" in architecture_content or "AST" in architecture_content

    def test_architecture_documents_sqlite_graph_database(self, architecture_content: str) -> None:
        """Key Features must include the SQLite Graph Database feature."""
        assert "SQLite Graph Database" in architecture_content

    def test_architecture_documents_smart_impact_analysis(self, architecture_content: str) -> None:
        """Key Features must include Smart Impact Analysis."""
        assert "Smart Impact Analysis" in architecture_content or "Impact Analysis" in architecture_content

    def test_architecture_documents_multilanguage_api_verification(self, architecture_content: str) -> None:
        """Key Features must document multi-language API verification."""
        assert "Multi-Language" in architecture_content or "API Verification" in architecture_content

    def test_architecture_documents_sandbox_validation_feature(self, architecture_content: str) -> None:
        """Key Features must include Sandbox Validation."""
        assert "Sandbox Validation" in architecture_content

    def test_architecture_documents_skill_management_feature(self, architecture_content: str) -> None:
        """Key Features must include Skill Management."""
        assert "Skill Management" in architecture_content

    def test_architecture_has_performance_section(self, architecture_content: str) -> None:
        """docs/architecture.md must include a Performance section."""
        assert "## Performance" in architecture_content

    def test_architecture_performance_table_has_seven_operations(self, architecture_content: str) -> None:
        """Performance table must document exactly 7 operations."""
        # Each row starts with "| " and contains a duration pattern like ~
        perf_section = architecture_content[architecture_content.find("## Performance"):]
        # Count data rows (excluding header and separator rows)
        data_rows = [
            line for line in perf_section.splitlines()
            if line.startswith("|") and "~" in line
        ]
        assert len(data_rows) == 7, f"Expected 7 performance rows, found {len(data_rows)}"

    def test_architecture_performance_lists_full_graph_build(self, architecture_content: str) -> None:
        """Performance table must include Full graph build entry."""
        assert "Full graph build" in architecture_content

    def test_architecture_performance_lists_impact_analysis(self, architecture_content: str) -> None:
        """Performance table must include Impact analysis entry."""
        assert "Impact analysis" in architecture_content

    def test_architecture_sandbox_validation_mentions_ruff_mypy(self, architecture_content: str) -> None:
        """Sandbox Validation feature must mention both ruff and mypy."""
        assert "ruff" in architecture_content
        assert "mypy" in architecture_content

    # Boundary test: risk levels must be documented
    def test_architecture_impact_analysis_mentions_risk_levels(self, architecture_content: str) -> None:
        """Smart Impact Analysis must document risk levels."""
        assert "low" in architecture_content.lower() and "medium" in architecture_content.lower() and "high" in architecture_content.lower()


class TestDevelopmentDoc:
    """Tests for docs/development.md development and contributing documentation."""

    def test_development_has_development_heading(self, development_content: str) -> None:
        """docs/development.md must have a Development heading."""
        assert "## Development" in development_content

    def test_development_has_project_structure_section(self, development_content: str) -> None:
        """docs/development.md must include a Project Structure section."""
        assert "Project Structure" in development_content

    def test_development_project_structure_lists_pyscribe_code(self, development_content: str) -> None:
        """Project structure must list the pyscribe_code package directory."""
        assert "pyscribe_code" in development_content

    def test_development_project_structure_lists_pyscribe_core(self, development_content: str) -> None:
        """Project structure must list the pyscribe_core package directory."""
        assert "pyscribe_core" in development_content

    def test_development_project_structure_lists_server_py(self, development_content: str) -> None:
        """Project structure must reference server.py."""
        assert "server.py" in development_content

    def test_development_project_structure_lists_managers(self, development_content: str) -> None:
        """Project structure must list the managers/ subdirectory."""
        assert "managers" in development_content

    def test_development_has_running_tests_section(self, development_content: str) -> None:
        """docs/development.md must include a Running Tests section."""
        assert "Running Tests" in development_content

    def test_development_running_tests_shows_pytest_command(self, development_content: str) -> None:
        """Running Tests section must show the pytest command."""
        assert "pytest tests/" in development_content

    def test_development_running_tests_shows_coverage_flag(self, development_content: str) -> None:
        """Running Tests section must show the --cov flag for coverage."""
        assert "--cov" in development_content

    def test_development_has_linting_section(self, development_content: str) -> None:
        """docs/development.md must include a Linting section."""
        assert "Lint" in development_content

    def test_development_linting_references_ruff(self, development_content: str) -> None:
        """Linting section must reference ruff."""
        assert "ruff" in development_content

    def test_development_type_checking_references_mypy(self, development_content: str) -> None:
        """Type checking section must reference mypy."""
        assert "mypy" in development_content

    def test_development_has_troubleshooting_section(self, development_content: str) -> None:
        """docs/development.md must include a Troubleshooting section."""
        assert "## Troubleshooting" in development_content

    def test_development_troubleshooting_covers_empty_graph(self, development_content: str) -> None:
        """Troubleshooting must address the 'codebase graph is empty' problem."""
        assert "graph is empty" in development_content or "codebase graph" in development_content.lower()

    def test_development_troubleshooting_covers_mypy_timeout(self, development_content: str) -> None:
        """Troubleshooting must address mypy check timeouts."""
        assert "mypy" in development_content and "timeout" in development_content.lower()

    def test_development_troubleshooting_covers_skill_download(self, development_content: str) -> None:
        """Troubleshooting must address skill download failures."""
        assert "Skill download fails" in development_content or "download" in development_content.lower()

    def test_development_troubleshooting_covers_no_callers(self, development_content: str) -> None:
        """Troubleshooting must address the 'no callers found' situation."""
        assert "No callers found" in development_content or "callers" in development_content.lower()

    def test_development_has_contributing_section(self, development_content: str) -> None:
        """docs/development.md must include a Contributing section."""
        assert "## Contributing" in development_content

    def test_development_contributing_mentions_fork(self, development_content: str) -> None:
        """Contributing steps must mention forking the repository."""
        assert "Fork" in development_content

    def test_development_contributing_mentions_feature_branch(self, development_content: str) -> None:
        """Contributing steps must mention creating a feature branch."""
        assert "feature branch" in development_content or "checkout -b" in development_content

    def test_development_contributing_mentions_pull_request(self, development_content: str) -> None:
        """Contributing steps must mention opening a Pull Request."""
        assert "Pull Request" in development_content

    def test_development_contributing_has_five_steps(self, development_content: str) -> None:
        """Contributing section must list exactly 5 numbered steps."""
        contributing_section = development_content[development_content.find("## Contributing"):]
        steps = re.findall(r"^\d+\.", contributing_section, re.MULTILINE)
        assert len(steps) == 5, f"Expected 5 contributing steps, found {len(steps)}"

    # Boundary test: the project structure should reference pyproject.toml
    def test_development_project_structure_lists_pyproject_toml(self, development_content: str) -> None:
        """Project structure must reference pyproject.toml."""
        assert "pyproject.toml" in development_content

    # Negative test: troubleshooting should not be empty
    def test_development_troubleshooting_has_multiple_items(self, development_content: str) -> None:
        """Troubleshooting section must contain at least 3 issue headings."""
        troubleshooting_idx = development_content.find("## Troubleshooting")
        contributing_idx = development_content.find("## Contributing")
        troubleshooting_section = development_content[troubleshooting_idx:contributing_idx]
        # Count ### subheadings within troubleshooting
        subheadings = re.findall(r"^###", troubleshooting_section, re.MULTILINE)
        assert len(subheadings) >= 3, f"Expected at least 3 troubleshooting items, found {len(subheadings)}"
