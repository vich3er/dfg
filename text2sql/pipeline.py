"""Конвеєр: питання -> бекенд -> AST-guard (SELECT, whitelist, LIMIT) -> read-only виконання з тайм-аутом."""
from __future__ import annotations
import time
from dataclasses import dataclass, field
import pandas as pd

from common import DB_PATH
from text2sql.guard import validate
from text2sql.executor import execute_readonly, QueryTimeout


@dataclass
class Result:
    question: str
    status: str                     # ok | refused | blocked | timeout | error
    sql_raw: str | None = None
    sql_safe: str | None = None
    reason: str = ""
    df: pd.DataFrame | None = None
    latency_s: float = 0.0
    tokens: int = 0
    meta: dict = field(default_factory=dict)


class Pipeline:
    def __init__(self, backend, db_path=DB_PATH, timeout_s: float = 5.0, max_rows: int = 1000):
        self.backend, self.db_path, self.timeout_s, self.max_rows = backend, db_path, timeout_s, max_rows

    def ask(self, question: str) -> Result:
        t0 = time.time()
        gen = self.backend.generate(question)
        r = Result(question, "refused", gen.sql, None, gen.note, tokens=gen.tokens)
        if gen.sql is None:
            r.latency_s = time.time() - t0
            return r
        g = validate(gen.sql, self.max_rows)
        if not g.ok:
            r.status, r.reason = "blocked", g.reason
        else:
            r.sql_safe = g.sql
            try:
                r.df, r.status = execute_readonly(g.sql, self.db_path, self.timeout_s), "ok"
            except QueryTimeout as e:
                r.status, r.reason = "timeout", str(e)
            except Exception as e:  # помилка SQL (невідома колонка тощо)
                r.status, r.reason = "error", str(e)[:200]
        r.latency_s = time.time() - t0
        return r
