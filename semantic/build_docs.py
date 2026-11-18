"""Генерує таблицю метрик для docs/semantic_layer.md з metrics.yml (щоб документація не розходилась з кодом)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ROOT
from semantic.semantic import load

cfg = load()
lines = ["| Метрика | Визначення | Формула | Одиниця | Адитивність | Власник | Джерела | Обмеження | Статус | Перегляд |",
         "|---|---|---|---|---|---|---|---|---|---|"]
for k, m in cfg["metrics"].items():
    lines.append(f"| `{k}` ({m['label']}) | {m['definition']} | `{m['formula']}` | {m['unit']} | {m['additivity']} | "
                 f"{m['owner']} | {', '.join(m['sources'])} | {m['constraints']} | {m['status']} | {m['reviewed_at']} |")
dl = ["| Вимір | Колонка | Опис |", "|---|---|---|"]
for k, d in cfg["dimensions"].items():
    dl.append(f"| `{k}` | `{d['column']}` | {d['description']} |")
tpl = (ROOT / "docs" / "semantic_layer.template.md").read_text(encoding="utf-8")
out = tpl.replace("{{METRICS}}", "\n".join(lines)).replace("{{DIMENSIONS}}", "\n".join(dl))
(ROOT / "docs" / "semantic_layer.md").write_text(out, encoding="utf-8")
print("docs/semantic_layer.md оновлено")
