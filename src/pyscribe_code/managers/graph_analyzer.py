"""Graph analyzer: orchestrates AST parsing + graph DB for codebase analysis."""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Any

from pyscribe_code.core.ast_parser import PythonASTParser
from pyscribe_code.core.graph_db import GraphDB
from pyscribe_code.core.ts_ast_parser import TypeScriptASTParser
from pyscribe_core.errors import LanguageDetectionError

logger = logging.getLogger(__name__)


class GraphAnalyzer:
    """Orchestrates graph building and impact analysis."""

    def __init__(self, project_root: str | Path, db_path: str | Path, language: str | None = None) -> None:
        self._project_root = Path(project_root)
        self._db = GraphDB(db_path)
        self._language = language
        self._py_parser = PythonASTParser()
        self._ts_parser = TypeScriptASTParser()

    def _get_parser(self, language: str):
        if language == "python":
            return self._py_parser
        if language in ("typescript", "javascript"):
            return self._ts_parser
        raise LanguageDetectionError(f"Unsupported language: {language}")

    def build_graph(
        self,
        scope: str = "full",
        path: str | None = None,
        force_rebuild: bool = False,
        language: str | None = None,
    ) -> dict[str, Any]:
        target_language = language or self._language or self._detect_language()
        self._language = target_language
        parser = self._get_parser(target_language)

        if force_rebuild:
            if scope == "full":
                self._clear_graph()
            elif scope == "file" and path:
                self._db.invalidate_file(path)
            elif scope == "module" and path:
                ext = "*.py" if target_language == "python" else "*.{ts,tsx,js,jsx}"
                if target_language == "python":
                    for py_file in Path(path).rglob("*.py"):
                        self._db.invalidate_file(str(py_file))
                else:
                    from pyscribe_code.core.ts_ast_parser import ALL_TS_JS_EXTENSIONS
                    for ext in ALL_TS_JS_EXTENSIONS:
                        for ts_file in Path(path).rglob(f"*{ext}"):
                            self._db.invalidate_file(str(ts_file))

        if scope == "full":
            analyses = self._parse_directory(parser, self._project_root, target_language)
        elif scope == "file" and path:
            file_path = Path(path)
            if not file_path.exists():
                return {"error": f"File not found: {file_path}"}
            if not self._db.is_file_cached(str(file_path)) or force_rebuild:
                analysis = parser.parse_file(file_path)
                self._db.insert_file_analysis(analysis)
            return self._graph_stats(file_path=str(file_path))
        elif scope == "module" and path:
            dir_path = Path(path)
            if not dir_path.exists():
                return {"error": f"Directory not found: {dir_path}"}
            analyses = self._parse_directory(parser, dir_path, target_language)
        else:
            return {"error": f"Invalid scope: {scope}"}

        for analysis in analyses:
            if not self._db.is_file_cached(analysis.file_path) or force_rebuild:
                self._db.remove_file_analysis(analysis.file_path)
                self._db.insert_file_analysis(analysis)

        return self._graph_stats()

    def _parse_directory(self, parser, dir_path: Path, language: str) -> list:
        if language == "python":
            return parser.parse_directory(dir_path)
        return parser.parse_directory(dir_path)

    def analyze_impact(
        self,
        symbol: str,
        change_type: str = "modify",
        max_depth: int = 3,
    ) -> dict[str, Any]:
        impact = self._db.calculate_impact_ratio(symbol, change_type)
        dependents = self._db.find_transitive_dependents(symbol, max_depth)
        test_files = self._map_to_test_files([symbol] + [d["caller"] for d in dependents])

        impact["dependents"] = dependents
        impact["test_files"] = test_files
        return impact

    def find_callers(self, symbol: str, file_path: str | None = None) -> dict[str, Any]:
        callers = self._db.find_callers(symbol)

        if file_path:
            callers = [c for c in callers if c.get("caller_file") == file_path]

        return {
            "symbol": symbol,
            "file_filter": file_path,
            "caller_count": len(callers),
            "callers": callers,
        }

    def _detect_language(self) -> str:
        py_files = list(self._project_root.rglob("*.py"))
        ts_files = list(self._project_root.rglob("*.ts")) + list(self._project_root.rglob("*.tsx"))
        js_files = list(self._project_root.rglob("*.js")) + list(self._project_root.rglob("*.jsx"))

        py_count = len(py_files)
        ts_count = len(ts_files)
        js_count = len(js_files)

        if py_count == 0 and ts_count == 0 and js_count == 0:
            raise LanguageDetectionError("No Python, TypeScript, or JavaScript files found")

        if py_count >= ts_count and py_count >= js_count:
            return "python"
        if ts_count >= py_count and ts_count >= js_count:
            return "typescript"
        return "javascript"

    def _check_cache_validity(self) -> bool:
        target_language = self._language or self._detect_language()
        if target_language == "python":
            files = list(self._project_root.rglob("*.py"))
        else:
            from pyscribe_code.core.ts_ast_parser import ALL_TS_JS_EXTENSIONS
            files = []
            for ext in ALL_TS_JS_EXTENSIONS:
                files.extend(self._project_root.rglob(f"*{ext}"))
        for f in files[:100]:
            if not self._db.is_file_cached(str(f)):
                return False
        return True

    def _build_incremental(self, changed_files: list[str]) -> None:
        target_language = self._language or self._detect_language()
        for file_path in changed_files:
            path = Path(file_path)
            if not path.exists():
                continue
            if target_language == "python" and path.suffix == ".py":
                self._db.remove_file_analysis(str(path))
                analysis = self._py_parser.parse_file(path)
                self._db.insert_file_analysis(analysis)
            elif target_language in ("typescript", "javascript") and path.suffix in {".ts", ".tsx", ".js", ".jsx"}:
                self._db.remove_file_analysis(str(path))
                analysis = self._ts_parser.parse_file(path)
                self._db.insert_file_analysis(analysis)

    def _map_to_test_files(self, affected_functions: list[str]) -> list[str]:
        test_files = []
        test_dirs = list(self._project_root.rglob("tests"))
        test_dirs += list(self._project_root.rglob("test"))
        test_dirs += list(self._project_root.rglob("__tests__"))
        target_names = {f.split(".")[-1] for f in affected_functions}

        target_language = self._language or self._detect_language()

        if target_language == "python":
            for test_dir in test_dirs:
                if not test_dir.is_dir():
                    continue
                for test_file in test_dir.rglob("test_*.py"):
                    try:
                        source = test_file.read_text(encoding="utf-8", errors="ignore")
                        tree = ast.parse(source)
                    except (SyntaxError, OSError):
                        continue
                    found = False
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Name) and node.id in target_names:
                            found = True
                            break
                        if isinstance(node, ast.Attribute) and node.attr in target_names:
                            found = True
                            break
                    if found:
                        test_files.append(str(test_file))
        else:
            from pyscribe_code.core.ts_ast_parser import ALL_TS_JS_EXTENSIONS
            for test_dir in test_dirs:
                if not test_dir.is_dir():
                    continue
                for ext in ALL_TS_JS_EXTENSIONS:
                    for test_file in test_dir.rglob(f"*{ext}"):
                        if not test_file.name.startswith(("test_", "spec_")) and not test_file.name.endswith((".test" + ext.lstrip("*"), ".spec" + ext.lstrip("*"))):
                            continue
                        try:
                            source = test_file.read_text(encoding="utf-8", errors="ignore")
                        except OSError:
                            continue
                        found = any(name in source for name in target_names)
                        if found:
                            test_files.append(str(test_file))

        return list(set(test_files))

    def _clear_graph(self) -> None:
        try:
            import sqlite3
            with sqlite3.connect(self._db._db_path) as conn:
                conn.execute("DELETE FROM edges")
                conn.execute("DELETE FROM nodes")
                conn.execute("DELETE FROM file_hashes")
        except Exception as e:
            logger.warning("Failed to clear graph: %s", e)

    def _graph_stats(self, file_path: str | None = None) -> dict[str, Any]:
        if file_path:
            return {
                "total_nodes": self._db.get_nodes_for_file(file_path),
                "total_edges": self._db.get_edges_for_file(file_path),
                "hotspots": self._db.get_hotspots_for_file(file_path, top_n=5),
                "module_dependencies": self._db.get_module_dependencies_for_file(file_path)[:10],
                "scope": "file",
                "file": file_path,
            }
        return {
            "total_nodes": self._db.get_total_nodes(),
            "total_edges": self._db.get_total_edges(),
            "hotspots": self._db.get_hotspots(top_n=5),
            "module_dependencies": self._db.get_module_dependencies()[:10],
        }

    def is_graph_empty(self) -> bool:
        return self._db.get_total_nodes() == 0
