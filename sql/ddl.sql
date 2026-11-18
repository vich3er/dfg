-- ЛР12. Зіркова схема «Відгуки пацієнтів» (DuckDB)
-- Зерно факту: ОДНА ЗГАДКА ОДНІЄЇ ТЕМИ (підкласу таксономії) В ОДНОМУ ВІДГУКУ ПАЦІЄНТА.

DROP TABLE IF EXISTS topic_relation;
DROP TABLE IF EXISTS fact_feedback_mention;
DROP TABLE IF EXISTS dim_feedback;
DROP TABLE IF EXISTS dim_channel;
DROP TABLE IF EXISTS dim_topic;
DROP TABLE IF EXISTS dim_patient;
DROP TABLE IF EXISTS dim_department;
DROP TABLE IF EXISTS dim_date;

CREATE TABLE dim_date (
    date_key       INTEGER PRIMARY KEY,          -- YYYYMMDD
    full_date      DATE NOT NULL UNIQUE,
    year           SMALLINT NOT NULL,
    quarter        SMALLINT NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    quarter_label  VARCHAR NOT NULL,             -- 2026-Q3
    month          SMALLINT NOT NULL CHECK (month BETWEEN 1 AND 12),
    month_label    VARCHAR NOT NULL,             -- 2026-09
    week           SMALLINT NOT NULL,
    day_of_week    SMALLINT NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
    is_weekend     BOOLEAN NOT NULL
);

-- Ієрархія: division_name -> department_name. SCD тип 1 (перезапис)
CREATE TABLE dim_department (
    department_key  INTEGER PRIMARY KEY,
    department_name VARCHAR NOT NULL UNIQUE,
    division_name   VARCHAR NOT NULL
);

-- SCD тип 2: група ризику пацієнта змінюється в часі
CREATE TABLE dim_patient (
    patient_key  INTEGER PRIMARY KEY,            -- сурогатний ключ версії
    patient_id   VARCHAR NOT NULL,               -- псевдонім (бізнес-ключ), без ПІБ
    age_group    VARCHAR NOT NULL,
    sex          VARCHAR NOT NULL,
    risk_group   VARCHAR NOT NULL,               -- низький / середній / високий
    valid_from   DATE NOT NULL,
    valid_to     DATE NOT NULL,
    is_current   BOOLEAN NOT NULL
);

-- ВИМІР-ТАКСОНОМІЯ (з ЛР5): корінь Feedback -> клас -> підклас (листок)
CREATE TABLE dim_topic (
    topic_key    INTEGER PRIMARY KEY,
    topic_iri    VARCHAR NOT NULL UNIQUE,        -- IRI підкласу
    topic_code   VARCHAR NOT NULL UNIQUE,
    topic_label  VARCHAR NOT NULL,
    class_iri    VARCHAR NOT NULL,               -- IRI батьківського класу
    class_code   VARCHAR NOT NULL,
    class_label  VARCHAR NOT NULL,
    level        SMALLINT NOT NULL               -- глибина в таксономії (2 = підклас)
);

CREATE TABLE dim_channel (
    channel_key  INTEGER PRIMARY KEY,
    channel_name VARCHAR NOT NULL UNIQUE,
    channel_type VARCHAR NOT NULL                -- активний / пасивний
);

-- Вироджений вимір: текст відгуку (синтетичний)
CREATE TABLE dim_feedback (
    feedback_id   VARCHAR PRIMARY KEY,
    feedback_text VARCHAR NOT NULL,
    language      VARCHAR NOT NULL
);

CREATE TABLE fact_feedback_mention (
    mention_key     BIGINT PRIMARY KEY,
    feedback_id     VARCHAR NOT NULL REFERENCES dim_feedback(feedback_id),
    date_key        INTEGER NOT NULL REFERENCES dim_date(date_key),
    department_key  INTEGER NOT NULL REFERENCES dim_department(department_key),
    patient_key     INTEGER NOT NULL REFERENCES dim_patient(patient_key),
    topic_key       INTEGER NOT NULL REFERENCES dim_topic(topic_key),
    channel_key     INTEGER NOT NULL REFERENCES dim_channel(channel_key),
    -- ===== міри =====
    mention_count   SMALLINT NOT NULL DEFAULT 1 CHECK (mention_count = 1),   -- адитивна
    is_negative     SMALLINT NOT NULL CHECK (is_negative IN (0, 1)),         -- адитивна
    is_critical     SMALLINT NOT NULL CHECK (is_critical IN (0, 1)),         -- адитивна
    sentiment_score DOUBLE   NOT NULL CHECK (sentiment_score BETWEEN -1 AND 1), -- неадитивна
    overall_rating  SMALLINT NOT NULL CHECK (overall_rating BETWEEN 1 AND 5),   -- неадитивна
    wait_minutes    INTEGER CHECK (wait_minutes >= 0),                          -- неадитивна, NULL якщо не застосовно
    UNIQUE (feedback_id, topic_key)
);

-- Семантична мережа тем: rdfs:subClassOf (з таксономії) та fb:coOccursWith (з даних)
CREATE TABLE topic_relation (
    subject_iri VARCHAR NOT NULL,
    predicate   VARCHAR NOT NULL,
    object_iri  VARCHAR NOT NULL,
    weight      DOUBLE NOT NULL,                 -- lift для coOccursWith, 1.0 для subClassOf
    support     INTEGER NOT NULL,
    PRIMARY KEY (subject_iri, predicate, object_iri)
);
