# PyScribe Code MCP

<p align="center">
  <strong>AI-Powered Code Analysis MCP Server</strong><br>
  <em>AST parsing, call graphs, impact analysis, API verification, sandbox validation & skill management</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12%2B-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/TypeScript-5.0%2B-3178C6?style=for-the-badge&logo=typescript&logoColor=white" alt="TypeScript 5.0+">
  <img src="https://img.shields.io/badge/MCP-Protocol-orange?style=for-the-badge&logo=mcp&logoColor=white" alt="MCP Protocol">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="MIT License">
  <img src="https://img.shields.io/badge/Tools-9-purple?style=for-the-badge" alt="9 Tools">
  <img src="https://img.shields.io/badge/Tests-162%2F162%20Passing-brightgreen?style=for-the-badge" alt="162/162 Tests Passing">
</p>

---

## What is PyScribe Code MCP?

PyScribe Code is a **Model Context Protocol (MCP) server** that gives AI coding agents (Cursor, Claude Code, Windsurf, Cline, etc.) deep code understanding capabilities. It analyzes your codebase using AST parsing (Python via `ast`, TypeScript/JavaScript via `tree-sitter`), builds call graphs, performs impact analysis, verifies API symbols, validates code in a sandbox, and manages reusable skills.

**Supported languages:** Python (.py), TypeScript (.ts, .tsx), JavaScript (.js, .jsx)

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

## Documentation

The documentation has been split into multiple files for better organization:

*   [Connect Your Agent](docs/agents.md)
*   [Available Tools & Usage](docs/tools.md)
*   [Installation & Configuration](docs/installation.md)
*   [Architecture & Performance](docs/architecture.md)
*   [Development & Contributing](docs/development.md)

---

## License

[MIT](LICENSE)

---

<p align="center">
  <em>Built with care for AI coding agents that need to understand code, not just read it.</em>
</p>
