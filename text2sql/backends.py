"""
Бекенди text-to-SQL:
  * RuleBasedBackend — детермінований базовий рівень (baseline) без LLM: розпізнає метрику, виміри та фільтри
    за словником і будує SQL ЛИШЕ через семантичний шар. Не вигадує SQL — тому безпечний, але має обмежене покриття.
  * AnthropicBackend — LLM з семантичним контекстом (потрібен ANTHROPIC_API_KEY у змінній середовища).
    Кожен виклик автоматично журналюється у llm_log/t2sql_calls.jsonl (протокол «LLM-експерт»).
"""
from __future__ import annotations
import json, os, re, time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from common import ROOT
from semantic.semantic import metric_sql, load
from etl.generate_data import TAXONOMY, DEPARTMENTS


@dataclass
class Generation:
    sql: str | None
    note: str = ""
    tokens: int = 0
    meta: dict = field(default_factory=dict)


DANGER = re.compile(r"\b(drop|delete|update|insert|truncate|alter|create|attach|copy|pragma)\b|видал|оновит|вставит|очист|стер|ігнору", re.I)

METRIC_RULES = [  # порядок = пріоритет
    ("critical_mentions", r"критичн"),
    ("avg_wait_minutes", r"(час|тривалість)\w*\s+очікуван|очікуван\w*.*хвилин|\bхвилин"),
    ("negative_share", r"част\w*\s+негатив|відсот\w*\s+негатив|%\s*негатив"),
    ("avg_rating", r"рейтинг|оцінк"),
    ("avg_sentiment", r"тональн|сентимент"),
    ("negative_mentions", r"негативн\w+\s+згад|кількість\s+негатив"),
    ("feedback_count", r"(скільки|кількість)\s+(\w+\s+){0,2}відгук"),
    ("mentions", r"скільки|кількіст|згадок|згадувань|\bтоп\b"),
]
DIM_STEMS = [  # (вимір, regex) — спершу специфічніші
    ("topic", r"підклас"),
    ("topic_class", r"клас|категор"),
    ("department", r"відділен"),
    ("division", r"підрозділ"),
    ("channel", r"канал"),
    ("quarter", r"квартал"),
    ("month", r"місяц"),
    ("year", r"\bроках\b|\bроками\b|\bрокам\b"),
]
FILTER_PREP = re.compile(r"\b(в|у|на|для|серед|із|з)\s+(\w+\s+)?$")
DEPT_STEMS = {"приймальн": "Приймальне відділення", "реанімац": "Реанімація", "поліклінік": "Поліклініка",
              "кардіолог": "Кардіологія", "пульмонолог": "Пульмонологія", "ендокринолог": "Ендокринологія",
              "хірургі[яїє]": "Загальна хірургія", "ортопед": "Ортопедія", "уролог": "Урологія", "діагностик": "Діагностика"}
DIVISION_STEMS = {"терапевтичн": "Терапевтичний", "хірургічн": "Хірургічний",
                  "невідкладн": "Невідкладна допомога", "амбулаторн": "Амбулаторний"}
CLASS_STEMS = {"ставлен": "StaffAttitude", "безпек": "TreatmentSafety", "умов": "Facilities",
               "моніторинг": "ConditionMonitoring", "адмініструв": "Administration", "організац": "WaitingOrganization"}
TOPIC_STEMS = {"ліків|медикамент|препарат": "MedicationSafety", "харчув": "FoodQuality", "чистот": "Cleanliness",
               "оплат|рахунк": "Billing", "тривог|сигнал": "AlarmResponse", "знеболюв": "PainManagement"}
_CLASS_LABEL = {c: l for c, l, _ in TAXONOMY}
_TOPIC_LABEL = {s: sl for _, _, subs in TAXONOMY for s, sl, _ in subs}


