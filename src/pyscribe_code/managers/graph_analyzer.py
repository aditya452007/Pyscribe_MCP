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
        """
        Initialize a GraphAnalyzer with project root, graph database, and optional target language.
        
        Parameters:
            project_root (str | Path): Path to the project root directory to analyze.
            db_path (str | Path): Path to the graph database file used for persistence.
            language (str | None): Optional target language hint ("python", "typescript", or "javascript"); if omitted, language will be auto-detected when needed.
        """
        self._project_root = Path(project_root)
        self._db = GraphDB(db_path)
        self._language = language
        self._py_parser = PythonASTParser()
        self._ts_parser = TypeScriptASTParser()

    def _get_parser(self, language: str):
        """
        Selects the appropriate AST parser for the given language.
        
        Parameters:
        	language (str): Language identifier; expected values are "python", "typescript", or "javascript".
        
        Returns:
        	The parser instance corresponding to the requested language.
        
        Raises:
        	LanguageDetectionError: If the language is not supported.
        """
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
        """
        Build or update the project analysis graph for a specified scope and persist results to the graph database.
        
        Selects the parser for the target language (argument, instance language, or auto-detected), optionally invalidates cached analyses when `force_rebuild` is true, parses files or directories according to `scope`, persists new analyses into the database, and returns graph statistics.
        
        Parameters:
            scope (str): One of "full", "module", or "file" determining the unit to (re)build.
            path (str | None): File or directory path used when `scope` is "file" or "module".
            force_rebuild (bool): If true, invalidate cached analyses for the affected scope before parsing.
            language (str | None): Explicit language hint ("python", "typescript", or "javascript"); if omitted, the analyzer's language or auto-detection is used.
        
        Returns:
            dict[str, Any]: Graph statistics for the requested scope, or an error dict with an "error" message on invalid input (missing path, invalid scope, or similar).
        """
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
        """
        Parse a directory of source files using the provided AST parser for the specified language.
        
        Parameters:
            parser: An AST parser instance with a `parse_directory(Path)` method.
            dir_path (Path): Path to the directory to parse.
            language (str): Target language hint used to select parser behavior.
        
        Returns:
            list: A list of file analysis results produced by the parser.
        """
        if language == "python":
            return parser.parse_directory(dir_path)
        return parser.parse_directory(dir_path)

    def analyze_impact(
        self,
        symbol: str,
        change_type: str = "modify",
        max_depth: int = 3,
    ) -> dict[str, Any]:
        """
        Compute impact metrics for a code symbol and include its transitive dependents and related test files.
        
        Parameters:
            symbol (str): Fully qualified name or identifier of the symbol to analyze.
            change_type (str): Type of change to evaluate impact for (e.g., "modify", "delete"). Defaults to "modify".
            max_depth (int): Maximum transitive depth to search for dependents. Defaults to 3.
        
        Returns:
            impact (dict[str, Any]): Impact metrics returned by the database augmented with:
                - "dependents" (list[dict]): Transitive dependent records up to `max_depth`.
                - "test_files" (list[str]): Paths to test files that likely reference the affected symbols.
        """
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
        """
        Detects the dominant language in the project by counting .py, .ts, and .js files.
        
        Ties are resolved by preferring Python first, then TypeScript over JavaScript.
        
        Returns:
            str: One of 'python', 'typescript', or 'javascript' indicating the detected language.
        
        Raises:
            LanguageDetectionError: If no Python, TypeScript, or JavaScript files are found.
        """
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
        """
        Check whether a sample of project files for the configured or detected language are present in the cache.
        
        Checks up to 100 files of the target language (Python: `*.py`; TypeScript/JavaScript: extensions from the parser configuration) and returns `False` immediately if any checked file is not cached.
        
        Returns:
            bool: `True` if all checked files have cached analysis, `False` otherwise.
        """
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
        """
        Perform incremental rebuild of analyses for a list of changed source files.
        
        Determines the target language from the instance language or by auto-detection, then for each existing path in `changed_files` that matches the target language's file extensions, re-parses that file and replaces its analysis in the graph database. Paths that do not exist are skipped.
        
        Parameters:
            changed_files (list[str]): Iterable of file paths to consider for incremental rebuild.
        
        Side effects:
            Updates the graph database by removing and inserting the file analysis for each re-parsed file.
        """
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
        """
        Map a list of affected function identifiers to likely test files that reference them.
        
        Scans common test directories ("tests", "test", "__tests__") under the project root and returns test file paths that reference any of the provided affected function names. The final component of each string in `affected_functions` (the text after the last dot) is used as the search target. Behavior depends on the detected or configured project language:
        - Python: parses each candidate test file and matches `Name` or `Attribute` AST nodes against the target names.
        - TypeScript/JavaScript: restricts to test-like filenames (e.g., starting with `test_`/`spec_` or ending with `.test.*`/`.spec.*`) and matches target names by simple substring search in the file text.
        
        Parameters:
            affected_functions (list[str]): A list of function or symbol identifiers; only the last dot-separated segment of each entry is used for matching.
        
        Returns:
            list[str]: A de-duplicated list of file paths (as strings) to test files that likely reference the affected functions.
        """
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
