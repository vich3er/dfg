"""
AST-захист для SQL (sqlglot): лише ОДИН оператор SELECT, білий список таблиць, заборона небезпечних функцій/вузлів,
примусовий LIMIT. Рівень верифікації V2 (парсер, права).
"""
from __future__ import annotations
from dataclasses import dataclass
import sqlglot
from sqlglot import exp

ALLOWED_TABLES = {"fact_feedback_mention", "dim_date", "dim_department", "dim_patient", "dim_topic",
                  "dim_channel", "dim_feedback", "topic_relation"}
FORBIDDEN_FUNC_PREFIXES = ("read_", "write_", "glob", "copy", "pragma", "duckdb_", "sniff_", "getenv",
                           "current_setting", "parquet_", "query", "http", "iceberg", "delta_", "load", "install", "system")
_FORBIDDEN_NODE_NAMES = ("Insert", "Update", "Delete", "Drop", "Create", "Alter", "Command", "Copy", "Pragma",
                         "Set", "Use", "Merge", "TruncateTable", "Transaction", "Commit", "Rollback", "Into",
                         "Attach", "Detach", "Export", "Install", "LoadData", "Grant", "Show", "Describe")
FORBIDDEN_NODES = tuple(getattr(exp, n) for n in _FORBIDDEN_NODE_NAMES if hasattr(exp, n))
SELECT_TYPES = tuple(getattr(exp, n) for n in ("Select", "Union", "SetOperation") if hasattr(exp, n))


@dataclass
class GuardResult:
    ok: bool
    sql: str | None = None      # безпечний SQL (з LIMIT) якщо ok
    reason: str = ""


def validate(sql: str, max_limit: int = 1000) -> GuardResult:
    if not sql or not sql.strip():
        return GuardResult(False, None, "порожній запит")
    try:
        trees = [t for t in sqlglot.parse(sql, read="duckdb") if t is not None]
    except sqlglot.errors.SqlglotError as e:
        return GuardResult(False, None, f"помилка парсингу: {str(e).splitlines()[0][:100]}")
    if len(trees) != 1:
        return GuardResult(False, None, "дозволено рівно один оператор")
    tree = trees[0]
    if not isinstance(tree, SELECT_TYPES):
        return GuardResult(False, None, f"не SELECT ({type(tree).__name__})")
    for node in tree.walk():
        n = node[0] if isinstance(node, tuple) else node
        if isinstance(n, FORBIDDEN_NODES):
            return GuardResult(False, None, f"заборонений вузол: {type(n).__name__}")
    cte_names = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    for t in tree.find_all(exp.Table):
        name = (t.name or "").lower()
        if not isinstance(t.this, exp.Identifier):
            return GuardResult(False, None, "табличні функції заборонені")
        if t.args.get("db") or t.args.get("catalog"):
            return GuardResult(False, None, f"схеми/каталоги заборонені: {t.sql()}")
        if name not in ALLOWED_TABLES and name not in cte_names:
            return GuardResult(False, None, f"таблиця не дозволена: {name}")
    for f in tree.find_all(exp.Func):
        fname = (f.name or f.sql_name() or "").lower()
        if fname.startswith(FORBIDDEN_FUNC_PREFIXES):
            return GuardResult(False, None, f"функція не дозволена: {fname}")
    lim = tree.args.get("limit")
    try:
        cur = int(lim.expression.name) if lim is not None else None
    except (ValueError, AttributeError):
        cur = None
    if cur is None or cur > max_limit:
        tree = tree.limit(max_limit)
    return GuardResult(True, tree.sql(dialect="duckdb"), "")
