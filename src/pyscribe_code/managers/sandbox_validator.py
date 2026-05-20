"""Sandbox validator for Python code: syntax, lint, type checking."""

from __future__ import annotations

import ast
import json
import logging
import subprocess  # nosec B404
import sys
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SandboxValidator:
    """Validates Python code before writing to disk."""

    def __init__(self, project_root: str | Path) -> None:
        self._project_root = Path(project_root)

    def validate(
        self,
        code: str,
        file_path: str | None = None,
        python_version: str | None = None,
        checks: list[str] | None = None,
        dependencies: list[str] | None = None,
    ) -> dict[str, Any]:
        if checks is None:
            checks = ["syntax", "imports", "lint", "types"]

        results: list[dict[str, Any]] = []

        if "syntax" in checks:
            results.append(self._check_syntax(code))

        if "imports" in checks:
            results.append(self._check_imports(code, dependencies))

        if "lint" in checks:
            results.append(self._check_lint(code))

        if "types" in checks and file_path:
            results.append(self._check_types(code, file_path))

        can_write = all(r["status"] != "fail" for r in results)
        fail_count = sum(1 for r in results if r["status"] == "fail")
        warn_count = sum(1 for r in results if r["status"] == "warn")

        if fail_count > 0:
            status = "fail"
            summary = f"{fail_count} error(s), {warn_count} warning(s)"
        elif warn_count > 0:
            status = "warn"
            summary = f"0 error(s), {warn_count} warning(s)"
        else:
            status = "pass"
            summary = "All checks passed"

        return {
            "file_path": file_path or "<unnamed>",
            "status": status,
            "can_write": can_write,
            "summary": summary,
            "results": results,
        }

    def _check_syntax(self, code: str) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        try:
            ast.parse(code)
            return {"check": "syntax", "status": "pass", "issues": []}
        except SyntaxError as e:
            issues.append({
                "line": e.lineno,
                "column": e.offset,
                "code": "SyntaxError",
                "message": str(e.msg),
                "severity": "error",
            })
            return {"check": "syntax", "status": "fail", "issues": issues}

    def _check_imports(self, code: str, dependencies: list[str] | None = None) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return {"check": "imports", "status": "warn", "issues": [{"line": None, "column": None, "code": "SKIP", "message": "Cannot check imports: syntax errors present", "severity": "warning"}]}

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if not self._module_exists(alias.name):
                        issues.append({
                            "line": node.lineno,
                            "column": node.col_offset,
                            "code": "ImportError",
                            "message": f"Module '{alias.name}' not found",
                            "severity": "warning",
                        })
            elif isinstance(node, ast.ImportFrom):
                if node.module and not self._module_exists(node.module):
                    issues.append({
                        "line": node.lineno,
                        "column": node.col_offset,
                        "code": "ImportError",
                        "message": f"Module '{node.module}' not found",
                        "severity": "warning",
                    })

        status = "warn" if issues else "pass"
        return {"check": "imports", "status": status, "issues": issues}

    def _check_lint(self, code: str) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        try:
            result = subprocess.run(  # nosec B603
                [sys.executable, "-m", "ruff", "check", "--output-format=json", "-"],
                input=code,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.stdout.strip():
                ruff_issues = json.loads(result.stdout)
                for issue in ruff_issues:
                    loc = issue.get("location", {})
                    if isinstance(loc, dict):
                        line = loc.get("row") or loc.get("line")
                        col = loc.get("column") or loc.get("col")
                    elif isinstance(loc, int):
                        line, col = loc, None
                    else:
                        line, col = None, None

                    issues.append({
                        "line": line,
                        "column": col,
                        "code": issue.get("code", "RUFF"),
                        "message": issue.get("message", issue.get("text", "")),
                        "severity": "warning",
                    })
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError, Exception) as e:
            issues.append({
                "line": None,
                "column": None,
                "code": "LINT_ERROR",
                "message": f"ruff check failed: {e}",
                "severity": "warning",
            })

        status = "warn" if issues else "pass"
        return {"check": "lint", "status": status, "issues": issues}

    def _check_types(self, code: str, file_path: str) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(code)
                temp_path = f.name

            result = subprocess.run(  # nosec B603
                [sys.executable, "-m", "mypy", temp_path, "--no-error-summary"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split(":", 4)
                if len(parts) >= 4:
                    issues.append({
                        "line": int(parts[1]) if parts[1].strip().isdigit() else None,
                        "column": int(parts[2]) if parts[2].strip().isdigit() else None,
                        "code": "mypy",
                        "message": parts[3].strip() + (f": {parts[4]}" if len(parts) > 4 else ""),
                        "severity": "error" if "error" in parts[3].lower() else "warning",
                    })
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            issues.append({
                "line": None,
                "column": None,
                "code": "TYPE_ERROR",
                "message": f"mypy check failed: {e}",
                "severity": "warning",
            })
        finally:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)

        status = "fail" if any(i["severity"] == "error" for i in issues) else ("warn" if issues else "pass")
        return {"check": "types", "status": status, "issues": issues}

    def _module_exists(self, module_name: str) -> bool:
        try:
            import importlib
            importlib.import_module(module_name)
            return True
        except (ModuleNotFoundError, ImportError):
            return False
