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
