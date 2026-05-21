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
        """
        Recursively traverses a tree-sitter AST node and dispatches recognized node types to specialized handlers to extract symbols and relationships.
        
        Parameters:
            node (tree_sitter.Node): The AST node to visit; traversal may recurse into its children. Side effects: updates visitor state and appends entries to self.nodes and self.edges for discovered declarations and relationships.
        """
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
        """
        Record a function or method declaration as a NodeInfo and traverse its body to collect nested symbols and call sites.
        
        Parameters:
            node (tree_sitter.Node): A tree-sitter node for a function declaration; must contain a `name` field. The function's symbol name is qualified with the current class when present, a signature is built and a NodeInfo appended. The visitor will temporarily set the current function context while visiting the node's `statement_block` children.
        """
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
        """
        Handle an arrow_function AST node: record a named arrow function as a NodeInfo when it is assigned to a variable, and traverse the function body with the function set as the current context.
        
        Parameters:
            node (tree_sitter.Node): The `arrow_function` node to process.
        
        Behavior:
            - If the arrow function's parent is a `variable_declarator` with a `name`, appends a `NodeInfo` for that variable name with `symbol_type="function"` and a signature produced by `_build_arrow_signature`.
            - If the arrow function has a `body`, visits each child of the body while temporarily setting `_current_function` to the variable name (if present) so that nested calls and edges are associated with the correct enclosing function.
        """
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
        """
        Record a method declaration and traverse its body while scoping the current function context.
        
        Appends a NodeInfo for the method (qualified with the current class if present) including its signature and line number, sets the visitor's current function to the method while visiting the method body, and restores the previous current function after traversal.
        
        Parameters:
            node (tree_sitter.Node): A `method_definition` AST node to process.
        """
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
        """
        Record a class declaration as a node, any extends/implements relationships as edges, and visit its body with the class context set.
        
        If the class has no name, the node is ignored. Appends a `NodeInfo` for the class to `self.nodes`, appends `EdgeInfo` entries for each recognized `extends` and `implements` target to `self.edges`, temporarily sets `self._current_class` to the class's name while visiting the class body, and restores the previous class context afterward.
        
        Parameters:
            node (tree_sitter.Node): The tree-sitter AST node representing a class_declaration.
        """
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
        """
        Record an interface declaration and its `extends` relationships, then visit its body.
        
        Parameters:
            node (tree_sitter.Node): The tree-sitter AST node for an `interface_declaration`.
        
        Notes:
            - Appends a `NodeInfo` for the interface to `self.nodes`.
            - For each recognized parent in the `extends` clause, appends an `EdgeInfo` with `edge_type="extends"` to `self.edges`.
            - Temporarily sets `self._current_interface` to the interface name while visiting the interface body.
        """
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
        """
        Extracts members from an interface body node and records them as NodeInfo entries.
        
        Scans the children of the provided interface body node for `property_signature` and `method_signature` members. For each found member with a name, appends a NodeInfo to `self.nodes` with a symbol_name qualified as "{interface}.{member}", symbol_type set to "property" or "method", the member's declaration line number, and an appropriate signature.
        
        Parameters:
            node (tree_sitter.Node): The `interface_body` AST node whose children will be inspected.
        """
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
        """
        Record a type alias declaration in the visitor's node list.
        
        If the node has a `name` field, extract the alias name, build its signature, and append a `NodeInfo` with `symbol_type="type"` and the declaration's line number. If the alias is unnamed, no node is added.
        """
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
        """
        Record an enum declaration and its members as NodeInfo entries.
        
        If the node has a name, appends a NodeInfo for the enum itself and, if a body is present, appends a NodeInfo for each enum member found (qualified as "EnumName.Member"). If the declaration has no name, the function does nothing.
        
        Parameters:
            node (tree_sitter.Node): AST node representing an enum declaration.
        """
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
        """
        Record a "calls" edge for a call expression and then traverse its children.
        
        If the call expression has a resolvable callee and the visitor is currently inside a function, append an EdgeInfo with edge_type "calls", source set to the current function, target set to the resolved callee, and line_number set to the call's starting line (1-based). After recording any edge, continue visiting all child nodes of the call expression.
        """
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
        """
        Record a "decorates" edge when a decorator expression names a decorator applied to the currently visited class.
        
        Parameters:
            node (tree_sitter.Node): A `decorator` AST node whose `expression` field is examined to resolve the decorator name.
        
        Behavior:
            If the decorator's expression resolves to a name and a class context is active (`self._current_class`),
            appends an `EdgeInfo` with `edge_type="decorates"`, `source` set to the current class, `target` set to the decorator name,
            and `line_number` set to the decorator node's starting line.
        """
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
        """
        Extract import specifiers and module import relationships from an import statement node.
        
        For each named import specifier found in the statement, appends a NodeInfo representing the imported symbol with symbol_type "import" and a signature of the form "import { <name> }". If the statement contains a string literal and there is a current function context, appends an EdgeInfo of type "imports" from the current function (or "(module)") to the module name with surrounding quotes removed. Line numbers on produced NodeInfo/EdgeInfo correspond to the import statement's starting line.
        
        Parameters:
            node (tree_sitter.Node): An `import_statement` AST node to inspect.
        """
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
        """
        Record 'imports' edges for each string literal child in an import-requirement AST node.
        
        Parameters:
            node (tree_sitter.Node): An `import_requirement` AST node whose string children are module specifiers; each string's quotes are stripped and an `EdgeInfo` with `source="(module)"`, `target=<module_name>`, and `edge_type="imports"` is appended to `self.edges` with the node's starting line number.
        """
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
        """
        Resolve the callee name from a tree-sitter expression node.
        
        Parameters:
            node (tree_sitter.Node): An expression node (identifier, member_expression, call_expression, or as_expression) to inspect for a callable name.
        
        Returns:
            The callee name string when it can be resolved, or `None` if no name could be determined.
        """
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
        """
        Builds a formatted function signature string for the given function AST node.
        
        Parameters:
            node (tree_sitter.Node): The function node from the tree-sitter AST.
            name (str): The function name to use in the signature.
        
        Returns:
            signature (str): A signature string containing an optional `async` prefix, the `function` keyword, the provided name, formatted parameters, and an optional return type (e.g. "async function foo(a, b) -> Type").
        """
        params = self._extract_parameters(node)
        return_type = self._extract_return_type(node)
        prefix = "async " if self._is_async(node) else ""
        return f"{prefix}function {name}({params}){return_type}"

    def _build_arrow_signature(self, node: tree_sitter.Node, name: str) -> str:
        """
        Builds a concise signature string for an arrow function assigned to a variable.
        
        Parameters:
            node (tree_sitter.Node): The arrow function AST node from which parameter text is extracted.
            name (str): The variable name the arrow function is assigned to.
        
        Returns:
            str: A signature string in the form "const {name} = ({params}) => ...".
        """
        params = self._extract_arrow_parameters(node)
        return f"const {name} = ({params}) => ..."

    def _build_method_signature(self, node: tree_sitter.Node, name: str) -> str:
        """
        Constructs a human-readable method signature string including access modifier, async marker, parameters, and return type.
        
        Parameters:
            node (tree_sitter.Node): The AST node for the method definition.
            name (str): The method's simple name.
        
        Returns:
            signature (str): Formatted signature like "`<access> <async?>name(param1: Type, ...) -> ReturnType`" (access and async may be omitted if absent).
        """
        params = self._extract_parameters(node)
        return_type = self._extract_return_type(node)
        prefix = "async " if self._is_async(node) else ""
        access = self._extract_access_modifier(node)
        return f"{access}{prefix}{name}({params}){return_type}"

    def _build_class_signature(self, node: tree_sitter.Node, name: str) -> str:
        """
        Builds a human-readable class signature including optional `extends` and `implements` clauses.
        
        Parameters:
            node (tree_sitter.Node): AST node for the class declaration; used to read `extends` and `implements` children.
            name (str): The class name.
        
        Returns:
            signature (str): A string like `"class MyClass extends Base1, Base2 implements IOne, ITwo"`, omitting `extends`/`implements` when absent.
        """
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
        """
        Builds a concise interface signature string, including any `extends` clause when present.
        
        Parameters:
            node (tree_sitter.Node): The interface declaration node to extract extends information from.
            name (str): The interface name.
        
        Returns:
            signature (str): Formatted signature like "interface Name" or "interface Name extends A, B".
        """
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
        """
        Builds a TypeScript type alias signature string for the given name.
        
        Returns:
            A string "type {name} = {value}" when the alias has a value, otherwise "type {name}".
        """
        value_node = node.child_by_field_name("value")
        if value_node:
            return f"type {name} = {value_node.text.decode('utf-8')}"
        return f"type {name}"

    def _build_enum_signature(self, node: tree_sitter.Node, name: str) -> str:
        """
        Builds the signature string for an enum declaration.
        
        Returns:
            signature (str): The enum signature formatted as "enum <Name>".
        """
        return f"enum {name}"

    def _build_method_sig_signature(self, node: tree_sitter.Node, name: str) -> str:
        """
        Constructs a method-signature string from a Tree-sitter signature node and a method name.
        
        Parameters:
            node (tree_sitter.Node): AST node containing parameter and return type information (e.g., a method or method_signature node).
            name (str): The method name to use as the signature's identifier.
        
        Returns:
            signature (str): The formatted signature string in the form "name(params){return_type}", where {return_type} is empty or of the form " -> <type>".
        """
        params = self._extract_parameters(node)
        return_type = self._extract_return_type(node)
        return f"{name}({params}){return_type}"

    def _extract_parameters(self, node: tree_sitter.Node) -> str:
        """
        Builds a comma-separated parameter list string from a function/method node's "parameters" field.
        
        Parameters:
            node (tree_sitter.Node): AST node expected to contain a "parameters" child (e.g., function, method, or arrow function node).
        
        Returns:
            str: Comma-separated parameter representations suitable for signatures. Required parameters use the formatted name or "name: type" from `_format_parameter`; optional parameters have a trailing `?`; rest parameters are prefixed with `...`. Returns an empty string if no parameters are present.
        """
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
        """
        Extract the parameter list text from an arrow function AST node.
        
        Parameters:
            node (tree_sitter.Node): An arrow function node whose "parameters" field will be read.
        
        Returns:
            str: A comma-separated list of parameter texts (e.g., "a, b"), or an empty string if no parameters are present.
        """
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
        """
        Format a parameter AST node as a readable "name" or "name: type" string.
        
        Parameters:
            node (tree_sitter.Node): A parameter node from the tree-sitter AST; expected to have a "name" field and optionally a "type" field.
        
        Returns:
            str: "name: <type>" if the node has a type, "name" if no type is present, or an empty string if the node lacks a name.
        """
        name_node = node.child_by_field_name("name")
        if not name_node:
            return ""
        name = name_node.text.decode("utf-8")
        type_node = node.child_by_field_name("type")
        if type_node:
            return f"{name}: {type_node.text.decode('utf-8')}"
        return name

    def _extract_return_type(self, node: tree_sitter.Node) -> str:
        """
        Format the return type annotation for a function-like AST node.
        
        Looks for a child field named "return_type" on the provided node and, if present,
        returns the annotation text prefixed with " -> ". If no return type is present,
        returns an empty string.
        
        Parameters:
            node (tree_sitter.Node): The function/method AST node to inspect.
        
        Returns:
            return_type (str): The formatted return type, e.g. " -> Promise<number>", or
            an empty string if no return type is declared.
        """
        return_type_node = node.child_by_field_name("return_type")
        if return_type_node:
            return f" -> {return_type_node.text.decode('utf-8')}"
        return ""

    def _extract_access_modifier(self, node: tree_sitter.Node) -> str:
        """
        Return the access modifier token found among the node's children, formatted with a trailing space.
        
        Parameters:
            node (tree_sitter.Node): AST node whose children will be scanned for `public`, `private`, or `protected` tokens.
        
        Returns:
            str: The modifier followed by a single space (e.g., `"public "`), or an empty string if no modifier is present.
        """
        for child in node.children:
            if child.type in ("public", "private", "protected"):
                return child.text.decode("utf-8") + " "
        return ""

    def _is_async(self, node: tree_sitter.Node) -> bool:
        """
        Check whether the given AST node contains an `async` child token.
        
        Parameters:
            node (tree_sitter.Node): AST node to inspect.
        
        Returns:
            True if the node has an `async` child, False otherwise.
        """
        for child in node.children:
            if child.type == "async":
                return True
        return False

    def _get_type_annotation(self, node: tree_sitter.Node) -> str:
        """
        Extract the textual type annotation from a tree-sitter node.
        
        Parameters:
            node (tree_sitter.Node): AST node that may contain a `type` field.
        
        Returns:
            str: The text of the node's `type` child if present, otherwise the string "unknown".
        """
        type_node = node.child_by_field_name("type")
        if type_node:
            return type_node.text.decode("utf-8")
        return "unknown"


