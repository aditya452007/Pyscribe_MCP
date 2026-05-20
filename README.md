# PyScribe Code MCP

<p align="center">
  <strong>AI-Powered Code Analysis MCP Server</strong><br>
  <em>AST parsing, call graphs, impact analysis, API verification, sandbox validation & skill management</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12%2B-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/MCP-Protocol-orange?style=for-the-badge&logo=mcp&logoColor=white" alt="MCP Protocol">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="MIT License">
  <img src="https://img.shields.io/badge/Tools-9-purple?style=for-the-badge" alt="9 Tools">
  <img src="https://img.shields.io/badge/Tests-35%2F35%20Passing-brightgreen?style=for-the-badge" alt="35/35 Tests Passing">
</p>

---

## What is PyScribe Code MCP?

PyScribe Code is a **Model Context Protocol (MCP) server** that gives AI coding agents (Cursor, Claude Code, Windsurf, Cline, etc.) deep code understanding capabilities. It analyzes your codebase using AST parsing, builds call graphs, performs impact analysis, verifies API symbols, validates code in a sandbox, and manages reusable skills.

**Think of it as giving your AI agent X-ray vision into your codebase.**

---

## Quick Start

```bash
# 1. Install
pip install .

# 2. Run the MCP server
pyscribe-code

# 3. Connect your AI agent and start coding with superpowers
```

---

## Connect Your Agent

### Cursor

Add to your Cursor MCP configuration (`.cursor/mcp.json` or Settings > MCP):

