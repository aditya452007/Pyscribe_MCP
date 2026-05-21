"""Tests for TypeScript/JavaScript codebase graph analyzer."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pyscribe_code.core.ts_ast_parser import TypeScriptASTParser, TSSymbolVisitor
from pyscribe_code.core.graph_db import GraphDB
from pyscribe_code.managers.graph_analyzer import GraphAnalyzer


@pytest.fixture
def sample_ts_project():
    """Create a temporary project with multiple TypeScript files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir)

        (path / "types.ts").write_text('''
export interface User {
  name: string;
  email: string;
}

export type UserId = string | number;

export enum Role {
  Admin,
  User,
  Guest
}
''')

        (path / "service.ts").write_text('''
import { User, UserId } from './types';

export class UserService {
  private users: Map<UserId, User> = new Map();

  getUser(id: UserId): User | undefined {
    return this.users.get(id);
  }

  createUser(name: string, email: string): User {
    const user: User = { name, email };
    this.users.set(name, user);
    return user;
  }
}

export const formatUser = (user: User): string => {
  return `${user.name} <${user.email}>`;
};
''')

        (path / "main.ts").write_text('''
import { UserService } from './service';
import { Role } from './types';

async function main(): Promise<void> {
  const service = new UserService();
  const user = service.createUser("John", "john@example.com");
  console.log(user);
}

main();
''')

        yield path


