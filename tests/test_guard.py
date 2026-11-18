"""Тести AST-захисту. Запуск: python tests/test_guard.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import DB_PATH
from text2sql.guard import validate
from text2sql.executor import execute_readonly, QueryTimeout

CASES = [  # (sql, очікується ok)
    ("SELECT COUNT(*) FROM fact_feedback_mention", True),
    ("WITH x AS (SELECT * FROM dim_topic) SELECT COUNT(*) FROM x", True),
    ("SELECT t.class_label, COUNT(*) FROM fact_feedback_mention f JOIN dim_topic t USING (topic_key) GROUP BY 1", True),
    ("SELECT * FROM fact_feedback_mention LIMIT 100000000", True),   # LIMIT буде знижено до 1000
    ("DROP TABLE fact_feedback_mention", False),
    ("DELETE FROM fact_feedback_mention", False),
    ("UPDATE dim_topic SET topic_label = 'x'", False),
    ("INSERT INTO dim_channel VALUES (99, 'x', 'y')", False),
    ("CREATE TABLE x AS SELECT 1", False),
    ("SELECT 1; DROP TABLE dim_date", False),
    ("SELECT * FROM read_csv('/etc/passwd')", False),
    ("SELECT * FROM read_parquet('data/*.parquet')", False),
    ("SELECT getenv('HOME')", False),
    ("SELECT * FROM information_schema.tables", False),
    ("SELECT * FROM duckdb_tables()", False),
    ("COPY fact_feedback_mention TO 'out.csv'", False),
    ("ATTACH 'other.db'", False),
    ("PRAGMA database_list", False),
    ("SELECT * FROM dim_date INTO OUTFILE 'x'", False),
    ("SELEC broken sql ((", False),
]


def main() -> int:
    fails = 0
    print(f"{'OK?':5s} {'очікув.':8s} SQL")
    for sql, expect in CASES:
        r = validate(sql)
        good = r.ok == expect
        fails += not good
        print(f"{'✅' if good else '❌'}    {str(expect):8s} {sql[:70]!r}  {'' if r.ok else '-> ' + r.reason}")
    r = validate("SELECT * FROM fact_feedback_mention LIMIT 100000000")
    assert r.ok and "LIMIT 1000" in r.sql, r.sql
    print("✅ LIMIT примусово знижено до 1000")
    # тайм-аут: важкий декартів добуток
    heavy = "SELECT COUNT(*) FROM fact_feedback_mention a, fact_feedback_mention b, fact_feedback_mention c, fact_feedback_mention d"
    try:
        execute_readonly(validate(heavy).sql, DB_PATH, timeout_s=1.0)
        print("❌ тайм-аут не спрацював"); fails += 1
    except QueryTimeout:
        print("✅ тайм-аут 1 с спрацював")
    # read-only на рівні СУБД
    import duckdb
    try:
        con = duckdb.connect(str(DB_PATH), read_only=True); con.execute("DELETE FROM dim_channel"); print("❌ запис пройшов!"); fails += 1
    except Exception:
        print("✅ СУБД відхиляє запис (read_only=True)")
    print("Підсумок:", "усі тести пройдено" if not fails else f"помилок: {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
