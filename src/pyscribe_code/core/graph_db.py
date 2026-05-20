"""SQLite-based graph storage for codebase analysis."""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, ClassVar

from pyscribe_code.core.ast_parser import FileAnalysis

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    symbol_name TEXT NOT NULL,
    symbol_type TEXT NOT NULL,
    line_number INTEGER NOT NULL,
    signature TEXT,
    UNIQUE(file_path, symbol_name, line_number)
);

CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,
    edge_type TEXT NOT NULL,
    line_number INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (source_id) REFERENCES nodes(id),
    FOREIGN KEY (target_id) REFERENCES nodes(id)
);

CREATE TABLE IF NOT EXISTS file_hashes (
    file_path TEXT PRIMARY KEY,
    hash TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_nodes_symbol ON nodes(symbol_name);
CREATE INDEX IF NOT EXISTS idx_nodes_file ON nodes(file_path);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
"""


class GraphDB:
    """Store and query codebase call graph using SQLite."""

    DEFAULT_RISK_CONFIG: ClassVar[dict[str, float]] = {
        "high_ratio": 0.5,
        "high_count": 10,
        "medium_ratio": 0.2,
        "medium_count": 5,
    }

    def __init__(
        self,
        db_path: str | Path,
        risk_config: dict[str, float] | None = None,
    ) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._risk_config = risk_config or self.DEFAULT_RISK_CONFIG
        self._init_db()

    def _init_db(self) -> None:
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.executescript(SCHEMA)
        except sqlite3.Error as e:
            logger.error("Failed to initialize graph DB: %s", e)
            raise

    def insert_file_analysis(self, analysis: FileAnalysis) -> None:
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()

                for node in analysis.nodes:
                    cursor.execute(
                        """INSERT OR IGNORE INTO nodes (file_path, symbol_name, symbol_type, line_number, signature)
                           VALUES (?, ?, ?, ?, ?)""",
                        (node.file_path, node.symbol_name, node.symbol_type, node.line_number, node.signature),
                    )

                for edge in analysis.edges:
                    source_id = self._get_node_id(cursor, edge.source, analysis.file_path)
                    target_id = self._get_node_id(cursor, edge.target, analysis.file_path)

                    if source_id and target_id:
                        cursor.execute(
                            """INSERT INTO edges (source_id, target_id, edge_type, line_number)
                               VALUES (?, ?, ?, ?)""",
                            (source_id, target_id, edge.edge_type, edge.line_number),
                        )

                file_hash = self._compute_file_hash(analysis.file_path)
                cursor.execute(
                    """INSERT OR REPLACE INTO file_hashes (file_path, hash, updated_at)
                       VALUES (?, ?, ?)""",
                    (analysis.file_path, file_hash, time.time()),
                )

        except sqlite3.Error as e:
            logger.warning("Failed to insert analysis for %s: %s", analysis.file_path, e)

    def remove_file_analysis(self, file_path: str) -> None:
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM nodes WHERE file_path = ?", (file_path,))
                node_ids = [row[0] for row in cursor.fetchall()]

                if node_ids:
                    placeholders = ",".join("?" * len(node_ids))
                    cursor.execute(f"DELETE FROM edges WHERE source_id IN ({placeholders}) OR target_id IN ({placeholders})", node_ids + node_ids)
                    cursor.execute(f"DELETE FROM nodes WHERE id IN ({placeholders})", node_ids)

                cursor.execute("DELETE FROM file_hashes WHERE file_path = ?", (file_path,))
        except sqlite3.Error as e:
            logger.warning("Failed to remove analysis for %s: %s", file_path, e)

    def find_callers(self, symbol: str) -> list[dict[str, Any]]:
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT n1.symbol_name, n1.file_path, n1.symbol_type, n1.line_number, e.line_number as call_line
                       FROM edges e
                       JOIN nodes n1 ON e.source_id = n1.id
                       JOIN nodes n2 ON e.target_id = n2.id
                       WHERE n2.symbol_name = ? AND e.edge_type = 'calls'""",
                    (symbol,),
                )
                return [
                    {
                        "caller": row[0],
                        "caller_file": row[1],
                        "caller_type": row[2],
                        "caller_line": row[3],
                        "call_line": row[4],
                    }
                    for row in cursor.fetchall()
                ]
        except sqlite3.Error as e:
            logger.warning("Failed to find callers for %s: %s", symbol, e)
            return []

    def find_callees(self, symbol: str) -> list[dict[str, Any]]:
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT n2.symbol_name, n2.file_path, n2.symbol_type, n2.line_number, e.line_number as call_line
                       FROM edges e
                       JOIN nodes n1 ON e.source_id = n1.id
                       JOIN nodes n2 ON e.target_id = n2.id
                       WHERE n1.symbol_name = ? AND e.edge_type = 'calls'""",
                    (symbol,),
                )
                return [
                    {
                        "callee": row[0],
                        "callee_file": row[1],
                        "callee_type": row[2],
                        "callee_line": row[3],
                        "call_line": row[4],
                    }
                    for row in cursor.fetchall()
                ]
        except sqlite3.Error as e:
            logger.warning("Failed to find callees for %s: %s", symbol, e)
            return []

    def find_transitive_dependents(self, symbol: str, max_depth: int = 3) -> list[dict[str, Any]]:
        dependents: list[dict[str, Any]] = []
        visited: set[str] = {symbol}
        current_level = [symbol]

        for depth in range(max_depth):
            next_level = []
            for sym in current_level:
                callers = self.find_callers(sym)
                for caller in callers:
                    caller_name = caller["caller"]
                    if caller_name not in visited:
                        visited.add(caller_name)
                        caller["depth"] = depth + 1
                        dependents.append(caller)
                        next_level.append(caller_name)
            current_level = next_level
            if not current_level:
                break

        return dependents

    def calculate_impact_ratio(self, symbol: str, change_type: str = "modify") -> dict[str, Any]:
        dependents = self.find_transitive_dependents(symbol)
        total_nodes = self.get_total_nodes()

        direct_callers = len(self.find_callers(symbol))
        transitive_count = len(dependents)

        impact_ratio = transitive_count / total_nodes if total_nodes > 0 else 0

        cfg = self._risk_config
        if impact_ratio > cfg["high_ratio"] and transitive_count > cfg["high_count"]:
            risk = "high"
        elif impact_ratio > cfg["medium_ratio"] and transitive_count > cfg["medium_count"]:
            risk = "medium"
        else:
            risk = "low"

        return {
            "symbol": symbol,
            "change_type": change_type,
            "direct_callers": direct_callers,
            "transitive_dependents": transitive_count,
            "total_nodes": total_nodes,
            "impact_ratio": round(impact_ratio, 3),
            "risk_level": risk,
        }

    def get_module_dependencies(self) -> list[dict[str, Any]]:
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT DISTINCT n1.file_path, n2.file_path, COUNT(*) as call_count
                       FROM edges e
                       JOIN nodes n1 ON e.source_id = n1.id
                       JOIN nodes n2 ON e.target_id = n2.id
                       WHERE n1.file_path != n2.file_path AND e.edge_type = 'calls'
                       GROUP BY n1.file_path, n2.file_path
                       ORDER BY call_count DESC""",
                )
                return [
                    {
                        "source_file": row[0],
                        "target_file": row[1],
                        "call_count": row[2],
                    }
                    for row in cursor.fetchall()
                ]
        except sqlite3.Error as e:
            logger.warning("Failed to get module dependencies: %s", e)
            return []

    def get_hotspots(self, top_n: int = 10) -> list[dict[str, Any]]:
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT n.symbol_name, n.file_path, n.symbol_type, COUNT(*) as caller_count
                       FROM edges e
                       JOIN nodes n ON e.target_id = n.id
                       WHERE e.edge_type = 'calls'
                       GROUP BY n.symbol_name, n.file_path
                       ORDER BY caller_count DESC
                       LIMIT ?""",
                    (top_n,),
                )
                return [
                    {
                        "symbol": row[0],
                        "file": row[1],
                        "type": row[2],
                        "caller_count": row[3],
                    }
                    for row in cursor.fetchall()
                ]
        except sqlite3.Error as e:
            logger.warning("Failed to get hotspots: %s", e)
            return []

    def get_total_nodes(self) -> int:
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM nodes")
                return cursor.fetchone()[0]
        except sqlite3.Error:
            return 0

    def get_total_edges(self) -> int:
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM edges")
                return cursor.fetchone()[0]
        except sqlite3.Error:
            return 0

    def get_nodes_for_file(self, file_path: str) -> int:
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM nodes WHERE file_path = ?", (file_path,))
                return cursor.fetchone()[0]
        except sqlite3.Error:
            return 0

    def get_edges_for_file(self, file_path: str) -> int:
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT COUNT(*) FROM edges e
                       JOIN nodes n ON e.source_id = n.id
                       WHERE n.file_path = ?""",
                    (file_path,),
                )
                return cursor.fetchone()[0]
        except sqlite3.Error:
            return 0

    def get_hotspots_for_file(self, file_path: str, top_n: int = 5) -> list[dict[str, Any]]:
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT n.symbol_name, n.file_path, n.symbol_type, COUNT(*) as caller_count
                       FROM edges e
                       JOIN nodes n ON e.target_id = n.id
                       WHERE e.edge_type = 'calls' AND n.file_path = ?
                       GROUP BY n.symbol_name, n.file_path
                       ORDER BY caller_count DESC
                       LIMIT ?""",
                    (file_path, top_n),
                )
                return [
                    {
                        "symbol": row[0],
                        "file": row[1],
                        "type": row[2],
                        "caller_count": row[3],
                    }
                    for row in cursor.fetchall()
                ]
        except sqlite3.Error:
            return []

    def get_module_dependencies_for_file(self, file_path: str) -> list[dict[str, Any]]:
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT DISTINCT n1.file_path, n2.file_path, COUNT(*) as call_count
                       FROM edges e
                       JOIN nodes n1 ON e.source_id = n1.id
                       JOIN nodes n2 ON e.target_id = n2.id
                       WHERE n1.file_path = ? AND n1.file_path != n2.file_path AND e.edge_type = 'calls'
                       GROUP BY n1.file_path, n2.file_path
                       ORDER BY call_count DESC""",
                    (file_path,),
                )
                return [
                    {
                        "source_file": row[0],
                        "target_file": row[1],
                        "call_count": row[2],
                    }
                    for row in cursor.fetchall()
                ]
        except sqlite3.Error:
            return []

    def invalidate_file(self, file_path: str) -> None:
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("DELETE FROM file_hashes WHERE file_path = ?", (file_path,))
        except sqlite3.Error as e:
            logger.warning("Failed to invalidate file %s: %s", file_path, e)

    def is_file_cached(self, file_path: str) -> bool:
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT hash FROM file_hashes WHERE file_path = ?", (file_path,))
                row = cursor.fetchone()
                if not row:
                    return False

                current_hash = self._compute_file_hash(file_path)
                return row[0] == current_hash
        except (sqlite3.Error, OSError):
            return False

    def _get_node_id(self, cursor: sqlite3.Cursor, symbol_name: str, file_path: str) -> int | None:
        cursor.execute(
            "SELECT id FROM nodes WHERE symbol_name = ? AND file_path = ?",
            (symbol_name, file_path),
        )
        row = cursor.fetchone()
        return row[0] if row else None

    @staticmethod
    def _compute_file_hash(file_path: str) -> str:
        try:
            content = Path(file_path).read_bytes()
            return hashlib.sha256(content).hexdigest()
        except OSError:
            return ""
