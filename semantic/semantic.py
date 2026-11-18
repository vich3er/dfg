"""
Семантичний шар: генерація SQL за назвою метрики.
Приклади:
    from semantic.semantic import metric_sql
    metric_sql("negative_share", group_by=["department"], filters={"year": 2026})
CLI:
    python semantic/semantic.py negative_share --by department --filter year=2026
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import yaml

YML = Path(__file__).with_name("metrics.yml")


def load(path: Path = YML) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _lit(v) -> str:
    if isinstance(v, bool):
        raise ValueError("bool не підтримується у фільтрах")
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def metric_sql(metrics, group_by=(), filters: dict | None = None, order_by=None,
               limit: int | None = None, cfg: dict | None = None) -> str:
    """order_by: список (ім'я_метрики_або_виміру, 'ASC'|'DESC'). За замовчуванням — за вимірами групування."""
    cfg = cfg or load()
    metrics = [metrics] if isinstance(metrics, str) else list(metrics)
    dims, mdefs, fa = cfg["dimensions"], cfg["metrics"], cfg["fact"]["alias"]
    joins: dict[str, str] = {}
    select, group = [], []

    def need(dname: str):
        if dname not in dims:
            raise ValueError(f"Невідомий вимір: {dname}. Доступні: {sorted(dims)}")
        d = dims[dname]
        joins.setdefault(d["alias"], f"JOIN {d['table']} {d['alias']} ON {d['join_on']}")
        return d

    for g in group_by:
        d = need(g)
        select.append(f'{d["column"]} AS "{g}"'); group.append(d["column"])
    for m in metrics:
        if m not in mdefs:
            raise ValueError(f"Невідома метрика: {m}. Доступні: {sorted(mdefs)}")
        spec = mdefs[m]; expr = spec["formula"]
        if spec.get("round") is not None:
            expr = f"ROUND({expr}, {spec['round']})"
        select.append(f"{expr} AS {m}")
    where = []
    for dname, val in (filters or {}).items():
        d = need(dname)
        if isinstance(val, (list, tuple, set)):
            where.append(f"{d['column']} IN ({', '.join(_lit(x) for x in val)})")
        else:
            where.append(f"{d['column']} = {_lit(val)}")
    sql = f"SELECT {', '.join(select)}\nFROM {cfg['fact']['table']} {fa}"
    if joins:
        sql += "\n" + "\n".join(joins.values())
    if where:
        sql += "\nWHERE " + " AND ".join(where)
    if group:
        sql += "\nGROUP BY " + ", ".join(group)
    if order_by is None and group_by:
        order_by = [(g, "ASC") for g in group_by]
    if order_by:
        parts = []
        for name, direction in order_by:
            if name not in metrics and name not in group_by:
                raise ValueError(f"ORDER BY за невідомим полем: {name}")
            if direction.upper() not in ("ASC", "DESC"):
                raise ValueError("Напрям сортування: ASC або DESC")
            parts.append(f'"{name}" {direction.upper()}')
        sql += "\nORDER BY " + ", ".join(parts)
    if limit:
        sql += f"\nLIMIT {int(limit)}"
    return sql


def describe(metric: str, cfg: dict | None = None) -> dict:
    return (cfg or load())["metrics"][metric]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Згенерувати SQL за метрикою")
    ap.add_argument("metric"); ap.add_argument("--by", nargs="*", default=[])
    ap.add_argument("--filter", nargs="*", default=[], help="dim=value")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    flt = {}
    for kv in a.filter:
        k, v = kv.split("=", 1); flt[k] = int(v) if v.isdigit() else v
    print(metric_sql(a.metric, a.by, flt, limit=a.limit))
