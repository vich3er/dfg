"""Семантична мережа тем: rdfs:subClassOf (таксономія) + fb:coOccursWith (дані, lift)."""
from __future__ import annotations
import pandas as pd
from etl.generate_data import BASE_IRI

ROOT_IRI = BASE_IRI + "Feedback"
MIN_SUPPORT, MIN_LIFT = 15, 1.5


def build_topic_relations(con) -> pd.DataFrame:
    sub_leaf = con.execute("""
        SELECT t.topic_iri AS subject_iri, 'rdfs:subClassOf' AS predicate, t.class_iri AS object_iri,
               1.0 AS weight, COUNT(*)::INTEGER AS support
        FROM fact_feedback_mention f JOIN dim_topic t USING (topic_key)
        GROUP BY t.topic_iri, t.class_iri""").fetchdf()
    sub_class = con.execute(f"""
        SELECT t.class_iri AS subject_iri, 'rdfs:subClassOf' AS predicate, '{ROOT_IRI}' AS object_iri,
               1.0 AS weight, COUNT(*)::INTEGER AS support
        FROM fact_feedback_mention f JOIN dim_topic t USING (topic_key)
        GROUP BY t.class_iri""").fetchdf()
    co = con.execute(f"""
        WITH n AS (SELECT COUNT(DISTINCT feedback_id) AS N FROM fact_feedback_mention),
        tc AS (SELECT topic_key, COUNT(DISTINCT feedback_id) AS c FROM fact_feedback_mention GROUP BY 1),
        p AS (SELECT a.topic_key AS ta, b.topic_key AS tb, COUNT(*) AS s
              FROM fact_feedback_mention a JOIN fact_feedback_mention b
                ON a.feedback_id = b.feedback_id AND a.topic_key < b.topic_key GROUP BY 1, 2)
        SELECT da.topic_iri AS subject_iri, 'fb:coOccursWith' AS predicate, db.topic_iri AS object_iri,
               ROUND((p.s * 1.0 * n.N) / (ca.c * cb.c), 3) AS weight, p.s::INTEGER AS support
        FROM p CROSS JOIN n
        JOIN tc ca ON ca.topic_key = p.ta JOIN tc cb ON cb.topic_key = p.tb
        JOIN dim_topic da ON da.topic_key = p.ta JOIN dim_topic db ON db.topic_key = p.tb
        WHERE p.s >= {MIN_SUPPORT} AND (p.s * 1.0 * n.N) / (ca.c * cb.c) >= {MIN_LIFT}
        ORDER BY weight DESC""").fetchdf()
    return pd.concat([sub_leaf, sub_class, co], ignore_index=True)


def write_turtle(con, edges: pd.DataFrame, path) -> None:
    topics = con.execute("SELECT topic_iri, topic_label, class_iri, class_label FROM dim_topic").fetchdf()
    short = lambda iri: "fb:" + iri.replace(BASE_IRI, "")
    lines = ["@prefix fb: <%s> ." % BASE_IRI,
             "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .", "",
             "fb:Feedback a rdfs:Class ; rdfs:label \"Відгук пацієнта\"@uk .", ""]
    for _, r in topics.drop_duplicates("class_iri").iterrows():
        lines.append(f'{short(r.class_iri)} a rdfs:Class ; rdfs:subClassOf fb:Feedback ; rdfs:label "{r.class_label}"@uk .')
    for _, r in topics.iterrows():
        lines.append(f'{short(r.topic_iri)} a rdfs:Class ; rdfs:subClassOf {short(r.class_iri)} ; rdfs:label "{r.topic_label}"@uk .')
    lines.append("")
    for _, r in edges[edges.predicate == "fb:coOccursWith"].iterrows():
        lines.append(f"{short(r.subject_iri)} fb:coOccursWith {short(r.object_iri)} .  # lift={r.weight}, support={r.support}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
