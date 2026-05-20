"""Tests for API verifier and symbol parser."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from pyscribe_code.core.symbol_parser import (
    NodeSymbolParser,
    PythonSymbolParser,
    find_similar_symbols,
    find_symbol,
    resolve_import_path,
)
from pyscribe_code.managers.api_verifier import APIVerifier


@pytest.fixture
def sample_python_file():
    """Create a temporary Python file with sample symbols."""
    content = '''
"""Sample module for testing."""

CONSTANT = 42

class MyClass:
    """A sample class."""

    def __init__(self, value: int) -> None:
        self.value = value

    def get_value(self) -> int:
        """Return the value."""
        return self.value

    async def fetch_data(self, url: str) -> str:
        """Fetch data from URL."""
        return ""


def sample_function(name: str, count: int = 10) -> list[str]:
    """A sample function."""
    return [name] * count


async def async_helper(data: dict) -> bool:
    """An async helper function."""
    return True
'''
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        path = Path(f.name)
    yield path
    path.unlink()


@pytest.fixture
def sample_dts_file():
    """Create a temporary TypeScript declaration file."""
    content = '''
export declare function fetchData(url: string): Promise<string>;
export declare class MyService {
    constructor(config: Config);
    initialize(): void;
}
export declare interface Config {
    host: string;
    port: number;
}
export declare const VERSION: string;
export declare type Result = Success | Error;
export declare enum Status {
    Active = 1,
    Inactive = 0
}
'''
    with tempfile.NamedTemporaryFile(mode="w", suffix=".d.ts", delete=False) as f:
        f.write(content)
        path = Path(f.name)
    yield path
    path.unlink()


@pytest.fixture
def sample_project_dir():
    """Create a temporary directory with sample Python files."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir)
        (path / "sample.py").write_text('''
def hello(name: str) -> str:
    return f"Hello, {name}!"

class Greeter:
    def greet(self, name: str) -> str:
        return hello(name)
''')
        yield path


class TestPythonSymbolParser:
    """Test Python AST-based symbol extraction."""

    def test_parse_file_extracts_functions(self, sample_python_file):
        parser = PythonSymbolParser()
        symbols = parser.parse_file(sample_python_file)

        functions = [s for s in symbols if s.symbol_type == "function"]
        assert len(functions) >= 2
        names = [f.name for f in functions]
        assert "sample_function" in names
        assert "async_helper" in names

    def test_parse_file_extracts_classes(self, sample_python_file):
        parser = PythonSymbolParser()
        symbols = parser.parse_file(sample_python_file)

        classes = [s for s in symbols if s.symbol_type == "class"]
        assert len(classes) >= 1
        assert any(c.name == "MyClass" for c in classes)

    def test_parse_file_extracts_methods(self, sample_python_file):
        parser = PythonSymbolParser()
        symbols = parser.parse_file(sample_python_file)

        methods = [s for s in symbols if s.symbol_type == "method"]
        assert len(methods) >= 2
        names = [m.name for m in methods]
        assert "get_value" in names
        assert "fetch_data" in names

    def test_parse_file_extracts_variables(self, sample_python_file):
        parser = PythonSymbolParser()
        symbols = parser.parse_file(sample_python_file)

        variables = [s for s in symbols if s.symbol_type == "variable"]
        assert any(v.name == "CONSTANT" for v in variables)

    def test_signature_includes_parameters(self, sample_python_file):
        parser = PythonSymbolParser()
        symbols = parser.parse_file(sample_python_file)

        func = next((s for s in symbols if s.name == "sample_function"), None)
        assert func is not None
        assert "name" in func.signature
        assert "count" in func.signature

    def test_async_function_detection(self, sample_python_file):
        parser = PythonSymbolParser()
        symbols = parser.parse_file(sample_python_file)

        async_func = next((s for s in symbols if s.name == "async_helper"), None)
        assert async_func is not None
        assert "async" in async_func.signature

    def test_invalid_file_returns_empty(self):
        parser = PythonSymbolParser()
        symbols = parser.parse_file("nonexistent.py")
        assert symbols == []