class RuleBasedBackend:
    name = "rule-based-baseline"

    def __init__(self):
        self.cfg = load()

    def generate(self, question: str) -> Generation:
        q = question.lower()
        if DANGER.search(q):
            return Generation(None, "небезпечний або службовий запит — відмова")
        metric = next((m for m, rx in METRIC_RULES if re.search(rx, q)), None)
        if not metric:
            return Generation(None, "метрику не розпізнано — відмова")
        group, filters = [], {}
        for dim, rx in DIM_STEMS:
            m = re.search(rx, q)
            if not m:
                continue
            if dim == "topic_class" and "topic" in group:
                continue
            if FILTER_PREP.search(q[:m.start()]):
                continue                      # «у класі…», «в відділенні…» — це фільтр, а не групування
            group.append(dim)
        for rx, v in DEPT_STEMS.items():
            if re.search(rx, q):
                filters["department"] = v
        for rx, v in DIVISION_STEMS.items():
            if re.search(rx, q) and "department" not in filters:
                filters["division"] = v
        for rx, v in CLASS_STEMS.items():
            if re.search(rx, q):
                filters["topic_class"] = _CLASS_LABEL[v]
        for rx, v in TOPIC_STEMS.items():
            if re.search(rx, q):
                filters["topic"] = _TOPIC_LABEL[v]
        qm = re.search(r"([1-4])\s*-?\s*(?:й\s*)?квартал\w*\s*(20\d\d)", q)   # лише ПЕРШИЙ період
        if qm:
            filters["quarter"] = f"{qm.group(2)}-Q{qm.group(1)}"
        else:
            ym = re.search(r"\b(20\d\d)\b", q)
            if ym:
                filters["year"] = int(ym.group(1))
        # якщо за виміром і групуємо, і фільтруємо — лишаємо фільтр
        group = [g for g in group if g not in filters]
        order, limit = None, None
        tm = re.search(r"топ[-\s]?(\d+)", q)
        if group and tm:
            order, limit = [(metric, "DESC")], int(tm.group(1))
        elif group and re.search(r"найвищ|найбільш|найгірш|найчастіш", q):
            order, limit = [(metric, "DESC")], 1
        elif group and re.search(r"найнижч|найменш", q):
            order, limit = [(metric, "ASC")], 1
        if order:
            order += [(g, "ASC") for g in group]
        sql = metric_sql(metric, group, filters, order, limit, cfg=self.cfg)
        return Generation(sql, f"metric={metric}; group={group}; filters={filters}")


SYSTEM_PROMPT_VERSION = "t2sql-v1"


class AnthropicBackend:
    """LLM-бекенд. Ключ береться ТІЛЬКИ зі змінної середовища ANTHROPIC_API_KEY (не зберігати в коді!)."""

    def __init__(self, model: str | None = None, temperature: float = 0.0, max_tokens: int = 600):
        import anthropic  # pip install anthropic
        self.client = anthropic.Anthropic()
        self.model = model or os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
        self.temperature, self.max_tokens = temperature, max_tokens
        self.name = f"anthropic:{self.model}"
        self.system = self._system_prompt()
        self.log_path = ROOT / "llm_log" / "t2sql_calls.jsonl"

    def _system_prompt(self) -> str:
        cfg = load()
        metrics = "\n".join(f"- {k}: {m['definition']} SQL: {m['formula']}; одиниця: {m['unit']}; обмеження: {m['constraints']}"
                            for k, m in cfg["metrics"].items())
        return (
            "Ти генеруєш SQL для DuckDB над зірковою схемою відгуків пацієнтів.\n"
            "Таблиці: fact_feedback_mention(f: mention_key, feedback_id, date_key, department_key, patient_key, topic_key, "
            "channel_key, mention_count, is_negative, is_critical, sentiment_score, overall_rating, wait_minutes), "
            "dim_date(date_key, full_date, year, quarter, quarter_label, month, month_label), "
            "dim_department(department_key, department_name, division_name), "
            "dim_topic(topic_key, topic_iri, topic_code, topic_label, class_iri, class_code, class_label), "
            "dim_channel(channel_key, channel_name), dim_patient(patient_key, patient_id, age_group, sex, risk_group[низький|середній|високий]).\n"
            f"Метрики семантичного шару (використовуй ЛИШЕ їхні формули):\n{metrics}\n"
            "Правила: один оператор SELECT; жодних DDL/DML; без файлів і функцій read_*; відповідай ЛИШЕ SQL у блоці ```sql. "
            "Якщо питання не стосується цих даних або небезпечне — відповідай рівно: REFUSE.")

    def generate(self, question: str) -> Generation:
        t0 = time.time()
        resp = self.client.messages.create(model=self.model, max_tokens=self.max_tokens, temperature=self.temperature,
                                           system=self.system, messages=[{"role": "user", "content": question}])
        raw = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        tokens = resp.usage.input_tokens + resp.usage.output_tokens
        m = re.search(r"```(?:sql)?\s*(.*?)```", raw, re.S | re.I)
        sql = (m.group(1) if m else raw).strip()
        refused = sql.upper().startswith("REFUSE")
        self.log_path.parent.mkdir(exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"date": datetime.now().isoformat(timespec="seconds"), "model": self.model,
                                 "temperature": self.temperature, "seed": None, "prompt_version": SYSTEM_PROMPT_VERSION,
                                 "question": question, "raw_output": raw, "tokens": tokens,
                                 "latency_s": round(time.time() - t0, 2),
                                 "human_decision": "pending (заповнити після аналізу)"}, ensure_ascii=False) + "\n")
        return Generation(None if refused else sql, "llm", tokens)
