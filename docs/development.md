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


## Troubleshooting

### "The codebase graph is empty"
Run `analyze-codebase-graph` with `scope="full"` first before using `analyze-impact` or `find-callers`.

### mypy check timeout
The type check timeout is set to 10 seconds. For large files, run `sandbox-validate` with `checks=["syntax","imports","lint"]` to skip type checking.

### Skill download fails
Check network connectivity and verify the skill source URL in your configuration.

### No callers found for a symbol
The symbol may be called dynamically (via `getattr`, decorators, etc.) or the graph may not be fully built. Try `force_rebuild: true`.


## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
