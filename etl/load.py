"""
ELT: генерація -> завантаження у DuckDB (за sql/ddl.sql) -> перевірка ключів/якості -> Parquet + VERSION.json.
Запуск:  python etl/load.py [--seed 42] [--n-feedback 1500]
"""
from __future__ import annotations
import argparse, hashlib, json, platform, sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import duckdb, pandas as pd
from common import ROOT, DB_PATH, DATA_DIR
from etl.generate_data import generate, GENERATOR_VERSION
from etl.quality_checks import run_checks, save_report
from etl.semantic_network import build_topic_relations, write_turtle

DATA_VERSION = "1.0.0"
TABLES = ["dim_date", "dim_department", "dim_patient", "dim_topic", "dim_channel",
          "dim_feedback", "fact_feedback_mention", "topic_relation"]


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main(seed: int, n_feedback: int) -> int:
    dfs = generate(seed=seed, n_feedback=n_feedback)
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = duckdb.connect(str(DB_PATH))
    con.execute((ROOT / "sql" / "ddl.sql").read_text(encoding="utf-8"))
    for name in ["dim_date", "dim_department", "dim_patient", "dim_topic", "dim_channel",
                 "dim_feedback", "fact_feedback_mention"]:
        df = dfs[name]
        con.register("df_in", df)
        cols = ", ".join(df.columns)
        con.execute(f"INSERT INTO {name} ({cols}) SELECT {cols} FROM df_in")
        con.unregister("df_in")
        print(f"  завантажено {name:24s} {len(df):6d} рядків")

    edges = build_topic_relations(con)
    con.register("df_in", edges)
    con.execute("INSERT INTO topic_relation SELECT subject_iri, predicate, object_iri, weight, support FROM df_in")
    con.unregister("df_in")
    write_turtle(con, edges, DATA_DIR / "feedback_semantic_network.ttl")
    print(f"  завантажено topic_relation          {len(edges):6d} рядків")

    orphans_sql = (ROOT / "sql" / "checks" / "orphans.sql").read_text(encoding="utf-8")
    results = run_checks(con, orphans_sql)
    save_report(results, DATA_DIR / "quality_report.json", ROOT / "docs" / "quality_report.md")
    ok = all(r["passed"] for r in results)
    print(f"  перевірки якості: {sum(r['passed'] for r in results)}/{len(results)}")

    files = {}
    for t in TABLES:
        out = DATA_DIR / f"{t}.parquet"
        con.execute(f"COPY (SELECT * FROM {t}) TO '{out.as_posix()}' (FORMAT PARQUET)")
        files[out.name] = {"rows": int(con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]), "sha256": sha256(out)}
    version = {"data_version": DATA_VERSION, "generator_version": GENERATOR_VERSION, "seed": seed,
               "n_feedback": n_feedback, "created_at": datetime.now().isoformat(timespec="seconds"),
               "duckdb": duckdb.__version__, "pandas": pd.__version__, "python": platform.python_version(),
               "synthetic": True, "files": files}
    (DATA_DIR / "VERSION.json").write_text(json.dumps(version, ensure_ascii=False, indent=2), encoding="utf-8")
    con.close()
    print("Готово." if ok else "УВАГА: є провалені перевірки якості!")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n-feedback", type=int, default=1500)
    a = ap.parse_args()
    sys.exit(main(a.seed, a.n_feedback))
