"""Sandbox validator for TypeScript/JavaScript code: syntax, lint, type checking."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess  # nosec B404
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TS_EXTENSIONS = {".ts", ".tsx"}
JS_EXTENSIONS = {".js", ".jsx"}


class TSSandboxValidator:
    """Validates TypeScript/JavaScript code before writing to disk."""

    def __init__(self, project_root: str | Path) -> None:
        """
        Initialize the validator with the repository/project root.
        
        Parameters:
            project_root (str | Path): Path to the project root used to resolve local binaries and configuration; stored on the instance as a pathlib.Path.
        """
        self._project_root = Path(project_root)

    def validate(
        self,
        code: str,
        file_path: str | None = None,
        checks: list[str] | None = None,
        ts_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Run requested sandbox checks (syntax, lint, types) on TypeScript/JavaScript code and return an aggregated report.
        
        Parameters:
            code (str): Source code to validate.
            file_path (str | None): Optional filename used to choose file extension and display in the report. If omitted, "<unnamed>" is used in the returned report.
            checks (list[str] | None): List of checks to run. Supported values: "syntax", "lint", "types". When omitted, defaults to ["syntax", "lint", "types"].
            ts_config (dict[str, Any] | None): Optional TypeScript compiler configuration used for the "types" check; when omitted a sensible default tsconfig is generated.
        
        Returns:
            dict[str, Any]: Aggregated validation report with keys:
                - "file_path" (str): Provided file_path or "<unnamed>".
                - "status" (str): Overall status: "pass", "warn", or "fail".
                - "can_write" (bool): True when no check produced a "fail" status.
                - "summary" (str): One-line summary like "All checks passed" or "<errors> error(s), <warnings> warning(s)".
                - "results" (list[dict[str, Any]]): Per-check result objects produced by the individual check methods.
        """
        if checks is None:
            checks = ["syntax", "lint", "types"]

        results: list[dict[str, Any]] = []

        if "syntax" in checks:
            results.append(self._check_syntax(code, file_path))

        if "lint" in checks:
            results.append(self._check_lint(code, file_path))

        if "types" in checks:
            results.append(self._check_types(code, file_path, ts_config))

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

    def _check_syntax(self, code: str, file_path: str | None = None) -> dict[str, Any]:
        """
        Run a TypeScript/JavaScript syntax check on the provided code using the `tsc` compiler.
        
        Parameters:
        	code (str): Source code to validate.
        	file_path (str | None): Optional filename used to determine file extension for the temporary file; when omitted a default `.ts` suffix is used.
        
        Returns:
        	result (dict): A report with keys:
        		- "check": the string "syntax".
        		- "status": one of "pass", "warn", or "fail".
        		- "issues": a list of issue objects, each with:
        			- "line" (int | None)
        			- "column" (int | None)
        			- "code" (str)
        			- "message" (str)
        			- "severity" ("error" or "warning")
        		
        Notes:
        	- If the `tsc` binary is not available, the method returns a single warning issue indicating the check was skipped.
        	- On execution failures or timeouts a single warning issue with code "SYNTAX_ERROR" is added.
        """
        issues: list[dict[str, Any]] = []
        ext = self._get_extension(file_path)

        if not self._has_tsc():
            return {"check": "syntax", "status": "warn", "issues": [{"line": None, "column": None, "code": "SKIP", "message": "tsc not available, skipping syntax check", "severity": "warning"}]}

        temp_path = None
        try:
            suffix = ext if ext else ".ts"
            with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False, encoding="utf-8") as f:
                f.write(code)
                temp_path = f.name

            result = subprocess.run(  # nosec B603
                ["tsc", "--noEmit", "--pretty", "false", "--skipLibCheck", temp_path],
                capture_output=True,
                text=True,
                timeout=15,
            )

            if result.returncode != 0:
                for line in result.stdout.strip().split("\n"):
                    if not line:
                        continue
                    parsed = self._parse_tsc_line(line)
                    if parsed:
                        issues.append(parsed)

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            issues.append({
                "line": None,
                "column": None,
                "code": "SYNTAX_ERROR",
                "message": f"tsc syntax check failed: {e}",
                "severity": "warning",
            })
        finally:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)

        status = "fail" if any(i["severity"] == "error" for i in issues) else ("warn" if issues else "pass")
        return {"check": "syntax", "status": status, "issues": issues}

    def _check_lint(self, code: str, file_path: str | None = None) -> dict[str, Any]:
        """
        Run ESLint on the provided code (using a project-local or global eslint) and return parsed lint issues.
        
        If an eslint executable cannot be found, returns a warning-level result indicating the lint check was skipped. When eslint runs and produces JSON output, each message is converted to an issue with `line`, `column`, `code` (rule id or "eslint"), `message`, and `severity` ("error" for severity 2, otherwise "warning"). On execution errors or timeouts a single warning-style issue is returned describing the failure. A temporary file is used for linting and is always cleaned up.
        
        Parameters:
            file_path (str | None): Optional original file path used to choose the temporary file extension; if omitted a default extension is used.
        
        Returns:
            dict: A result dictionary with keys:
                - "check": always "lint"
                - "status": "pass" if no issues, otherwise "warn"
                - "issues": list of issue dicts, each containing:
                    - "line" (int | None)
                    - "column" (int | None)
                    - "code" (str)
                    - "message" (str)
                    - "severity" ("error" | "warning")
        """
        issues: list[dict[str, Any]] = []

        eslint = self._find_eslint()
        if not eslint:
            return {"check": "lint", "status": "warn", "issues": [{"line": None, "column": None, "code": "SKIP", "message": "eslint not available, skipping lint check", "severity": "warning"}]}

        ext = self._get_extension(file_path)
        temp_path = None
        try:
            suffix = ext if ext else ".ts"
            with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False, encoding="utf-8") as f:
                f.write(code)
                temp_path = f.name

            result = subprocess.run(  # nosec B603
                [eslint, "--format", "json", temp_path],
                capture_output=True,
                text=True,
                timeout=15,
                cwd=str(self._project_root),
            )

            if result.stdout.strip():
                try:
                    lint_results = json.loads(result.stdout)
                    for file_result in lint_results:
                        for msg in file_result.get("messages", []):
                            issues.append({
                                "line": msg.get("line"),
                                "column": msg.get("column"),
                                "code": msg.get("ruleId", "eslint"),
                                "message": msg.get("message", ""),
                                "severity": "error" if msg.get("severity") == 2 else "warning",
                            })
                except json.JSONDecodeError:
                    pass

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            issues.append({
                "line": None,
                "column": None,
                "code": "LINT_ERROR",
                "message": f"eslint check failed: {e}",
                "severity": "warning",
            })
        finally:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)

        status = "fail" if any(i["severity"] == "error" for i in issues) else ("warn" if issues else "pass")
        return {"check": "lint", "status": status, "issues": issues}

    def _check_types(
        self,
        code: str,
        file_path: str | None = None,
        ts_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Run a TypeScript type check on the provided code using a temporary tsconfig and return structured issues.
        
        Parameters:
            code (str): Source code to type-check.
            file_path (str | None): Optional filename hint used to choose an appropriate file extension for the temporary source file.
            ts_config (dict[str, Any] | None): Optional tsconfig object to use instead of the default compiler options.
        
        Returns:
            dict[str, Any]: A report with keys:
                - `check` (str): The check name `"types"`.
                - `status` (str): One of `"pass"`, `"warn"`, or `"fail"`.
                - `issues` (list[dict]): A list of issue objects; each issue contains:
                    - `line` (int | None)
                    - `column` (int | None)
                    - `code` (str)
                    - `message` (str)
                    - `severity` (str): `"error"` or `"warning"`.
        """
        issues: list[dict[str, Any]] = []

        if not self._has_tsc():
            return {"check": "types", "status": "warn", "issues": [{"line": None, "column": None, "code": "SKIP", "message": "tsc not available, skipping type check", "severity": "warning"}]}

        ext = self._get_extension(file_path)
        temp_dir = None
        temp_path = None
        try:
            temp_dir = tempfile.mkdtemp()
            suffix = ext if ext else ".ts"
            temp_path = Path(temp_dir) / f"validate{suffix}"
            temp_path.write_text(code, encoding="utf-8")

            config_path = Path(temp_dir) / "tsconfig.json"
            config = ts_config or {
                "compilerOptions": {
                    "target": "ES2020",
                    "module": "commonjs",
                    "strict": True,
                    "esModuleInterop": True,
                    "skipLibCheck": True,
                    "noEmit": True,
                },
            }
            config_path.write_text(json.dumps(config), encoding="utf-8")

            result = subprocess.run(  # nosec B603
                ["tsc", "-p", str(config_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                for line in result.stdout.strip().split("\n"):
                    if not line:
                        continue
                    parsed = self._parse_tsc_line(line)
                    if parsed:
                        issues.append(parsed)

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            issues.append({
                "line": None,
                "column": None,
                "code": "TYPE_ERROR",
                "message": f"tsc type check failed: {e}",
                "severity": "warning",
            })
        finally:
            if temp_dir:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)

        status = "fail" if any(i["severity"] == "error" for i in issues) else ("warn" if issues else "pass")
        return {"check": "types", "status": status, "issues": issues}

    def _parse_tsc_line(self, line: str) -> dict[str, Any] | None:
        """
        Parse a single line of TypeScript compiler (tsc) output into a structured issue dictionary.
        
        Returns:
            dict: An issue with keys:
                - `line` (int | None): 1-based line number if present and numeric, otherwise `None`.
                - `column` (int | None): 1-based column number if present and numeric, otherwise `None`.
                - `code` (str): The source of the issue, always `"tsc"`.
                - `message` (str): The message text extracted from the line (empty string if none found).
                - `severity` (str): `"error"` when the line contains "error" (case-insensitive) and does not contain "warning"; otherwise `"warning"`.
            None: If the line cannot be parsed into the expected tsc format.
        """
        if "(" not in line or ")" not in line:
            return None

        try:
            file_part, rest = line.split("(", 1)
            line_col, _ = rest.split(")", 1)
            line_num_str, col_str = line_col.split(",")

            message = ""
            if ": " in line:
                message = line.split(": ", 1)[1].strip()

            is_error = "error" in line.lower() and "warning" not in line.lower()

            return {
                "line": int(line_num_str.strip()) if line_num_str.strip().isdigit() else None,
                "column": int(col_str.strip()) if col_str.strip().isdigit() else None,
                "code": "tsc",
                "message": message,
                "severity": "error" if is_error else "warning",
            }
        except (ValueError, IndexError):
            return None

    def _get_extension(self, file_path: str | None) -> str:
        """
        Return the file extension to use for a temporary source file.
        
        Parameters:
            file_path (str | None): Optional file path whose suffix will be used if it matches a supported TypeScript/JavaScript extension.
        
        Returns:
            str: The suffix from `file_path` when it is one of the supported extensions (`.ts`, `.tsx`, `.js`, `.jsx`); otherwise `".ts"`.
        """
        if file_path:
            path = Path(file_path)
            if path.suffix in TS_EXTENSIONS | JS_EXTENSIONS:
                return path.suffix
        return ".ts"

    def _has_tsc(self) -> bool:
        """
        Check whether the TypeScript compiler (`tsc`) is available locally or on PATH.

        Returns:
            True if a project-local `tsc` exists under `node_modules/.bin` or `tsc` is on PATH, False otherwise.
        """
        local_tsc = self._project_root / "node_modules" / ".bin" / "tsc"
        if local_tsc.exists() and os.access(local_tsc, os.X_OK):
            return True
        local_tsc_cmd = self._project_root / "node_modules" / ".bin" / "tsc.cmd"
        if local_tsc_cmd.exists():
            return True
        return shutil.which("tsc") is not None

    def _find_eslint(self) -> str | None:
        """
        Resolve the eslint executable to use for linting.
        
        Checks for a globally available `eslint` on the PATH first; if not found, checks for a local project installation under `node_modules/.bin` and returns the first matching executable path.
        
        Returns:
            str | None: The executable name or absolute path to `eslint` if found, otherwise `None`.
        """
        if shutil.which("eslint"):
            return "eslint"

        local_eslint = self._project_root / "node_modules" / ".bin" / "eslint"
        if local_eslint.exists():
            return str(local_eslint)

        local_eslint_cmd = self._project_root / "node_modules" / ".bin" / "eslint.cmd"
        if local_eslint_cmd.exists():
            return str(local_eslint_cmd)

        return None
