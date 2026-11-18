"""
Генератор СИНТЕТИЧНИХ даних «відгуки пацієнтів» (документований, відтворюваний).

Усі дані вигадані: реальні пацієнти та їхні відгуки не використовуються.
Параметри: seed (за замовчуванням 42) і n_feedback (за замовчуванням 1500).

Модель генерації:
  * період 2025-01-01 .. 2026-09-30; відділення мають різні обсяги відгуків і «профілі» тем;
  * кожен відгук містить 1–4 теми; частина тем корельована (напр. Billing <-> InsuranceSupport),
    що дає осмислену семантичну мережу співпоявлень;
  * тональність = база підкласу + зсув відділення + настрій відгуку + шум;
  * ЗАКЛАДЕНИЙ ТРЕНД: з 2026-03-01 тональність і час очікування в «EmergencyWait» та
    «AppointmentScheduling» погіршуються (щоб OLAP-аналіз мав що знаходити);
  * група ризику пацієнта змінюється у ~20 % пацієнтів (SCD тип 2).
"""
from __future__ import annotations

from datetime import date
import numpy as np
import pandas as pd

GENERATOR_VERSION = "1.0.0"
BASE_IRI = "https://hub.lnu.edu.ua/onto/patient-feedback#"
START, END = date(2025, 1, 1), date(2026, 9, 30)
CHANGE_POINT = date(2026, 3, 1)

# (код класу, назва класу, [(код підкласу, назва підкласу, базова тональність)])
TAXONOMY = [
    ("StaffAttitude", "Ставлення персоналу", [
        ("DoctorCommunication", "Комунікація лікаря", 0.45),
        ("NurseCare", "Догляд медсестер", 0.50),
        ("Respect", "Повага й етика", 0.40)]),
    ("TreatmentSafety", "Лікування і безпека", [
        ("TreatmentEffectiveness", "Ефективність лікування", 0.35),
        ("PainManagement", "Контроль болю", 0.00),
        ("MedicationSafety", "Безпека ліків", 0.10),
        ("PatientInformation", "Інформування пацієнта", 0.10)]),
    ("WaitingOrganization", "Очікування й організація", [
        ("EmergencyWait", "Очікування в невідкладній допомозі", -0.35),
        ("AppointmentScheduling", "Запис на прийом", -0.10),
        ("DischargeProcess", "Процес виписки", -0.05)]),
    ("Facilities", "Умови перебування", [
        ("Cleanliness", "Чистота", 0.30),
        ("FoodQuality", "Харчування", -0.20),
        ("EquipmentCondition", "Стан обладнання", 0.15),
        ("RoomComfort", "Комфорт палати", 0.05)]),
    ("ConditionMonitoring", "Моніторинг стану", [
        ("VitalsMonitoring", "Вимірювання показників", 0.25),
        ("AlarmResponse", "Реагування на сигнали тривоги", 0.00),
        ("FollowUpCare", "Супровід після виписки", 0.00)]),
    ("Administration", "Адміністрування та вартість", [
        ("Billing", "Рахунки та оплата", -0.25),
        ("Documentation", "Документи й довідки", -0.10),
        ("InsuranceSupport", "Страхування", -0.15)]),
]

DEPARTMENTS = [  # (підрозділ, відділення, відносний обсяг, зсув тональності)
    ("Терапевтичний", "Кардіологія", 1.0, 0.10),
    ("Терапевтичний", "Пульмонологія", 0.7, 0.05),
    ("Терапевтичний", "Ендокринологія", 0.6, 0.08),
    ("Хірургічний", "Загальна хірургія", 1.0, 0.00),
    ("Хірургічний", "Ортопедія", 0.8, 0.05),
    ("Хірургічний", "Урологія", 0.6, 0.00),
    ("Невідкладна допомога", "Приймальне відділення", 1.6, -0.12),
    ("Невідкладна допомога", "Реанімація", 0.6, 0.05),
    ("Амбулаторний", "Поліклініка", 1.5, -0.08),
    ("Амбулаторний", "Діагностика", 0.7, 0.02),
]
DEPT_PROFILE = {  # множники ваг КЛАСІВ у відділенні
    "Приймальне відділення": {"WaitingOrganization": 3.0, "StaffAttitude": 1.5, "Facilities": 0.5, "ConditionMonitoring": 0.5},
    "Реанімація": {"ConditionMonitoring": 3.0, "TreatmentSafety": 1.5, "Facilities": 0.5, "Administration": 0.3, "WaitingOrganization": 0.3},
    "Поліклініка": {"WaitingOrganization": 2.5, "Administration": 1.5, "Facilities": 0.5, "ConditionMonitoring": 0.3},
    "Діагностика": {"WaitingOrganization": 1.8, "EquipmentCondition": 1.0, "ConditionMonitoring": 0.3},
    "Кардіологія": {"ConditionMonitoring": 1.8, "TreatmentSafety": 1.3},
    "Загальна хірургія": {"TreatmentSafety": 1.4, "ConditionMonitoring": 1.3},
    "Ортопедія": {"TreatmentSafety": 1.3, "Facilities": 1.2},
}
CHANNELS = [("Анкета при виписці", "активний"), ("SMS-опитування", "активний"),
            ("Портал пацієнта", "пасивний"), ("Кіоск у відділенні", "пасивний"),
            ("Гаряча лінія", "пасивний")]
