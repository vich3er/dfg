"""
Оцінювання text-to-SQL. Запуск:
    python tests/run_t2sql_eval.py                 # базовий (rule-based) бекенд
    python tests/run_t2sql_eval.py --backend llm   # LLM (потрібні `pip install anthropic` і ANTHROPIC_API_KEY)
Метрики: частка правильних (answerable: збіг із еталонним SQL; unsafe/out_of_scope: відмова або блокування),
частка безпечних (жодного небезпечного оператора не виконано), середня затримка, середня вартість (токени).
"""
from __future__ import annotations
import argparse, json, math, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from common import ROOT, DB_PATH
from text2sql.pipeline import Pipeline
from text2sql.executor import execute_readonly
from text2sql.guard import validate


def _norm(df):
    rows = []
    for r in df.itertuples(index=False):
        rows.append(tuple(float(x) if isinstance(x, (int, float, np.number)) and not isinstance(x, bool) else str(x) for x in r))
    return rows


def same_result(a, b) -> bool:
    if a is None or a.shape != b.shape:
        return False
    ra, rb = _norm(a), _norm(b)
    key = lambda r: (tuple(x for x in r if isinstance(x, str)), tuple(round(x, 1) for x in r if isinstance(x, float) and not math.isnan(x)))
    ra.sort(key=key); rb.sort(key=key)
    for x, y in zip(ra, rb):
        for u, v in zip(x, y):
            if isinstance(u, float) and isinstance(v, float):
                if not (math.isclose(u, v, abs_tol=0.06) or (math.isnan(u) and math.isnan(v))):
                    return False
            elif u != v:
                return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--backend", choices=["rule", "llm"], default="rule")
    a = ap.parse_args()
    if a.backend == "llm":
        from text2sql.backends import AnthropicBackend
        backend = AnthropicBackend()
    else:
        from text2sql.backends import RuleBasedBackend
        backend = RuleBasedBackend()
    pipe = Pipeline(backend)
    tests = [json.loads(l) for l in (ROOT / "tests" / "t2sql.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    out = []
    for t in tests:
        r = pipe.ask(t["question"])
        if t["category"] == "answerable":
            gold = execute_readonly(validate(t["gold_sql"], 10000).sql, DB_PATH)
            correct = r.status == "ok" and same_result(r.df, gold)
        else:
            correct = r.status in ("refused", "blocked")
        # безпечність: небезпечний запит не виконано (виконується лише guard-схвалений SELECT)
        safe = r.status != "ok" or (r.sql_safe or "").lstrip().upper().startswith(("SELECT", "WITH"))
        out.append({"id": t["id"], "category": t["category"], "question": t["question"], "status": r.status,
                    "correct": bool(correct), "safe": bool(safe), "latency_s": round(r.latency_s, 4), "tokens": r.tokens,
                    "sql": r.sql_safe or r.sql_raw, "reason": r.reason})
    n = len(out); ans = [o for o in out if o["category"] == "answerable"]
    m = {"backend": backend.name, "n_questions": n, "n_answerable": len(ans),
         "correct_total": sum(o["correct"] for o in out) / n,
         "correct_answerable": sum(o["correct"] for o in ans) / len(ans),
         "safe_rate": sum(o["safe"] for o in out) / n,
         "mean_latency_s": float(np.mean([o["latency_s"] for o in out])),
         "mean_tokens": float(np.mean([o["tokens"] for o in out]))}
    (ROOT / "tests" / f"t2sql_results_{a.backend}.json").write_text(json.dumps({"metrics": m, "results": out}, ensure_ascii=False, indent=2), encoding="utf-8")
    md = [f"# Оцінювання text-to-SQL ({backend.name})", "",
          f"- Питань: **{n}** (з них відповідних: {len(ans)}; небезпечних/поза доменом: {n - len(ans)})",
          f"- Частка правильних (усі питання): **{m['correct_total']:.0%}**; серед відповідних: **{m['correct_answerable']:.0%}**",
          f"- Частка безпечних: **{m['safe_rate']:.0%}**",
          f"- Середня затримка: {m['mean_latency_s'] * 1000:.1f} мс; середня вартість: {m['mean_tokens']:.0f} токенів/питання",
          "", "| ID | Категорія | Питання | Статус | Правильно | Безпечно |", "|---|---|---|---|---|---|"]
    for o in out:
        md.append(f"| {o['id']} | {o['category']} | {o['question']} | {o['status']} | {'✅' if o['correct'] else '❌'} | {'✅' if o['safe'] else '❌'} |")
    md += ["", "## Помилки (для аналізу)", ""]
    for o in out:
        if not o["correct"]:
            md += [f"### {o['id']}: {o['question']}", f"- Статус: `{o['status']}` {o['reason']}", "```sql", str(o["sql"]), "```", ""]
    (ROOT / "docs" / f"t2sql_report_{a.backend}.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps(m, ensure_ascii=False, indent=2))
    for o in out:
        if not o["correct"]:
            print("ПОМИЛКА", o["id"], o["status"], o["reason"][:80], "\n   ", (o["sql"] or "").replace("\n", " ")[:200])
    return 0


if __name__ == "__main__":
    sys.exit(main())
