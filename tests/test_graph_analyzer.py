"""Tests for codebase graph analyzer."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pyscribe_code.core.ast_parser import PythonASTParser, SymbolVisitor
from pyscribe_code.core.graph_db import GraphDB
from pyscribe_code.managers.graph_analyzer import GraphAnalyzer


@pytest.fixture
def sample_project():
    """Create a temporary project with multiple Python files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir)

        (path / "utils.py").write_text('''
def helper(x: int) -> int:
    return x * 2

def format_result(value: str) -> str:
    return f"Result: {value}"
''')

        (path / "service.py").write_text('''
from utils import helper

class Service:
    def __init__(self) -> None:
        pass

    def process(self, data: int) -> int:
        return helper(data)

    def run(self) -> str:
        result = self.process(42)
        return str(result)
''')

        (path / "main.py").write_text('''
from service import Service

def main() -> None:
    svc = Service()
    output = svc.run()
    print(output)

if __name__ == "__main__":
    main()
''')

        yield path


@pytest.fixture
def graph_db(tmp_path):
    """Create a temporary graph database."""
    db_path = tmp_path / "test_graph.sqlite"
    return GraphDB(db_path)


class TestPythonASTParser:
    """Test AST parsing of Python files."""

    def test_parses_functions(self, sample_project):
        parser = PythonASTParser()
        analysis = parser.parse_file(sample_project / "utils.py")

        functions = [n for n in analysis.nodes if n.symbol_type == "function"]
        assert len(functions) == 2
        names = [f.symbol_name for f in functions]
        assert "helper" in names
        assert "format_result" in names

    def test_parses_classes(self, sample_project):
        parser = PythonASTParser()
        analysis = parser.parse_file(sample_project / "service.py")

        classes = [n for n in analysis.nodes if n.symbol_type == "class"]
        assert len(classes) == 1
        assert classes[0].symbol_name == "Service"

    def test_parses_methods(self, sample_project):
        parser = PythonASTParser()
        analysis = parser.parse_file(sample_project / "service.py")

        methods = [n for n in analysis.nodes if n.symbol_type == "method"]
        assert len(methods) >= 2
        names = [m.symbol_name for m in methods]
        assert "Service.process" in names
        assert "Service.run" in names

    def test_extracts_call_edges(self, sample_project):
        parser = PythonASTParser()
        analysis = parser.parse_file(sample_project / "service.py")

        call_edges = [e for e in analysis.edges if e.edge_type == "calls"]
        assert len(call_edges) > 0

    def test_parses_directory(self, sample_project):
        parser = PythonASTParser()
        analyses = parser.parse_directory(sample_project)

        assert len(analyses) == 3
        files = {a.file_path for a in analyses}
        assert any("utils.py" in f for f in files)
        assert any("service.py" in f for f in files)
        assert any("main.py" in f for f in files)

    def test_excludes_venv(self, sample_project):
        venv_dir = sample_project / "venv" / "lib"
        venv_dir.mkdir(parents=True)
        (venv_dir / "site.py").write_text("def bad(): pass")

        parser = PythonASTParser()
        analyses = parser.parse_directory(sample_project)

        for a in analyses:
            assert "venv" not in a.file_path


class TestGraphDB:
    """Test graph database operations."""

    def test_insert_and_query_nodes(self, graph_db, sample_project):
        from pyscribe_code.core.ast_parser import FileAnalysis, NodeInfo, EdgeInfo

        analysis = FileAnalysis(
            file_path=str(sample_project / "utils.py"),
            nodes=[
                NodeInfo(str(sample_project / "utils.py"), "helper", "function", 2, "def helper(x: int) -> int"),
            ],
            edges=[],
        )
        graph_db.insert_file_analysis(analysis)

        callers = graph_db.find_callers("helper")
        assert len(callers) == 0

    def test_cache_validity(self, graph_db, sample_project):
        assert not graph_db.is_file_cached(str(sample_project / "utils.py"))

    def test_invalidate_file(self, graph_db, sample_project):
        graph_db.invalidate_file(str(sample_project / "utils.py"))

    def test_total_counts(self, graph_db):
        assert graph_db.get_total_nodes() == 0
        assert graph_db.get_total_edges() == 0


class TestGraphAnalyzer:
    """Test high-level graph analysis."""

    def test_build_graph(self, sample_project, tmp_path):
        db_path = tmp_path / "graph.sqlite"
        analyzer = GraphAnalyzer(sample_project, db_path)

        result = analyzer.build_graph(scope="full")

        assert result["total_nodes"] > 0
        assert result["total_edges"] >= 0

    def test_find_callers(self, sample_project, tmp_path):
        db_path = tmp_path / "graph.sqlite"
        analyzer = GraphAnalyzer(sample_project, db_path)
        analyzer.build_graph(scope="full")

        result = analyzer.find_callers("helper")
        assert "caller_count" in result

    def test_analyze_impact(self, sample_project, tmp_path):
        db_path = tmp_path / "graph.sqlite"
        analyzer = GraphAnalyzer(sample_project, db_path)
        analyzer.build_graph(scope="full")

        result = analyzer.analyze_impact("helper", change_type="modify")

        assert "risk_level" in result
        assert result["risk_level"] in ("low", "medium", "high")
        assert "direct_callers" in result
        assert "transitive_dependents" in result

    def test_force_rebuild(self, sample_project, tmp_path):
        db_path = tmp_path / "graph.sqlite"
        analyzer = GraphAnalyzer(sample_project, db_path)

        result1 = analyzer.build_graph(scope="full")
        result2 = analyzer.build_graph(scope="full", force_rebuild=True)

        assert result1["total_nodes"] == result2["total_nodes"]

    def test_detect_language(self, sample_project, tmp_path):
        db_path = tmp_path / "graph.sqlite"
        analyzer = GraphAnalyzer(sample_project, db_path)

        lang = analyzer._detect_language()
        assert lang == "python"
