## Installation

### From Source (Recommended for Development)

```bash
# Clone the repository
git clone https://github.com/aditya452007/Pyscribe_MCP.git
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
    url: "https://github.com/aditya452007/skills"

http:
  timeout: 30
  max_retries: 3

cache:
  ttl: 3600
  max_size: 256
```


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

