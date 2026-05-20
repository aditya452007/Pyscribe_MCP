"""Python AST parser for codebase graph extraction."""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_EXCLUSIONS = {
    "venv", ".venv", "node_modules", ".git", "__pycache__",
    ".mypy_cache", "dist", "build", ".tox", ".eggs",
}


@dataclass
class NodeInfo:
    """Information about a code node (function, class, etc)."""

    file_path: str
    symbol_name: str
    symbol_type: str
    line_number: int
    signature: str = ""


@dataclass
class EdgeInfo:
    """Information about a code edge (call relationship)."""

    source: str
    target: str
    edge_type: str
    line_number: int = 0


@dataclass
class FileAnalysis:
    """Analysis result for a single file."""

    file_path: str
    nodes: list[NodeInfo] = field(default_factory=list)
    edges: list[EdgeInfo] = field(default_factory=list)


class SymbolVisitor(ast.NodeVisitor):
    """AST visitor that extracts definitions and call relationships."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.nodes: list[NodeInfo] = []
        self.edges: list[EdgeInfo] = []
        self._current_class: str = ""
        self._current_function: str = ""

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        class_name = node.name
        signature = self._build_class_signature(node)
        self.nodes.append(NodeInfo(
            file_path=self.file_path,
            symbol_name=class_name,
            symbol_type="class",
            line_number=node.lineno or 0,
            signature=signature,
        ))

        old_class = self._current_class
        self._current_class = class_name

        for base in node.bases:
            base_name = self._resolve_name(base)
            if base_name:
                self.edges.append(EdgeInfo(
                    source=class_name,
                    target=base_name,
                    edge_type="inherits",
                    line_number=node.lineno or 0,
                ))

        self.generic_visit(node)
        self._current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        func_name = node.name
        symbol_type = "method" if self._current_class else "function"
        full_name = f"{self._current_class}.{func_name}" if self._current_class else func_name

        signature = self._build_function_signature(node)
        self.nodes.append(NodeInfo(
            file_path=self.file_path,
            symbol_name=full_name,
            symbol_type=symbol_type,
            line_number=node.lineno or 0,
            signature=signature,
        ))

        old_function = self._current_function
        self._current_function = full_name

        self.generic_visit(node)
        self._current_function = old_function

    def visit_Call(self, node: ast.Call) -> None:
        callee = self._resolve_call_name(node)
        if callee and self._current_function:
            self.edges.append(EdgeInfo(
                source=self._current_function,
                target=callee,
                edge_type="calls",
                line_number=node.lineno or 0,
            ))
        self.generic_visit(node)

    def _build_class_signature(self, node: ast.ClassDef) -> str:
        bases = [self._resolve_name(base) for base in node.bases]
        base_str = ", ".join(b for b in bases if b)
        return f"class {node.name}({base_str})" if base_str else f"class {node.name}"

    def _build_function_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {self._resolve_name(arg.annotation)}"
            args.append(arg_str)

        args_str = ", ".join(args)
        returns = ""
        if node.returns:
            returns = f" -> {self._resolve_name(node.returns)}"

        prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
        return f"{prefix}def {node.name}({args_str}){returns}"

    def _resolve_name(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return f"{self._resolve_name(node.value)}.{node.attr}"
        if isinstance(node, ast.Constant):
            return str(node.value)
        if isinstance(node, ast.Subscript):
            return f"{self._resolve_name(node.value)}[{self._resolve_name(node.slice)}]"
        return ""

    def _resolve_call_name(self, node: ast.Call) -> str | None:
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return self._resolve_name(node.func)
        return None


class PythonASTParser:
    """High-level parser that walks directories and extracts code graphs."""

    def __init__(self, exclude: set[str] | None = None) -> None:
        self.exclude = exclude or DEFAULT_EXCLUSIONS

    def parse_file(self, file_path: str | Path) -> FileAnalysis:
        path = Path(file_path)
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (SyntaxError, OSError) as e:
            logger.warning("Failed to parse %s: %s", file_path, e)
            return FileAnalysis(file_path=str(path))

        visitor = SymbolVisitor(str(path))
        visitor.visit(tree)

        return FileAnalysis(
            file_path=str(path),
            nodes=visitor.nodes,
            edges=visitor.edges,
        )

    def parse_directory(
        self,
        dir_path: str | Path,
        exclude: set[str] | None = None,
    ) -> list[FileAnalysis]:
        path = Path(dir_path)
        if not path.is_dir():
            return []

        exclusions = exclude or self.exclude
        results = []

        for py_file in path.rglob("*.py"):
            if self._is_excluded(py_file, exclusions):
                continue
            analysis = self.parse_file(py_file)
            results.append(analysis)

        return results

    def _is_excluded(self, file_path: Path, exclusions: set[str]) -> bool:
        parts = set(file_path.parts)
        return bool(parts & exclusions)
