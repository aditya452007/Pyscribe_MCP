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
