## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    AI Coding Agent                       │
│              (Cursor, Claude, Windsurf, etc.)            │
└────────────────────────┬────────────────────────────────┘
                         │ MCP Protocol (stdio)
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   PyScribe Code MCP                      │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │    Graph     │  │     API      │  │   Sandbox    │  │
│  │  Analyzer    │  │  Verifier    │  │  Validator   │  │
│  │              │  │              │  │              │  │
│  │  - AST Parse │  │  - Local     │  │  - Syntax    │  │
│  │  - tree-sitter│ │  - Known     │  │  - Imports   │  │
│  │  - Build     │  │  - Similar   │  │  - Lint      │  │
│  │  - Impact    │  │  - Doc URL   │  │  - Types     │  │
│  │  - Callers   │  │              │  │              │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                 │                 │          │
│  ┌──────▼───────┐  ┌──────▼───────┐  ┌──────▼───────┐  │
│  │  SQLite DB   │  │  LRU Cache   │  │  subprocess  │  │
│  │  (nodes/     │  │  (256        │  │  (ruff/      │  │
│  │   edges)     │  │  entries)    │  │   mypy/tsc)  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │              Skill Manager                        │   │
│  │                                                   │   │
│  │  - Catalog browsing    - Skill download           │   │
│  │  - Detail inspection   - Local management         │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```


## Key Features

### AST-Powered Analysis
- Parses Python files using the built-in `ast` module
- Parses TypeScript/JavaScript files using `tree-sitter` (TypeScript + TSX languages)
- Extracts functions, classes, methods, interfaces, type aliases, enums, and call relationships
- Supports cross-file call tracking via graph database
- TypeScript-specific: extends/implements relationships, decorator tracking, property signatures

### SQLite Graph Database
- Persistent storage with WAL mode for concurrent access
- SHA-256 file hashing for intelligent cache invalidation
- Incremental rebuild support for changed files only

### Smart Impact Analysis
- Transitive dependency tracking with configurable depth
- Risk level calculation (low/medium/high)
- Automatic test file mapping via AST-based matching

### Multi-Language API Verification
- Python, TypeScript, and JavaScript support
- Local site-packages search
- Known library symbol database (extensible)
- Similarity matching for typos

### Sandbox Validation
- **Python**: Syntax checking via AST parsing, import verification, linting with `ruff`, type checking with `mypy`
- **TypeScript/JavaScript**: Syntax checking via `tsc --noEmit`, linting with `eslint --format json`, type checking via `tsc -p <generated tsconfig.json>` (with `noEmit: true`)
- Selective check execution
- Auto-detects language from file extension

### Skill Management
- GitHub-based skill repository
- Full directory structure preservation
- Catalog browsing with search and pagination
- Local skill management


## Performance

| Operation | Avg Duration | Cached |
|-----------|-------------|--------|
| Full graph build (Python) | ~4-5s | SQLite |
| Full graph build (TypeScript) | ~3-4s | SQLite |
| File graph build | ~100ms | SQLite |
| Impact analysis | ~50ms | LRU |
| Find callers | ~30ms | SQLite |
| API verify (known) | ~5ms | LRU |
| Sandbox (syntax) | ~10ms | - |
| Sandbox (full) | ~1-10s | - |