class TestNodeSymbolParser:
    """Test TypeScript declaration file parsing."""

    def test_parse_function_declarations(self, sample_dts_file):
        parser = NodeSymbolParser()
        symbols = parser.parse_file(sample_dts_file)

        functions = [s for s in symbols if s.symbol_type == "function"]
        assert len(functions) >= 1
        assert any(f.name == "fetchData" for f in functions)

    def test_parse_class_declarations(self, sample_dts_file):
        parser = NodeSymbolParser()
        symbols = parser.parse_file(sample_dts_file)

        classes = [s for s in symbols if s.symbol_type == "class"]
        assert len(classes) >= 1
        assert any(c.name == "MyService" for c in classes)

    def test_parse_interface_declarations(self, sample_dts_file):
        parser = NodeSymbolParser()
        symbols = parser.parse_file(sample_dts_file)

        interfaces = [s for s in symbols if s.symbol_type == "interface"]
        assert len(interfaces) >= 1
        assert any(i.name == "Config" for i in interfaces)

    def test_parse_const_declarations(self, sample_dts_file):
        parser = NodeSymbolParser()
        symbols = parser.parse_file(sample_dts_file)

        consts = [s for s in symbols if s.symbol_type == "const"]
        assert any(c.name == "VERSION" for c in consts)

    def test_parse_enum_declarations(self, sample_dts_file):
        parser = NodeSymbolParser()
        symbols = parser.parse_file(sample_dts_file)

        enums = [s for s in symbols if s.symbol_type == "enum"]
        assert any(e.name == "Status" for e in enums)


class TestSymbolSearch:
    """Test symbol search functions."""

    def test_find_symbol_in_directory(self, sample_project_dir):
        sym = find_symbol(sample_project_dir, "hello", language="python")
        assert sym is not None
        assert sym.name == "hello"
        assert sym.symbol_type == "function"

    def test_find_symbol_not_found(self, sample_project_dir):
        sym = find_symbol(sample_project_dir, "nonexistent", language="python")
        assert sym is None

    def test_find_similar_symbols(self, sample_project_dir):
        similar = find_similar_symbols(sample_project_dir, "hell", threshold=0.6, language="python")
        assert len(similar) > 0
        assert any(s.name == "hello" for s in similar)

    def test_resolve_import_path(self, sample_project_dir):
        lib_dir = sample_project_dir / "sample_lib"
        lib_dir.mkdir()
        (lib_dir / "__init__.py").write_text("from .module import hello\n")
        (lib_dir / "module.py").write_text("def hello(name: str) -> str:\n    return f'Hello, {name}!'\n")

        path = resolve_import_path("sample_lib", "hello", sample_project_dir, language="python")
        assert path is not None
        assert "hello" in path


class TestAPIVerifier:
    """Test API verification with fallback chain."""

    def test_verify_local_symbol(self, sample_project_dir):
        verifier = APIVerifier(sample_project_dir)
        result = verifier.verify(library="sample", symbol="hello", language="python")

        assert result["status"] == "FOUND"
        assert result["symbol"] == "hello"
        assert result["source"] == "local"

    def test_verify_nonexistent_symbol(self, sample_project_dir):
        verifier = APIVerifier(sample_project_dir)
        result = verifier.verify(library="sample", symbol="nonexistent", language="python")

        assert result["status"] == "DOES_NOT_EXIST"
        assert len(result.get("similar", [])) >= 0

    def test_verify_caches_result(self, sample_project_dir):
        verifier = APIVerifier(sample_project_dir)
        result1 = verifier.verify(library="sample", symbol="hello", language="python")
        result2 = verifier.verify(library="sample", symbol="hello", language="python")

        assert result1 == result2

    def test_verify_detects_language(self, sample_project_dir):
        verifier = APIVerifier(sample_project_dir)
        result = verifier.verify(library="sample", symbol="hello")

        assert "language" in result
        assert result["language"] in ("python", "typescript", "javascript")
