"""Виконання у режимі read-only з тайм-аутом (interrupt) і вимкненим зовнішнім доступом."""
from __future__ import annotations
import threading
import duckdb
import pandas as pd


class QueryTimeout(Exception):
    pass


def execute_readonly(sql: str, db_path, timeout_s: float = 5.0) -> pd.DataFrame:
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        for stmt in ("SET enable_external_access=false", "SET threads=2", "SET memory_limit='512MB'"):
            try:
                con.execute(stmt)
            except Exception:
                pass
        timer = threading.Timer(timeout_s, con.interrupt)
        timer.start()
        try:
            return con.execute(sql).fetchdf()
        except duckdb.InterruptException as e:
            raise QueryTimeout(f"перевищено тайм-аут {timeout_s} с") from e
        finally:
            timer.cancel()
    finally:
        con.close()
