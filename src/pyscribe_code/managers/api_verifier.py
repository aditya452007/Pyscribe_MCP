"""API verification with fallback chain: local -> known libraries -> doc URL."""

from __future__ import annotations

import logging
import site
import sysconfig
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pyscribe_code.core.symbol_parser import (
    SymbolInfo,
    find_similar_symbols,
    find_symbol,
    resolve_import_path,
)
from pyscribe_core.cache import LRUCache

logger = logging.getLogger(__name__)

KNOWN_SYMBOLS: dict[str, set[str]] = {
    "python": {"print", "len", "range", "str", "int", "list", "dict", "set", "tuple", "bool", "float", "open", "input", "type", "isinstance", "enumerate", "zip", "map", "filter", "sorted", "reversed", "sum", "min", "max", "abs", "round", "any", "all", "hash", "id", "dir", "getattr", "setattr", "hasattr", "callable", "iter", "next", "slice"},
    "fastapi": {"FastAPI", "APIRouter", "Depends", "Body", "Path", "Query", "Header", "Cookie", "HTTPException", "Response", "JSONResponse", "Request", "UploadFile", "File", "Form"},
    "pydantic": {"BaseModel", "Field", "validator", "root_validator", "ValidationError", "EmailStr", "HttpUrl", "PositiveInt", "NegativeFloat", "constr", "conint", "conlist"},
    "numpy": {"array", "zeros", "ones", "eye", "linspace", "arange", "reshape", "dot", "matmul", "transpose", "sum", "mean", "std", "max", "min", "argmax", "argmin", "where", "concatenate", "stack", "split"},
    "pandas": {"DataFrame", "Series", "read_csv", "read_excel", "read_sql", "concat", "merge", "groupby", "pivot_table", "crosstab", "cut", "qcut", "get_dummies", "to_datetime"},
    "django": {"Model", "View", "TemplateView", "Form", "ModelForm", "QuerySet", "HttpResponse", "HttpRequest", "middleware", "admin", "settings", "urls"},
    "flask": {"Flask", "Blueprint", "request", "response", "render_template", "redirect", "url_for", "session", "g", "abort", "jsonify"},
    "sqlalchemy": {"create_engine", "Column", "Integer", "String", "ForeignKey", "relationship", "declarative_base", "sessionmaker", "Session", "select", "insert", "update", "delete"},
    "react": {"useState", "useEffect", "useContext", "useReducer", "useCallback", "useMemo", "useRef", "createContext", "forwardRef", "memo", "Suspense", "lazy"},
}