@pytest.fixture
def sample_js_project():
    """Create a temporary project with JavaScript files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir)

        (path / "utils.js").write_text('''
function helper(x) {
  return x * 2;
}

module.exports = { helper };
''')

        (path / "app.js").write_text('''
const { helper } = require('./utils');

class App {
  process(data) {
    return helper(data);
  }
}

module.exports = App;
''')

        yield path


@pytest.fixture
def graph_db(tmp_path):
    """Create a temporary graph database."""
    db_path = tmp_path / "test_graph.sqlite"
    return GraphDB(db_path)


class TestTypeScriptASTParser:
    """Test AST parsing of TypeScript files."""

    def test_parses_functions(self, sample_ts_project):
        parser = TypeScriptASTParser()
        analysis = parser.parse_file(sample_ts_project / "service.ts")

        functions = [n for n in analysis.nodes if n.symbol_type == "function"]
        assert len(functions) >= 1
        names = [f.symbol_name for f in functions]
        assert "formatUser" in names

    def test_parses_classes(self, sample_ts_project):
        parser = TypeScriptASTParser()
        analysis = parser.parse_file(sample_ts_project / "service.ts")

        classes = [n for n in analysis.nodes if n.symbol_type == "class"]
        assert len(classes) == 1
        assert classes[0].symbol_name == "UserService"

    def test_parses_methods(self, sample_ts_project):
        parser = TypeScriptASTParser()
        analysis = parser.parse_file(sample_ts_project / "service.ts")

        methods = [n for n in analysis.nodes if n.symbol_type == "method"]
        assert len(methods) >= 2
        names = [m.symbol_name for m in methods]
        assert "UserService.getUser" in names
        assert "UserService.createUser" in names

    def test_parses_interfaces(self, sample_ts_project):
        parser = TypeScriptASTParser()
        analysis = parser.parse_file(sample_ts_project / "types.ts")

        interfaces = [n for n in analysis.nodes if n.symbol_type == "interface"]
        assert len(interfaces) == 1
        assert interfaces[0].symbol_name == "User"

    def test_parses_type_aliases(self, sample_ts_project):
        parser = TypeScriptASTParser()
        analysis = parser.parse_file(sample_ts_project / "types.ts")

        types = [n for n in analysis.nodes if n.symbol_type == "type"]
        assert len(types) == 1
        assert types[0].symbol_name == "UserId"

    def test_parses_enums(self, sample_ts_project):
        parser = TypeScriptASTParser()
        analysis = parser.parse_file(sample_ts_project / "types.ts")

        enums = [n for n in analysis.nodes if n.symbol_type == "enum"]
        assert len(enums) == 1
        assert enums[0].symbol_name == "Role"

    def test_parses_enum_members(self, sample_ts_project):
        parser = TypeScriptASTParser()
        analysis = parser.parse_file(sample_ts_project / "types.ts")

        enum_members = [n for n in analysis.nodes if n.symbol_type == "enum_member"]
        assert len(enum_members) >= 1

    def test_extracts_call_edges(self, sample_ts_project):
        parser = TypeScriptASTParser()
        analysis = parser.parse_file(sample_ts_project / "service.ts")

        call_edges = [e for e in analysis.edges if e.edge_type == "calls"]
        assert len(call_edges) > 0

    def test_parses_directory(self, sample_ts_project):
        parser = TypeScriptASTParser()
        analyses = parser.parse_directory(sample_ts_project)

        assert len(analyses) == 3
        files = {a.file_path for a in analyses}
        assert any("types.ts" in f for f in files)
        assert any("service.ts" in f for f in files)
        assert any("main.ts" in f for f in files)

    def test_excludes_node_modules(self, sample_ts_project):
        node_modules = sample_ts_project / "node_modules" / "package"
        node_modules.mkdir(parents=True)
        (node_modules / "bad.ts").write_text("function bad(): void {}")

        parser = TypeScriptASTParser()
        analyses = parser.parse_directory(sample_ts_project)

        for a in analyses:
            assert "node_modules" not in a.file_path


class TestJavaScriptASTParser:
    """Test AST parsing of JavaScript files."""

    def test_parses_functions(self, sample_js_project):
        parser = TypeScriptASTParser()
        analysis = parser.parse_file(sample_js_project / "utils.js")

        functions = [n for n in analysis.nodes if n.symbol_type == "function"]
        assert len(functions) >= 1
        names = [f.symbol_name for f in functions]
        assert "helper" in names

    def test_parses_classes(self, sample_js_project):
        parser = TypeScriptASTParser()
        analysis = parser.parse_file(sample_js_project / "app.js")

        classes = [n for n in analysis.nodes if n.symbol_type == "class"]
        assert len(classes) == 1
        assert classes[0].symbol_name == "App"

    def test_parses_methods(self, sample_js_project):
        parser = TypeScriptASTParser()
        analysis = parser.parse_file(sample_js_project / "app.js")

        methods = [n for n in analysis.nodes if n.symbol_type == "method"]
        assert len(methods) >= 1
        names = [m.symbol_name for m in methods]
        assert "App.process" in names


class TestGraphAnalyzerTypeScript:
    """Test high-level graph analysis for TypeScript projects."""

    def test_build_graph(self, sample_ts_project, tmp_path):
        db_path = tmp_path / "graph.sqlite"
        analyzer = GraphAnalyzer(sample_ts_project, db_path, language="typescript")

        result = analyzer.build_graph(scope="full")

        assert result["total_nodes"] > 0
        assert result["total_edges"] >= 0

    def test_find_callers(self, sample_ts_project, tmp_path):
        db_path = tmp_path / "graph.sqlite"
        analyzer = GraphAnalyzer(sample_ts_project, db_path, language="typescript")
        analyzer.build_graph(scope="full")

        result = analyzer.find_callers("createUser")
        assert "caller_count" in result

    def test_analyze_impact(self, sample_ts_project, tmp_path):
        db_path = tmp_path / "graph.sqlite"
        analyzer = GraphAnalyzer(sample_ts_project, db_path, language="typescript")
        analyzer.build_graph(scope="full")

        result = analyzer.analyze_impact("createUser", change_type="modify")

        assert "risk_level" in result
        assert result["risk_level"] in ("low", "medium", "high")
        assert "direct_callers" in result
        assert "transitive_dependents" in result

    def test_force_rebuild(self, sample_ts_project, tmp_path):
        db_path = tmp_path / "graph.sqlite"
        analyzer = GraphAnalyzer(sample_ts_project, db_path, language="typescript")

        result1 = analyzer.build_graph(scope="full")
        result2 = analyzer.build_graph(scope="full", force_rebuild=True)

        assert result1["total_nodes"] == result2["total_nodes"]

    def test_detect_language_ts_project(self, sample_ts_project, tmp_path):
        db_path = tmp_path / "graph.sqlite"
        analyzer = GraphAnalyzer(sample_ts_project, db_path)

        lang = analyzer._detect_language()
        assert lang == "typescript"

    def test_detect_language_js_project(self, sample_js_project, tmp_path):
        db_path = tmp_path / "graph.sqlite"
        analyzer = GraphAnalyzer(sample_js_project, db_path)

        lang = analyzer._detect_language()
        assert lang in ("javascript", "typescript")


class TestGraphDBTypeScript:
    """Test graph database operations with TypeScript nodes."""

    def test_insert_ts_nodes(self, graph_db, sample_ts_project):
        from pyscribe_code.core.ast_parser import FileAnalysis, NodeInfo, EdgeInfo

        analysis = FileAnalysis(
            file_path=str(sample_ts_project / "types.ts"),
            nodes=[
                NodeInfo(str(sample_ts_project / "types.ts"), "User", "interface", 2, "interface User"),
                NodeInfo(str(sample_ts_project / "types.ts"), "UserId", "type", 7, "type UserId = string | number"),
                NodeInfo(str(sample_ts_project / "types.ts"), "Role", "enum", 9, "enum Role"),
            ],
            edges=[],
        )
        graph_db.insert_file_analysis(analysis)

        assert graph_db.get_total_nodes() == 3

    def test_ts_node_types_stored(self, graph_db, sample_ts_project):
        from pyscribe_code.core.ast_parser import FileAnalysis, NodeInfo

        analysis = FileAnalysis(
            file_path=str(sample_ts_project / "types.ts"),
            nodes=[
                NodeInfo(str(sample_ts_project / "types.ts"), "User", "interface", 2),
                NodeInfo(str(sample_ts_project / "types.ts"), "UserId", "type", 7),
                NodeInfo(str(sample_ts_project / "types.ts"), "Role", "enum", 9),
            ],
            edges=[],
        )
        graph_db.insert_file_analysis(analysis)

        callers = graph_db.find_callers("User")
        assert isinstance(callers, list)