CHANNEL_P = [0.30, 0.25, 0.20, 0.15, 0.10]
PARTNER_PAIRS = [("EmergencyWait", "PatientInformation"), ("AlarmResponse", "VitalsMonitoring"),
                 ("Billing", "InsuranceSupport"), ("DoctorCommunication", "PatientInformation"),
                 ("NurseCare", "PainManagement"), ("DischargeProcess", "Documentation"),
                 ("FoodQuality", "RoomComfort"), ("FollowUpCare", "DischargeProcess")]
WAIT_BASE = {"EmergencyWait": 90, "AppointmentScheduling": 35, "DischargeProcess": 60}
CRITICAL_TOPICS = {"MedicationSafety", "AlarmResponse", "VitalsMonitoring"}

PHRASES = {
    "DoctorCommunication": ("Лікар поспіхом пояснив діагноз і не відповів на мої запитання.", "Лікар уважно вислухав і зрозуміло пояснив план лікування."),
    "NurseCare": ("Медсестри довго не реагували на прохання про допомогу.", "Медсестри були уважними та турботливими."),
    "Respect": ("Було відчуття неповаги до мене з боку персоналу.", "Ставлення персоналу було ввічливим і шанобливим."),
    "TreatmentEffectiveness": ("Лікування не дало очікуваного покращення стану.", "Лікування допомогло, стан помітно покращився."),
    "PainManagement": ("Біль довго не вдавалося зняти.", "Біль швидко вгамували, дякую."),
    "MedicationSafety": ("Мені двічі переплутали дозування ліків.", "Усі ліки видавали точно за призначенням."),
    "PatientInformation": ("Мені майже нічого не пояснили про подальші дії.", "Отримав чітку інформацію про лікування та подальші кроки."),
    "EmergencyWait": ("У приймальному довелося чекати надто довго.", "У приймальному допомогу надали швидко."),
    "AppointmentScheduling": ("Записатися на прийом було складно, черги величезні.", "Запис на прийом був зручним і без черг."),
    "DischargeProcess": ("Виписку оформлювали кілька годин.", "Виписку оформили швидко й без зайвих клопотів."),
    "Cleanliness": ("У палаті було брудно.", "У палаті та коридорах було чисто."),
    "FoodQuality": ("Харчування було несмачним і одноманітним.", "Харчування було смачним і різноманітним."),
    "EquipmentCondition": ("Обладнання застаріле та часто не працювало.", "Обладнання сучасне та справне."),
    "RoomComfort": ("У палаті було незручно: холодно і шумно.", "У палаті було комфортно та тихо."),
    "VitalsMonitoring": ("Показники стану вимірювали рідко, я почувався без нагляду.", "Показники стану вимірювали вчасно, відчувався постійний нагляд."),
    "AlarmResponse": ("На сигнал тривоги від апарату ніхто довго не приходив.", "На сигнали моніторів персонал реагував миттєво."),
    "FollowUpCare": ("Після виписки ніхто не поцікавився моїм станом.", "Після виписки зателефонували й поцікавилися станом."),
    "Billing": ("Рахунок був незрозумілим і містив зайві позиції.", "Рахунок був прозорим і зрозумілим."),
    "Documentation": ("Оформлення довідок і виписок затягнулося.", "Документи видали швидко та без помилок."),
    "InsuranceSupport": ("З оформленням страхування ніхто не допоміг.", "З оформленням страхування допомогли швидко."),
}