```json
{
  "mcpServers": {
    "pyscribe-code": {
      "command": "python",
      "args": ["-m", "pyscribe_code"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

### Claude Code

Add to your `~/.claude/CLAUDE.md` or project-level `CLAUDE.md`:

```
Use the pyscribe-code MCP server for code analysis.
Available tools: analyze-codebase-graph, analyze-impact, find-callers,
verify-api, sandbox-validate, list-skill-catalog, get-skill-detail,
download-skill, list-installed-skills
```

Or configure in `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "pyscribe-code": {
      "command": "python",
      "args": ["-m", "pyscribe_code"],
      "cwd": "${workspace}"
    }
  }
}
```

### Windsurf / Cline

Add to your MCP settings:

```json
{
  "mcpServers": {
    "pyscribe-code": {
      "command": "python",
      "args": ["-m", "pyscribe_code"],
      "env": {},
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

### OpenCode

Add to your `opencode.json`:

```json
{
  "mcp": {
    "pyscribe-code": {
      "command": ["python", "-m", "pyscribe_code"],
      "cwd": "."
    }
  }
}
```

### Any MCP-Compatible Agent

PyScribe Code uses the **stdio transport**, making it compatible with any agent that supports the MCP protocol. Simply point your agent to:

```
Command: python
Args:    -m pyscribe_code
CWD:     your project root
```

---

## Available Tools

PyScribe Code provides **9 powerful tools** for AI agents:

### Code Analysis

| Tool | Description | When to Use |
|------|-------------|-------------|
| `analyze-codebase-graph` | Build AST-based call graph of functions/classes | **Always call first** before impact analysis or finding callers |
| `analyze-impact` | Analyze impact of modifying/deleting/renaming a symbol | Before refactoring to understand blast radius |
| `find-callers` | Find all callers of a specific function or method | Understanding usage patterns of a function |

### API Verification

| Tool | Description | When to Use |
|------|-------------|-------------|
| `verify-api` | Verify if an API symbol exists in a library | Checking if a function/class exists before using it |

### Code Validation

| Tool | Description | When to Use |
|------|-------------|-------------|
| `sandbox-validate` | Validate code: syntax, imports, lint, types | **Always call before writing code** to disk |

### Skill Management

| Tool | Description | When to Use |
|------|-------------|-------------|
| `list-skill-catalog` | Browse available skills from GitHub | Discover new capabilities |
| `get-skill-detail` | Get detailed info about a skill | Before downloading |
| `download-skill` | Download a skill directory | Install a skill |
| `list-installed-skills` | List locally installed skills | Check what's available |

---

## Tool Usage Examples

### 1. Analyze Your Codebase

```
Tool: analyze-codebase-graph
Args: {"scope": "full", "force_rebuild": true}

# Analyze a single file
Args: {"scope": "file", "path": "src/main.py"}

# Analyze a module/directory
Args: {"scope": "module", "path": "src/services"}
```

### 2. Find Who Calls a Function

```
Tool: find-callers
Args: {"symbol": "validate_email"}

# Filter by specific file
Args: {"symbol": "validate_email", "file_path": "src/auth.py"}
```

### 3. Assess Refactoring Impact

```
Tool: analyze-impact
Args: {"symbol": "process_order", "change_type": "modify", "max_depth": 3}

# What happens if we delete this?
Args: {"symbol": "legacy_handler", "change_type": "delete", "max_depth": 5}
```

### 4. Verify API Exists

```
Tool: verify-api
Args: {"library": "fastapi", "symbol": "FastAPI"}

# Check a React hook
Args: {"library": "react", "symbol": "useState", "language": "typescript"}

# With documentation URL
Args: {"library": "pydantic", "symbol": "BaseModel", "doc_url": "https://docs.pydantic.dev"}
```

### 5. Validate Code Before Writing

```
Tool: sandbox-validate
Args: {
  "code": "def greet(name: str) -> str:\n    return f'Hello, {name}!'",
  "file_path": "src/utils.py",
  "python_version": "3.12",
  "checks": ["syntax", "imports", "lint", "types"]
}
```

### 6. Browse & Download Skills

```
# List all available skills
Tool: list-skill-catalog
Args: {"limit": 20, "offset": 0}

# Search for specific skills
Args: {"query": "graph"}

# Get details before downloading
Tool: get-skill-detail
Args: {"skill_name": "graphql"}

# Download a skill
Tool: download-skill
Args: {"skill_name": "graphql"}

# Check installed skills
Tool: list-installed-skills
```

---

## Typical Workflow

```
1. analyze-codebase-graph(scope="full")     ← Build the graph
        ↓
2. find-callers(symbol="my_func")           ← Find usage
        ↓
3. analyze-impact(symbol="my_func")         ← Assess risk
        ↓
4. verify-api(library="fastapi", ...)       ← Verify dependencies
        ↓
5. sandbox-validate(code="...")             ← Validate changes
        ↓
6. Write code to disk (only if can_write=true)
```

---

## Installation

### From Source (Recommended for Development)

```bash
# Clone the repository
git clone https://github.com/your-org/pyscribe.git
cd pyscribe

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v
```

### Direct Install

```bash
pip install pyscribe
```

---

## Running the Server

### Development Mode (with verbose logging)

```bash
python -m pyscribe_code --verbose
```

### Production Mode

```bash
pyscribe-code
```

### With Custom Configuration

Create a `.pyscribe/config.yaml`:

```yaml
skill_sources:
  - name: "default"
    url: "https://github.com/your-org/skills"

http:
  timeout: 30
  max_retries: 3

cache:
  ttl: 3600
  max_size: 256
```

---

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
│  │  - Build     │  │  - Known     │  │  - Imports   │  │
│  │  - Impact    │  │  - Similar   │  │  - Lint      │  │
│  │  - Callers   │  │  - Doc URL   │  │  - Types     │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                 │                 │          │
│  ┌──────▼───────┐  ┌──────▼───────┐  ┌──────▼───────┐  │
│  │  SQLite DB   │  │  LRU Cache   │  │  subprocess  │  │
│  │  (nodes/     │  │  (256        │  │  (ruff/      │  │
│  │   edges)     │  │  entries)    │  │   mypy)      │  │
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

---

## Key Features

### AST-Powered Analysis
- Parses Python files using the built-in `ast` module
- Extracts functions, classes, methods, and call relationships
- Supports cross-file call tracking via graph database

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
- Syntax checking via AST parsing
- Import verification
- Linting with `ruff`
- Type checking with `mypy`
- Selective check execution

### Skill Management
- GitHub-based skill repository
- Full directory structure preservation
- Catalog browsing with search and pagination
- Local skill management

---

## Development

### Project Structure

```
pyscribe/
├── src/
│   ├── pyscribe_code/          # MCP server & tools
│   │   ├── server.py           # MCP tool definitions & handlers
│   │   ├── core/
│   │   │   ├── ast_parser.py   # Python AST parsing
│   │   │   ├── graph_db.py     # SQLite graph storage
│   │   │   └── symbol_parser.py# Symbol extraction utilities
│   │   └── managers/
│   │       ├── graph_analyzer.py   # Orchestration layer
│   │       ├── api_verifier.py     # API verification
│   │       ├── sandbox_validator.py# Code validation
│   │       └── skill_manager.py    # Skill management
│   └── pyscribe_core/          # Shared utilities
│       ├── cache.py            # LRU cache
│       ├── config.py           # YAML configuration
│       ├── errors.py           # Exception hierarchy
│       ├── http.py             # Async HTTP client
│       └── retry.py            # Exponential backoff
├── tests/                      # Test suite
└── pyproject.toml              # Project configuration
```

### Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=src/pyscribe_core,src/pyscribe_code

# Specific test file
pytest tests/test_graph_analyzer.py -v
```

### Linting & Type Checking

```bash
# Lint
ruff check src/

# Type check
mypy src/
```

---

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PYSCRIBE_MAX_RETRIES` | `3` | Maximum HTTP retry attempts |
| `PYSCRIBE_CACHE_TTL` | `3600` | Cache TTL in seconds |
| `PYSCRIBE_LOG_LEVEL` | `INFO` | Logging level |

### Tool Parameters

#### `analyze-codebase-graph`
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `scope` | `string` | No | `"full"` | `full`, `file`, or `module` |
| `path` | `string` | Conditional | - | File/dir path for `file`/`module` scope |
| `force_rebuild` | `boolean` | No | `false` | Force rebuild cache |

#### `analyze-impact`
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `symbol` | `string` | **Yes** | - | Symbol name to analyze |
| `change_type` | `string` | No | `"modify"` | `modify`, `delete`, or `rename` |
| `max_depth` | `integer` | No | `3` | Transitive depth (1-5) |

#### `sandbox-validate`
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `code` | `string` | **Yes** | - | Python code to validate |
| `file_path` | `string` | No | - | Intended file path |
| `python_version` | `string` | No | - | Target Python version |
| `checks` | `array` | No | `["syntax","imports","lint","types"]` | Checks to run |
| `dependencies` | `array` | No | - | Import names to verify |

---

## Performance

| Operation | Avg Duration | Cached |
|-----------|-------------|--------|
| Full graph build | ~4-5s | SQLite |
| File graph build | ~100ms | SQLite |
| Impact analysis | ~50ms | LRU |
| Find callers | ~30ms | SQLite |
| API verify (known) | ~5ms | LRU |
| Sandbox (syntax) | ~10ms | - |
| Sandbox (full) | ~1-10s | - |

---

## Troubleshooting

### "The codebase graph is empty"
Run `analyze-codebase-graph` with `scope="full"` first before using `analyze-impact` or `find-callers`.

### mypy check timeout
The type check timeout is set to 10 seconds. For large files, run `sandbox-validate` with `checks=["syntax","imports","lint"]` to skip type checking.

### Skill download fails
Check network connectivity and verify the skill source URL in your configuration.

### No callers found for a symbol
The symbol may be called dynamically (via `getattr`, decorators, etc.) or the graph may not be fully built. Try `force_rebuild: true`.

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

[MIT](LICENSE)

---

<p align="center">
  <em>Built with care for AI coding agents that need to understand code, not just read it.</em>
</p>