class TypeScriptASTParser:
    """High-level parser that walks directories and extracts TypeScript/JavaScript graphs."""

    def __init__(self, exclude: set[str] | None = None) -> None:
        """
        Initialize the parser with an optional set of path components to exclude and prepare TypeScript/TSX grammars.
        
        Parameters:
            exclude (set[str] | None): Optional set of directory or file name components to skip when scanning (e.g., "node_modules", ".git"). If omitted, a sensible default exclusion set is used.
        """
        self.exclude = exclude or {"venv", ".venv", "node_modules", ".git", "__pycache__", ".mypy_cache", "dist", "build", ".tox", ".eggs"}
        self._ts_language = tree_sitter.Language(tree_sitter_typescript.language_typescript())
        self._tsx_language = tree_sitter.Language(tree_sitter_typescript.language_tsx())

    def parse_file(self, file_path: str | Path) -> FileAnalysis:
        """
        Parse a TypeScript or JavaScript source file and extract symbol nodes and relationship edges.
        
        Parameters:
            file_path (str | Path): Path to the source file to parse.
        
        Returns:
            FileAnalysis: Analysis for the given file containing `file_path`, and the extracted `nodes` and `edges`. If the file cannot be read, returns a FileAnalysis with only `file_path` populated and no nodes or edges.
        """
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
        """
        Recursively parse TypeScript and JavaScript files under a directory and return their analyses.
        
        Parameters:
            dir_path (str | Path): Directory to search for files with extensions in ALL_TS_JS_EXTENSIONS.
            exclude (set[str] | None): Optional set of path components to exclude; if provided, overrides the parser instance's default exclusions.
        
        Returns:
            list[FileAnalysis]: A list of FileAnalysis objects for each parsed file found under dir_path. If dir_path is not a directory, returns an empty list.
        """
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
        """
        Check if any component of the given path is present in the exclusions set.
        
        Parameters:
            file_path (Path): The filesystem path to evaluate.
            exclusions (set[str]): A set of path component names; if any component of `file_path` is in this set, the path is considered excluded.
        
        Returns:
            bool: `True` if any path component of `file_path` is present in `exclusions`, `False` otherwise.
        """
        parts = set(file_path.parts)
        return bool(parts & exclusions)