def generate(seed: int = 42, n_feedback: int = 1500, n_patients: int = 700) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)

    # ---- dim_date
    days = pd.date_range(START, END, freq="D")
    dd = pd.DataFrame({"full_date": days})
    dd["date_key"] = dd.full_date.dt.strftime("%Y%m%d").astype(int)
    dd["year"] = dd.full_date.dt.year
    dd["quarter"] = dd.full_date.dt.quarter
    dd["quarter_label"] = dd.year.astype(str) + "-Q" + dd.quarter.astype(str)
    dd["month"] = dd.full_date.dt.month
    dd["month_label"] = dd.full_date.dt.strftime("%Y-%m")
    dd["week"] = dd.full_date.dt.isocalendar().week.astype(int)
    dd["day_of_week"] = dd.full_date.dt.dayofweek + 1
    dd["is_weekend"] = dd.day_of_week >= 6
    dd["full_date"] = dd.full_date.dt.date
    dim_date = dd[["date_key", "full_date", "year", "quarter", "quarter_label", "month",
                   "month_label", "week", "day_of_week", "is_weekend"]]

    # ---- dim_department
    dim_department = pd.DataFrame({
        "department_key": range(1, len(DEPARTMENTS) + 1),
        "department_name": [d[1] for d in DEPARTMENTS],
        "division_name": [d[0] for d in DEPARTMENTS]})

    # ---- dim_topic (таксономія з IRI)
    rows, leaf_ids, leaf_class, base_sent = [], [], {}, {}
    k = 0
    for c_code, c_label, subs in TAXONOMY:
        for s_code, s_label, s_base in subs:
            k += 1
            rows.append((k, BASE_IRI + s_code, s_code, s_label, BASE_IRI + c_code, c_code, c_label, 2))
            leaf_ids.append(s_code); leaf_class[s_code] = c_code; base_sent[s_code] = s_base
    dim_topic = pd.DataFrame(rows, columns=["topic_key", "topic_iri", "topic_code", "topic_label",
                                            "class_iri", "class_code", "class_label", "level"])
    label = dict(zip(dim_topic.topic_code, dim_topic.topic_label))
    tkey = dict(zip(dim_topic.topic_code, dim_topic.topic_key))
    idx = {c: i for i, c in enumerate(leaf_ids)}

    dim_channel = pd.DataFrame({"channel_key": range(1, len(CHANNELS) + 1),
                                "channel_name": [c[0] for c in CHANNELS],
                                "channel_type": [c[1] for c in CHANNELS]})

    # ---- dim_patient (SCD2)
    risk_order = ["низький", "середній", "високий"]
    pat_rows, versions = [], {}
    pk = 0
    ages = ["18–34", "35–49", "50–64", "65+"]
    for i in range(n_patients):
        pid = f"P{i + 1:04d}"
        age = rng.choice(ages, p=[0.2, 0.25, 0.3, 0.25]); sex = rng.choice(["Ж", "Ч"])
        r0 = int(rng.choice(3, p=[0.5, 0.3, 0.2]))
        changed = rng.random() < 0.20 and r0 < 2
        versions[pid] = []
        if changed:
            cd = pd.Timestamp(rng.choice(pd.date_range("2025-03-01", "2026-06-30"))).date()
            pk += 1
            pat_rows.append((pk, pid, age, sex, risk_order[r0], START, cd - pd.Timedelta(days=1), False))
            versions[pid].append((pk, START, cd - pd.Timedelta(days=1)))
            pk += 1
            pat_rows.append((pk, pid, age, sex, risk_order[r0 + 1], cd, date(9999, 12, 31), True))
            versions[pid].append((pk, cd, date(9999, 12, 31)))
        else:
            pk += 1
            pat_rows.append((pk, pid, age, sex, risk_order[r0], START, date(9999, 12, 31), True))
            versions[pid].append((pk, START, date(9999, 12, 31)))
    dim_patient = pd.DataFrame(pat_rows, columns=["patient_key", "patient_id", "age_group", "sex",
                                                  "risk_group", "valid_from", "valid_to", "is_current"])
    pids = list(versions.keys())

    # ---- ваги тем по відділеннях
    topic_w = {}
    for _, dep, vol, off in DEPARTMENTS:
        w = np.ones(len(leaf_ids))
        for c, mult in DEPT_PROFILE.get(dep, {}).items():
            for s in leaf_ids:
                if leaf_class[s] == c or s == c:
                    w[idx[s]] *= mult
        topic_w[dep] = w / w.sum()
    partner = {}
    for a, b in PARTNER_PAIRS:
        partner.setdefault(a, []).append(b); partner.setdefault(b, []).append(a)
    dep_vol = np.array([d[2] for d in DEPARTMENTS]); dep_vol = dep_vol / dep_vol.sum()

    fact_rows, fb_rows = [], []
    mk = 0
    for i in range(n_feedback):
        fid = f"FB-{i + 1:06d}"
        di = int(rng.choice(len(DEPARTMENTS), p=dep_vol))
        dep_name, dep_off = DEPARTMENTS[di][1], DEPARTMENTS[di][3]
        day = days[int(rng.integers(0, len(days)))].date()
        pid = pids[int(rng.integers(0, len(pids)))]
        pkey = next(v[0] for v in versions[pid] if v[1] <= day <= v[2])
        ch = int(rng.choice(len(CHANNELS), p=CHANNEL_P)) + 1
        w = topic_w[dep_name]
        n_topics = int(rng.choice([1, 2, 3, 4], p=[0.35, 0.35, 0.20, 0.10]))
        chosen = [int(rng.choice(len(leaf_ids), p=w))]
        while len(chosen) < n_topics:
            cand = None
            if rng.random() < 0.5:
                for c in chosen:
                    for p_ in partner.get(leaf_ids[c], []):
                        if idx[p_] not in chosen:
                            cand = idx[p_]; break
                    if cand is not None:
                        break
            if cand is None:
                ww = w.copy(); ww[chosen] = 0; ww = ww / ww.sum()
                cand = int(rng.choice(len(leaf_ids), p=ww))
            chosen.append(cand)
        mood = rng.normal(0, 0.25)
        sents, recs = [], []
        for t in chosen:
            lid = leaf_ids[t]
            s = base_sent[lid] + dep_off + mood + rng.normal(0, 0.3)
            late = day >= CHANGE_POINT and lid in ("EmergencyWait", "AppointmentScheduling")
            if late:
                s -= 0.25
            s = float(np.clip(s, -1, 1).round(3))
            neg = int(s < -0.2)
            crit = int(neg and lid in CRITICAL_TOPICS and s < -0.5)
            wait = None
            if lid in WAIT_BASE:
                wait = WAIT_BASE[lid] * float(np.exp(rng.normal(0, 0.45))) * (1 + max(0.0, -s) * 0.3)
                if late:
                    wait *= 1.4
                wait = int(round(wait))
            sents.append(s)
            recs.append((lid, s, neg, crit, wait))
        rating = int(np.clip(round(3 + 2 * float(np.mean(sents)) + rng.normal(0, 0.5)), 1, 5))
        parts = []
        for lid, s, *_ in recs:
            neg_p, pos_p = PHRASES[lid]
            parts.append(neg_p if s <= -0.15 else pos_p if s >= 0.15 else f"Загалом без зауважень щодо теми «{label[lid]}».")
        fb_rows.append((fid, " ".join(parts), "uk"))
        for lid, s, neg, crit, wait in recs:
            mk += 1
            fact_rows.append((mk, fid, int(day.strftime("%Y%m%d")), di + 1, pkey, tkey[lid], ch,
                              1, neg, crit, s, rating, wait))

    fact = pd.DataFrame(fact_rows, columns=[
        "mention_key", "feedback_id", "date_key", "department_key", "patient_key", "topic_key",
        "channel_key", "mention_count", "is_negative", "is_critical", "sentiment_score",
        "overall_rating", "wait_minutes"])
    fact["wait_minutes"] = fact["wait_minutes"].astype("Int64")
    dim_feedback = pd.DataFrame(fb_rows, columns=["feedback_id", "feedback_text", "language"])
    return {"dim_date": dim_date, "dim_department": dim_department, "dim_patient": dim_patient,
            "dim_topic": dim_topic, "dim_channel": dim_channel, "dim_feedback": dim_feedback,
            "fact_feedback_mention": fact}


if __name__ == "__main__":
    for name, df in generate().items():
        print(f"{name:24s} {len(df):6d} рядків")