class APIVerifier:
    """Orchestrates API symbol verification with fallback chain."""

    def __init__(
        self,
        project_root: str | Path,
        known_symbols: dict[str, set[str]] | None = None,
    ) -> None:
        self._project_root = Path(project_root)
        self._cache: LRUCache = LRUCache(maxsize=256)
        self._known_symbols = known_symbols or KNOWN_SYMBOLS

    def verify(
        self,
        library: str,
        symbol: str,
        symbol_type: str = "",
        import_path: str = "",
        doc_url: str = "",
        language: str = "",
    ) -> dict[str, Any]:
        cache_key = f"{library}:{symbol}:{symbol_type}:{language}"
        if cached := self._cache.get(cache_key):
            return cached

        if not language:
            language = self._detect_language(library)

        result: dict[str, Any] = {}

        local_result = self._check_local(library, symbol, language)
        if local_result["status"] == "FOUND":
            local_result["doc_url"] = doc_url if doc_url else None
            local_result["doc_url_valid"] = self._validate_url(doc_url) if doc_url else None
            self._cache.put(cache_key, local_result)
            return local_result

        known_result = self._check_known_library(library, symbol)
        if known_result["status"] == "FOUND":
            known_result["doc_url"] = doc_url if doc_url else None
            known_result["doc_url_valid"] = self._validate_url(doc_url) if doc_url else None
            self._cache.put(cache_key, known_result)
            return known_result

        similar = self._find_similar(library, symbol, language)
        result = {
            "status": "DOES_NOT_EXIST",
            "library": library,
            "symbol": symbol,
            "symbol_type": symbol_type,
            "language": language,
            "similar": similar,
            "message": f"Symbol '{symbol}' not found in '{library}'",
            "doc_url": doc_url if doc_url else None,
            "doc_url_valid": self._validate_url(doc_url) if doc_url else None,
        }

        self._cache.put(cache_key, result)
        return result

    def _check_local(self, library: str, symbol: str, language: str) -> dict[str, Any]:
        search_dirs = self._get_search_dirs(library, language)

        for search_dir in search_dirs:
            if search_dir.name in ("site-packages", "lib", "Lib"):
                lib_subdir = search_dir / library
                if lib_subdir.is_dir():
                    sym = find_symbol(lib_subdir, symbol, symbol_type="", language=language)
                    if sym:
                        import_path = resolve_import_path(library, symbol, self._project_root, language)
                        return {
                            "status": "FOUND",
                            "library": library,
                            "symbol": sym.name,
                            "symbol_type": sym.symbol_type,
                            "language": language,
                            "file_path": sym.file_path,
                            "line_number": sym.line_number,
                            "signature": sym.signature,
                            "import_path": import_path,
                            "source": "local",
                        }
            else:
                sym = find_symbol(search_dir, symbol, symbol_type="", language=language)
                if sym:
                    import_path = resolve_import_path(library, symbol, self._project_root, language)
                    return {
                        "status": "FOUND",
                        "library": library,
                        "symbol": sym.name,
                        "symbol_type": sym.symbol_type,
                        "language": language,
                        "file_path": sym.file_path,
                        "line_number": sym.line_number,
                        "signature": sym.signature,
                        "import_path": import_path,
                        "source": "local",
                    }

        return {
            "status": "NOT_FOUND_LOCAL",
            "library": library,
            "symbol": symbol,
            "language": language,
        }

    def _check_known_library(self, library: str, symbol: str) -> dict[str, Any]:
        if library in self._known_symbols and symbol in self._known_symbols[library]:
            return {
                "status": "FOUND",
                "library": library,
                "symbol": symbol,
                "source": "known_library",
                "message": f"Symbol '{symbol}' is a known symbol in '{library}'",
            }

        return {"status": "NOT_FOUND_KNOWN", "library": library}

    def _find_similar(self, library: str, symbol: str, language: str) -> list[str]:
        search_dirs = self._get_search_dirs(library, language)
        similar_symbols: list[SymbolInfo] = []

        for search_dir in search_dirs:
            if search_dir.name in ("site-packages", "lib", "Lib"):
                lib_subdir = search_dir / library
                if lib_subdir.is_dir():
                    similar_symbols.extend(
                        find_similar_symbols(lib_subdir, symbol, threshold=0.7, language=language)
                    )
            else:
                similar_symbols.extend(
                    find_similar_symbols(search_dir, symbol, threshold=0.7, language=language)
                )

        results = []
        for sym in similar_symbols[:5]:
            entry = f"{sym.name} ({sym.symbol_type})"
            if sym.signature:
                entry += f" - {sym.signature}"
            results.append(entry)

        return results

    def _get_search_dirs(self, library: str, language: str) -> list[Path]:
        dirs: list[Path] = []

        if language == "python":
            real_site_packages = [Path(p) for p in site.getsitepackages()]
            real_site_packages += [Path(site.getusersitepackages())]
            user_site = sysconfig.get_path("purelib")
            if user_site:
                real_site_packages.append(Path(user_site))
            stdlib = sysconfig.get_path("stdlib")
            if stdlib:
                dirs.append(Path(stdlib))

            for d in real_site_packages:
                if d.is_dir():
                    dirs.append(d)

            project_site_packages = list(self._project_root.rglob("site-packages"))
            project_lib = list(self._project_root.rglob("lib"))
            dirs.extend(project_site_packages)
            dirs.extend(project_lib)

            lib_dir = self._project_root / library
            if lib_dir.is_dir():
                dirs.append(lib_dir)

            src_dir = self._project_root / "src"
            if src_dir.is_dir():
                dirs.append(src_dir)

            dirs.append(self._project_root)

        elif language in ("typescript", "javascript"):
            node_modules = self._project_root / "node_modules" / library
            if node_modules.is_dir():
                dirs.append(node_modules)

            node_modules_root = self._project_root / "node_modules"
            if node_modules_root.is_dir():
                dirs.append(node_modules_root)

            dirs.append(self._project_root)

        return [d for d in dirs if d.is_dir()]

    def _detect_language(self, library: str) -> str:
        py_files = list(self._project_root.glob("**/*.py"))
        ts_files = list(self._project_root.glob("**/*.ts"))
        dts_files = list(self._project_root.glob("**/*.d.ts"))
        js_files = list(self._project_root.glob("**/*.js"))

        py_count = len(py_files)
        ts_count = len(ts_files) + len(dts_files)
        js_count = len(js_files)

        if py_count > ts_count and py_count > js_count:
            return "python"
        if ts_count > py_count and ts_count > js_count:
            return "typescript"
        if js_count > py_count and js_count > ts_count:
            return "javascript"

        if library in ("fastapi", "flask", "django", "pydantic", "numpy", "pandas"):
            return "python"
        if library in ("react", "express", "typescript", "next"):
            return "typescript"

        return "python"

    @staticmethod
    def _validate_url(url: str) -> bool:
        try:
            parsed = urlparse(url)
            return all([parsed.scheme in ("http", "https"), parsed.netloc])
        except Exception:
            return False
