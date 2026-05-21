"""TypeScript/JavaScript AST parser using tree-sitter for codebase graph extraction."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import tree_sitter
import tree_sitter_typescript

from pyscribe_code.core.ast_parser import EdgeInfo, FileAnalysis, NodeInfo

logger = logging.getLogger(__name__)

TS_EXTENSIONS = {".ts", ".tsx"}
JS_EXTENSIONS = {".js", ".jsx"}
ALL_TS_JS_EXTENSIONS = TS_EXTENSIONS | JS_EXTENSIONS


@dataclass
class TSSymbolVisitor:
    """tree-sitter visitor that extracts TypeScript definitions and call relationships."""

    file_path: str
    language: tree_sitter.Language
    nodes: list[NodeInfo] = field(default_factory=list)
    edges: list[EdgeInfo] = field(default_factory=list)
    _current_class: str = ""
    _current_function: str = ""
    _current_interface: str = ""

    def visit_node(self, node: tree_sitter.Node) -> None:
        if node.type == "function_declaration":
            self._visit_function_declaration(node)
        elif node.type == "arrow_function":
            self._visit_arrow_function(node)
        elif node.type == "method_definition":
            self._visit_method_definition(node)
        elif node.type == "class_declaration":
            self._visit_class_declaration(node)
        elif node.type == "interface_declaration":
            self._visit_interface_declaration(node)
        elif node.type == "type_alias_declaration":
            self._visit_type_alias(node)
        elif node.type == "enum_declaration":
            self._visit_enum_declaration(node)
        elif node.type == "call_expression":
            self._visit_call_expression(node)
        elif node.type == "decorator":
            self._visit_decorator(node)
        elif node.type == "import_statement":
            self._visit_import_statement(node)
        elif node.type == "import_requirement":
            self._visit_import_requirement(node)
        else:
            for child in node.children:
                self.visit_node(child)

    def _visit_function_declaration(self, node: tree_sitter.Node) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        func_name = name_node.text.decode("utf-8")
        full_name = f"{self._current_class}.{func_name}" if self._current_class else func_name
        signature = self._build_function_signature(node, func_name)

        self.nodes.append(NodeInfo(
            file_path=self.file_path,
            symbol_name=full_name,
            symbol_type="method" if self._current_class else "function",
            line_number=node.start_point.row + 1,
            signature=signature,
        ))

        old_function = self._current_function
        self._current_function = full_name

        for child in node.children:
            if child.type == "statement_block":
                for stmt in child.children:
                    self.visit_node(stmt)

        self._current_function = old_function

    def _visit_arrow_function(self, node: tree_sitter.Node) -> None:
        parent = node.parent
        if not parent:
            return

        if parent.type == "variable_declarator":
            name_node = parent.child_by_field_name("name")
            if name_node:
                var_name = name_node.text.decode("utf-8")
                signature = self._build_arrow_signature(node, var_name)
                self.nodes.append(NodeInfo(
                    file_path=self.file_path,
                    symbol_name=var_name,
                    symbol_type="function",
                    line_number=node.start_point.row + 1,
                    signature=signature,
                ))

        body = node.child_by_field_name("body")
        if body:
            old_function = self._current_function
            name_node = parent.child_by_field_name("name")
            if name_node:
                self._current_function = name_node.text.decode("utf-8")
            for child in body.children:
                self.visit_node(child)
            self._current_function = old_function

    def _visit_method_definition(self, node: tree_sitter.Node) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        method_name = name_node.text.decode("utf-8")
        full_name = f"{self._current_class}.{method_name}" if self._current_class else method_name
        signature = self._build_method_signature(node, method_name)

        self.nodes.append(NodeInfo(
            file_path=self.file_path,
            symbol_name=full_name,
            symbol_type="method",
            line_number=node.start_point.row + 1,
            signature=signature,
        ))

        old_function = self._current_function
        self._current_function = full_name

        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                self.visit_node(child)

        self._current_function = old_function

    def _visit_class_declaration(self, node: tree_sitter.Node) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        class_name = name_node.text.decode("utf-8")
        signature = self._build_class_signature(node, class_name)

        self.nodes.append(NodeInfo(
            file_path=self.file_path,
            symbol_name=class_name,
            symbol_type="class",
            line_number=node.start_point.row + 1,
            signature=signature,
        ))

        extends_clause = node.child_by_field_name("extends")
        if extends_clause:
            for child in extends_clause.children:
                if child.type in ("identifier", "nested_identifier", "generic_type"):
                    base_name = child.text.decode("utf-8")
                    self.edges.append(EdgeInfo(
                        source=class_name,
                        target=base_name,
                        edge_type="extends",
                        line_number=node.start_point.row + 1,
                    ))

        implements_clause = node.child_by_field_name("implements")
        if implements_clause:
            for child in implements_clause.children:
                if child.type in ("identifier", "nested_identifier", "generic_type"):
                    iface_name = child.text.decode("utf-8")
                    self.edges.append(EdgeInfo(
                        source=class_name,
                        target=iface_name,
                        edge_type="implements",
                        line_number=node.start_point.row + 1,
                    ))

        old_class = self._current_class
        self._current_class = class_name

        for child in node.children:
            if child.type == "decorator":
                self._visit_decorator(child)

        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                self.visit_node(child)

        self._current_class = old_class

    def _visit_interface_declaration(self, node: tree_sitter.Node) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        iface_name = name_node.text.decode("utf-8")
        signature = self._build_interface_signature(node, iface_name)

        self.nodes.append(NodeInfo(
            file_path=self.file_path,
            symbol_name=iface_name,
            symbol_type="interface",
            line_number=node.start_point.row + 1,
            signature=signature,
        ))

        extends_clause = node.child_by_field_name("extends")
        if extends_clause:
            for child in extends_clause.children:
                if child.type in ("identifier", "nested_identifier", "generic_type"):
                    parent_name = child.text.decode("utf-8")
                    self.edges.append(EdgeInfo(
                        source=iface_name,
                        target=parent_name,
                        edge_type="extends",
                        line_number=node.start_point.row + 1,
                    ))

        old_interface = self._current_interface
        self._current_interface = iface_name

        body = node.child_by_field_name("body")
        if body:
            self._visit_interface_body(body)

        self._current_interface = old_interface

    def _visit_interface_body(self, node: tree_sitter.Node) -> None:
        for child in node.children:
            if child.type == "property_signature":
                name_node = child.child_by_field_name("name")
                if name_node:
                    prop_name = name_node.text.decode("utf-8")
                    full_name = f"{self._current_interface}.{prop_name}"
                    self.nodes.append(NodeInfo(
                        file_path=self.file_path,
                        symbol_name=full_name,
                        symbol_type="property",
                        line_number=child.start_point.row + 1,
                        signature=f"{prop_name}: {self._get_type_annotation(child)}",
                    ))
            elif child.type == "method_signature":
                name_node = child.child_by_field_name("name")
                if name_node:
                    method_name = name_node.text.decode("utf-8")
                    full_name = f"{self._current_interface}.{method_name}"
                    self.nodes.append(NodeInfo(
                        file_path=self.file_path,
                        symbol_name=full_name,
                        symbol_type="method",
                        line_number=child.start_point.row + 1,
                        signature=self._build_method_sig_signature(child, method_name),
                    ))

    def _visit_type_alias(self, node: tree_sitter.Node) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        type_name = name_node.text.decode("utf-8")
        signature = self._build_type_alias_signature(node, type_name)

        self.nodes.append(NodeInfo(
            file_path=self.file_path,
            symbol_name=type_name,
            symbol_type="type",
            line_number=node.start_point.row + 1,
            signature=signature,
        ))

    def _visit_enum_declaration(self, node: tree_sitter.Node) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        enum_name = name_node.text.decode("utf-8")
        signature = self._build_enum_signature(node, enum_name)

        self.nodes.append(NodeInfo(
            file_path=self.file_path,
            symbol_name=enum_name,
            symbol_type="enum",
            line_number=node.start_point.row + 1,
            signature=signature,
        ))

        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                if child.type == "property_identifier":
                    member_name = child.text.decode("utf-8")
                    self.nodes.append(NodeInfo(
                        file_path=self.file_path,
                        symbol_name=f"{enum_name}.{member_name}",
                        symbol_type="enum_member",
                        line_number=child.start_point.row + 1,
                        signature=member_name,
                    ))

    def _visit_call_expression(self, node: tree_sitter.Node) -> None:
        func_node = node.child_by_field_name("function")
        if func_node and self._current_function:
            callee = self._resolve_call_name(func_node)
            if callee:
                self.edges.append(EdgeInfo(
                    source=self._current_function,
                    target=callee,
                    edge_type="calls",
                    line_number=node.start_point.row + 1,
                ))

        for child in node.children:
            self.visit_node(child)

    def _visit_decorator(self, node: tree_sitter.Node) -> None:
        call_node = node.child_by_field_name("expression")
        if not call_node:
            for child in node.children:
                if child.type == "call_expression":
                    call_node = child
                    break
        if call_node:
            decorator_name = self._resolve_call_name(call_node)
            if decorator_name and self._current_class:
                self.edges.append(EdgeInfo(
                    source=self._current_class,
                    target=decorator_name,
                    edge_type="decorates",
                    line_number=node.start_point.row + 1,
                ))

    def _visit_import_statement(self, node: tree_sitter.Node) -> None:
        for child in node.children:
            if child.type == "import_clause":
                for clause_child in child.children:
                    if clause_child.type == "named_imports":
                        for spec in clause_child.children:
                            if spec.type == "import_specifier":
                                name_node = spec.child_by_field_name("name")
                                if name_node:
                                    imported_name = name_node.text.decode("utf-8")
                                    self.nodes.append(NodeInfo(
                                        file_path=self.file_path,
                                        symbol_name=imported_name,
                                        symbol_type="import",
                                        line_number=node.start_point.row + 1,
                                        signature=f"import {{ {imported_name} }}",
                                    ))
            elif child.type == "string":
                module_name = child.text.decode("utf-8").strip("'\"")
                source = self._current_function or "(module)"
                self.edges.append(EdgeInfo(
                    source=source,
                    target=module_name,
                    edge_type="imports",
                    line_number=node.start_point.row + 1,
                ))

    def _visit_import_requirement(self, node: tree_sitter.Node) -> None:
        for child in node.children:
            if child.type == "string":
                module_name = child.text.decode("utf-8").strip("'\"")
                self.edges.append(EdgeInfo(
                    source="(module)",
                    target=module_name,
                    edge_type="imports",
                    line_number=node.start_point.row + 1,
                ))

    def _resolve_call_name(self, node: tree_sitter.Node) -> str | None:
        if node.type == "identifier":
            return node.text.decode("utf-8")
        if node.type == "member_expression":
            return node.text.decode("utf-8")
        if node.type == "call_expression":
            return self._resolve_call_name(node.child_by_field_name("function") or node)
        if node.type == "as_expression":
            for child in node.children:
                if child.type == "identifier":
                    return child.text.decode("utf-8")
        return None

    def _build_function_signature(self, node: tree_sitter.Node, name: str) -> str:
        params = self._extract_parameters(node)
        return_type = self._extract_return_type(node)
        prefix = "async " if self._is_async(node) else ""
        return f"{prefix}function {name}({params}){return_type}"

    def _build_arrow_signature(self, node: tree_sitter.Node, name: str) -> str:
        params = self._extract_arrow_parameters(node)
        return f"const {name} = ({params}) => ..."

    def _build_method_signature(self, node: tree_sitter.Node, name: str) -> str:
        params = self._extract_parameters(node)
        return_type = self._extract_return_type(node)
        prefix = "async " if self._is_async(node) else ""
        access = self._extract_access_modifier(node)
        return f"{access}{prefix}{name}({params}){return_type}"

    def _build_class_signature(self, node: tree_sitter.Node, name: str) -> str:
        parts = [f"class {name}"]
        extends = node.child_by_field_name("extends")
        implements = node.child_by_field_name("implements")
        if extends:
            bases = []
            for child in extends.children:
                if child.type in ("identifier", "nested_identifier", "generic_type"):
                    bases.append(child.text.decode("utf-8"))
            if bases:
                parts.append(f"extends {', '.join(bases)}")
        if implements:
            ifaces = []
            for child in implements.children:
                if child.type in ("identifier", "nested_identifier", "generic_type"):
                    ifaces.append(child.text.decode("utf-8"))
            if ifaces:
                parts.append(f"implements {', '.join(ifaces)}")
        return " ".join(parts)

    def _build_interface_signature(self, node: tree_sitter.Node, name: str) -> str:
        parts = [f"interface {name}"]
        extends = node.child_by_field_name("extends")
        if extends:
            parents = []
            for child in extends.children:
                if child.type in ("identifier", "nested_identifier", "generic_type"):
                    parents.append(child.text.decode("utf-8"))
            if parents:
                parts.append(f"extends {', '.join(parents)}")
        return " ".join(parts)

    def _build_type_alias_signature(self, node: tree_sitter.Node, name: str) -> str:
        value_node = node.child_by_field_name("value")
        if value_node:
            return f"type {name} = {value_node.text.decode('utf-8')}"
        return f"type {name}"

    def _build_enum_signature(self, node: tree_sitter.Node, name: str) -> str:
        return f"enum {name}"

    def _build_method_sig_signature(self, node: tree_sitter.Node, name: str) -> str:
        params = self._extract_parameters(node)
        return_type = self._extract_return_type(node)
        return f"{name}({params}){return_type}"

    def _extract_parameters(self, node: tree_sitter.Node) -> str:
        params_node = node.child_by_field_name("parameters")
        if not params_node:
            return ""
        params = []
        for child in params_node.children:
            if child.type == "required_parameter":
                params.append(self._format_parameter(child))
            elif child.type == "optional_parameter":
                params.append(self._format_parameter(child) + "?")
            elif child.type == "rest_parameter":
                params.append("..." + self._format_parameter(child))
        return ", ".join(params)

    def _extract_arrow_parameters(self, node: tree_sitter.Node) -> str:
        params_node = node.child_by_field_name("parameters")
        if not params_node:
            return ""
        if params_node.type == "identifier":
            return params_node.text.decode("utf-8")
        params = []
        for child in params_node.children:
            if child.type in ("identifier", "required_parameter"):
                params.append(child.text.decode("utf-8"))
        return ", ".join(params)

    def _format_parameter(self, node: tree_sitter.Node) -> str:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return ""
        name = name_node.text.decode("utf-8")
        type_node = node.child_by_field_name("type")
        if type_node:
            return f"{name}: {type_node.text.decode('utf-8')}"
        return name

    def _extract_return_type(self, node: tree_sitter.Node) -> str:
        return_type_node = node.child_by_field_name("return_type")
        if return_type_node:
            return f" -> {return_type_node.text.decode('utf-8')}"
        return ""

    def _extract_access_modifier(self, node: tree_sitter.Node) -> str:
        for child in node.children:
            if child.type in ("public", "private", "protected"):
                return child.text.decode("utf-8") + " "
        return ""

    def _is_async(self, node: tree_sitter.Node) -> bool:
        for child in node.children:
            if child.type == "async":
                return True
        return False

    def _get_type_annotation(self, node: tree_sitter.Node) -> str:
        type_node = node.child_by_field_name("type")
        if type_node:
            return type_node.text.decode("utf-8")
        return "unknown"


class TypeScriptASTParser:
    """High-level parser that walks directories and extracts TypeScript/JavaScript graphs."""

    def __init__(self, exclude: set[str] | None = None) -> None:
        self.exclude = exclude or {"venv", ".venv", "node_modules", ".git", "__pycache__", ".mypy_cache", "dist", "build", ".tox", ".eggs"}
        self._ts_language = tree_sitter.Language(tree_sitter_typescript.language_typescript())
        self._tsx_language = tree_sitter.Language(tree_sitter_typescript.language_tsx())

    def parse_file(self, file_path: str | Path) -> FileAnalysis:
        path = Path(file_path)
        try:
            source = path.read_text(encoding="utf-8")
        except (SyntaxError, OSError) as e:
            logger.warning("Failed to read %s: %s", file_path, e)
            return FileAnalysis(file_path=str(path))

        language = self._tsx_language if path.suffix in {".tsx", ".jsx"} else self._ts_language
        parser = tree_sitter.Parser(language)
        tree = parser.parse(source.encode("utf-8"))

        visitor = TSSymbolVisitor(
            file_path=str(path),
            language=language,
        )
        visitor.visit_node(tree.root_node)

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

        for root, dirs, files in os.walk(path):
            dirs[:] = [
                d for d in dirs
                if not self._is_excluded(Path(root) / d, exclusions)
            ]
            for filename in files:
                file_path = Path(root) / filename
                if file_path.suffix in ALL_TS_JS_EXTENSIONS:
                    analysis = self.parse_file(file_path)
                    results.append(analysis)

        return results

    def _is_excluded(self, file_path: Path, exclusions: set[str]) -> bool:
        parts = set(file_path.parts)
        return bool(parts & exclusions)
