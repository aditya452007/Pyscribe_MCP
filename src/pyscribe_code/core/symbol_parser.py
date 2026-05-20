"""Symbol extraction from Python and Node.js files."""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

logger = logging.getLogger(__name__)


@dataclass
class SymbolInfo:
    """Metadata for a single symbol."""

    name: str
    symbol_type: str
    line_number: int
    signature: str = ""
    file_path: str = ""
    docstring: str = ""
    parent: str = ""


@dataclass
class PythonSymbolParser:
    """Parse .py/.pyi files using AST to extract symbols."""

    file_path: str = ""
    symbols: list[SymbolInfo] = field(default_factory=list)

    def parse_file(self, file_path: str | Path) -> list[SymbolInfo]:
        path = Path(file_path)
        self.file_path = str(path)
        self.symbols = []

        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(path))
        except (SyntaxError, OSError) as e:
            logger.warning("Failed to parse Python file %s: %s", file_path, e)
            return []

        self._visit_node(tree, parent="")
        return self.symbols

    def _visit_node(self, node: ast.AST, parent: str = "") -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                self._extract_function(child, parent)
                self._visit_node(child, parent=child.name)
            elif isinstance(child, ast.ClassDef):
                self._extract_class(child)
                self._visit_node(child, parent=child.name)
            elif isinstance(child, ast.Assign | ast.AnnAssign) and not parent:
                self._extract_variable(child, parent)
            else:
                self._visit_node(child, parent)

    def _extract_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, parent: str) -> None:
        symbol_type = "method" if parent else "function"
        signature = self._build_function_signature(node)
        docstring = ast.get_docstring(node) or ""

        self.symbols.append(SymbolInfo(
            name=node.name,
            symbol_type=symbol_type,
            line_number=node.lineno or 0,
            signature=signature,
            file_path=self.file_path,
            docstring=docstring,
            parent=parent,
        ))

    def _extract_class(self, node: ast.ClassDef) -> None:
        bases = [self._get_name(base) for base in node.bases if self._get_name(base)]
        signature = f"class {node.name}({', '.join(bases)})" if bases else f"class {node.name}"
        docstring = ast.get_docstring(node) or ""

        self.symbols.append(SymbolInfo(
            name=node.name,
            symbol_type="class",
            line_number=node.lineno or 0,
            signature=signature,
            file_path=self.file_path,
            docstring=docstring,
        ))

    def _extract_variable(self, node: ast.Assign | ast.AnnAssign, parent: str) -> None:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.symbols.append(SymbolInfo(
                        name=target.id,
                        symbol_type="variable",
                        line_number=node.lineno or 0,
                        file_path=self.file_path,
                        parent=parent,
                    ))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            self.symbols.append(SymbolInfo(
                name=node.target.id,
                symbol_type="variable",
                line_number=node.lineno or 0,
                file_path=self.file_path,
                parent=parent,
            ))

    def _build_function_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {self._get_name(arg.annotation)}"
            args.append(arg_str)

        args_str = ", ".join(args)
        returns = ""
        if node.returns:
            returns = f" -> {self._get_name(node.returns)}"

        prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
        return f"{prefix}def {node.name}({args_str}){returns}"

    def _get_name(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        if isinstance(node, ast.Constant):
            return str(node.value)
        if isinstance(node, ast.Subscript):
            return f"{self._get_name(node.value)}[{self._get_name(node.slice)}]"
        return ""


class NodeSymbolParser:
    """Parse .d.ts files using regex to extract TypeScript declarations."""

    file_path: str = ""
    symbols: list[SymbolInfo] = field(default_factory=list)

    PATTERNS: ClassVar[dict[str, re.Pattern]] = {
        "function": re.compile(
            r"(?:export\s+)?(?:declare\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)(?:\s*:\s*([^\{;]+))?",
            re.MULTILINE,
        ),
        "class": re.compile(
            r"(?:export\s+)?(?:declare\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w\s,]+))?",
            re.MULTILINE,
        ),
        "interface": re.compile(
            r"(?:export\s+)?(?:declare\s+)?interface\s+(\w+)(?:\s+extends\s+([\w\s,]+))?",
            re.MULTILINE,
        ),
        "const": re.compile(
            r"(?:export\s+)?(?:declare\s+)?const\s+(\w+)\s*:\s*([^\n;]+)",
            re.MULTILINE,
        ),
        "type": re.compile(
            r"(?:export\s+)?(?:declare\s+)?type\s+(\w+)\s*=\s*([^\n;]+)",
            re.MULTILINE,
        ),
        "enum": re.compile(
            r"(?:export\s+)?(?:declare\s+)?enum\s+(\w+)",
            re.MULTILINE,
        ),
    }

    def parse_file(self, file_path: str | Path) -> list[SymbolInfo]:
        path = Path(file_path)
        self.file_path = str(path)
        self.symbols = []

        try:
            source = path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("Failed to read file %s: %s", file_path, e)
            return []

        self._extract_symbols(source)
        return self.symbols

    def _extract_symbols(self, source: str) -> None:
        for symbol_type, pattern in self.PATTERNS.items():
            for match in pattern.finditer(source):
                name = match.group(1)
                line_number = source[:match.start()].count("\n") + 1

                signature = self._build_signature(symbol_type, match, name)

                self.symbols.append(SymbolInfo(
                    name=name,
                    symbol_type=symbol_type,
                    line_number=line_number,
                    signature=signature,
                    file_path=self.file_path,
                ))

    def _build_signature(self, symbol_type: str, match: re.Match, name: str) -> str:
        if symbol_type == "function":
            args = match.group(2) or ""
            returns = match.group(3) or "void"
            return f"function {name}({args.strip()}): {returns.strip()}"
        if symbol_type == "class":
            extends = match.group(2)
            implements = match.group(3)
            parts = [f"class {name}"]
            if extends:
                parts.append(f"extends {extends.strip()}")
            if implements:
                parts.append(f"implements {implements.strip()}")
            return " ".join(parts)
        if symbol_type == "interface":
            extends = match.group(2)
            parts = [f"interface {name}"]
            if extends:
                parts.append(f"extends {extends.strip()}")
            return " ".join(parts)
        if symbol_type in ("const", "type"):
            type_info = match.group(2) or "unknown"
            return f"{symbol_type} {name} = {type_info.strip()}"
        if symbol_type == "enum":
            return f"enum {name}"
        return name


def find_symbol(
    directory: str | Path,
    symbol_name: str,
    symbol_type: str = "",
    language: str = "python",
) -> SymbolInfo | None:
    path = Path(directory)
    if not path.is_dir():
        return None

    extensions = {".py", ".pyi"} if language == "python" else {".d.ts"}
    files = [f for f in path.rglob("*") if f.suffix in extensions and not _is_excluded(f)]

    for file_path in files:
        if language == "python":
            parser = PythonSymbolParser()
        else:
            parser = NodeSymbolParser()

        symbols = parser.parse_file(file_path)
        for sym in symbols:
            if sym.name == symbol_name and (not symbol_type or sym.symbol_type == symbol_type):
                return sym
    return None


def find_similar_symbols(
    directory: str | Path,
    symbol_name: str,
    threshold: float = 0.7,
    language: str = "python",
) -> list[SymbolInfo]:
    path = Path(directory)
    if not path.is_dir():
        return []

    extensions = {".py", ".pyi"} if language == "python" else {".d.ts"}
    files = [f for f in path.rglob("*") if f.suffix in extensions and not _is_excluded(f)]

    similar = []
    for file_path in files:
        if language == "python":
            parser = PythonSymbolParser()
        else:
            parser = NodeSymbolParser()

        symbols = parser.parse_file(file_path)
        for sym in symbols:
            score = _similarity_score(sym.name, symbol_name)
            if score >= threshold:
                similar.append(sym)

    similar.sort(key=lambda s: _similarity_score(s.name, symbol_name), reverse=True)
    return similar[:10]


def resolve_import_path(
    library: str,
    symbol: str,
    project_root: str | Path,
    language: str = "python",
) -> str | None:
    path = Path(project_root)
    if language == "python":
        return _resolve_python_import(library, symbol, path)
    return _resolve_ts_import(library, symbol, path)


def _resolve_python_import(library: str, symbol: str, project_root: Path) -> str | None:
    site_packages_dirs = list(project_root.rglob("site-packages"))
    venv_dirs = list(project_root.rglob("lib"))

    search_dirs = []
    for d in site_packages_dirs + venv_dirs:
        if d.is_dir():
            search_dirs.append(d)

    search_dirs.append(project_root)

    for search_dir in search_dirs:
        lib_dir = search_dir / library
        if lib_dir.is_dir():
            files = list(lib_dir.rglob("*.py")) + list(lib_dir.rglob("*.pyi"))
            for f in files:
                if _is_excluded(f):
                    continue
                parser = PythonSymbolParser()
                symbols = parser.parse_file(f)
                for sym in symbols:
                    if sym.name == symbol:
                        rel_path = f.relative_to(search_dir)
                        module_path = str(rel_path).replace("/", ".").replace("\\", ".").removesuffix(".py").removesuffix(".pyi")
                        return f"from {module_path} import {symbol}"

    return None


def _resolve_ts_import(library: str, symbol: str, project_root: Path) -> str | None:
    node_modules = project_root / "node_modules" / library
    if not node_modules.is_dir():
        return None

    files = list(node_modules.rglob("*.d.ts"))
    for f in files:
        if _is_excluded(f):
            continue
        parser = NodeSymbolParser()
        symbols = parser.parse_file(f)
        for sym in symbols:
            if sym.name == symbol:
                rel_path = f.relative_to(project_root / "node_modules")
                return f"import {{ {symbol} }} from '{library}/{rel_path}'"

    return f"import {{ {symbol} }} from '{library}'"


def _is_excluded(file_path: Path) -> bool:
    excluded = {"venv", ".venv", "node_modules", ".git", "__pycache__", ".mypy_cache", "dist", "build"}
    parts = set(file_path.parts)
    return bool(parts & excluded)


def _similarity_score(s1: str, s2: str) -> float:
    s1_lower = s1.lower()
    s2_lower = s2.lower()

    if s1_lower == s2_lower:
        return 1.0

    if s1_lower in s2_lower or s2_lower in s1_lower:
        return 0.9

    common = sum(1 for c in s1_lower if c in s2_lower)
    max_len = max(len(s1_lower), len(s2_lower))
    return common / max_len if max_len > 0 else 0.0
