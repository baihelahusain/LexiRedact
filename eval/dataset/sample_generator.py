"""
eval/dataset/sample_generator.py — Synthetic evaluation dataset generator.

Generates a reproducible dataset of realistic-but-fictional annotated chunks
and retrieval queries for benchmarking the three Lexiredact pipeline modes.

Design goals:
  - Within-cluster semantic similarity: groups of 4–6 chunks describe the SAME
    scenario from different phrasings, making top-K retrieval non-trivial.
  - Queries are paraphrased from chunk content, not keyword-matched.
  - PII positions are tracked at injection time — no post-hoc regex.
  - Fixed seed → identical output across runs (required by eval constraint 5).

Usage:
  python eval/dataset/sample_generator.py --output-dir eval/dataset/data/
"""

from __future__ import annotations

import argparse
import json
import os
import random
from dataclasses import asdict
from pathlib import Path

from eval.dataset.schema import AnnotatedEntity, EvalChunk, EvalDataset, EvalQuery

try:
    from faker import Faker  # type: ignore[import-untyped]
except ImportError as exc:
    raise ImportError(
        "faker is required for sample generation. Install with: pip install faker"
    ) from exc


# ── Cluster definitions ────────────────────────────────────────────────────────

CLUSTERS: list[str] = [
    "billing_dispute",
    "hr_record",
    "medical_record",
    "legal_correspondence",
    "customer_support",
    "it_security",
]

CLUSTER_ENTITY_TYPES: dict[str, list[str]] = {
    "billing_dispute":      ["PERSON", "EMAIL_ADDRESS", "CREDIT_CARD", "IBAN_CODE"],
    "hr_record":            ["PERSON", "PHONE_NUMBER", "LOCATION"],
    "medical_record":       ["PERSON", "PHONE_NUMBER", "LOCATION"],
    "legal_correspondence": ["PERSON", "LOCATION", "PHONE_NUMBER"],
    "customer_support":     ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER"],
    "it_security":          ["EMAIL_ADDRESS", "PHONE_NUMBER"],
}

# Number of scenario groups per cluster; each group has 4–6 chunks.
SCENARIOS_PER_CLUSTER = 11  # 11 × ~5.5 avg ≈ 60–65 chunks per cluster → 400 total


# ── Text templates ─────────────────────────────────────────────────────────────

BILLING_TEMPLATES = [
    "{name} submitted a billing dispute for invoice #{invoice} on {date}. Email: {email}.",
    "Customer {name} contacted finance about overcharge on invoice #{invoice}. Card: {cc}.",
    "Dispute filed by {name} ({email}) regarding invoice #{invoice} charged to account.",
    "Invoice #{invoice} raised by {name}. Payment card {cc} was charged incorrectly.",
    "Finance team received complaint from {name} about duplicate charge on #{invoice}.",
    "Account holder {name} emailed {email} disputing invoice #{invoice} amount of ${amount}.",
]

HR_TEMPLATES = [
    "{name} joined the {dept} department on {date}. Located in {city}. Phone: {phone}.",
    "Employee record for {name}: role {role}, salary ${salary}K, office {city}.",
    "{name} transferred to {city} office as {role} in {dept}. Contact: {phone}.",
    "HR update: {name} promoted to {role} in {dept}, effective {date}.",
    "Onboarding document for {name}. Department: {dept}. Start date: {date}.",
    "Performance review — {name}, {role}. Location: {city}. Phone: {phone}.",
]

MEDICAL_TEMPLATES = [
    "Patient {name} admitted on {date}. Condition: {condition}. Contact: {phone}.",
    "{name} scheduled for follow-up on {date} at {city} clinic. Phone: {phone}.",
    "Medical record: {name}, diagnosis {condition}, appointment {date}.",
    "Dr. {doctor} treated {name} for {condition} on {date}.",
    "Patient {name} from {city} requested prescription refill. Ref: {phone}.",
    "Discharge summary for {name}: {condition} resolved. Next visit {date}.",
]

LEGAL_TEMPLATES = [
    "Case #{case} — {name} (plaintiff) vs {firm}. Hearing on {date} in {city}.",
    "Law firm {firm} filed motion on behalf of {name} in case #{case}. Phone: {phone}.",
    "{name} retained {firm} for case #{case} proceedings. Contact: {phone}.",
    "Correspondence to {name} regarding case #{case} scheduled in {city}.",
    "Legal notice sent to {name} by {firm}. Case reference #{case}.",
    "Court filing: {firm} representing {name}, hearing {date}, {city}.",
]

SUPPORT_TEMPLATES = [
    "{name} opened support ticket about {issue}. Contact: {email}, {phone}.",
    "Support request from {name} ({email}): {issue}. Priority: high.",
    "Customer {name} called {phone} to report {issue}. Ticket created.",
    "{name} emailed {email} with complaint about {issue}.",
    "Callback requested by {name} at {phone}. Issue: {issue}.",
    "Agent spoke with {name} ({email}) regarding {issue} on {date}.",
]

IT_TEMPLATES = [
    "Security alert: user {email} triggered {event} from IP {ip} on {date}.",
    "Ticket #{ticket}: {email} reported {event}. IP address logged: {ip}.",
    "Admin {email} reset password following {event}. Phone verification: {phone}.",
    "Firewall blocked {ip} after repeated {event} attempts. Notified {email}.",
    "Incident #{ticket}: unauthorised access attempt by {ip}. User: {email}.",
    "IT security log — {event} detected for {email}. Source IP: {ip}.",
]

CLUSTER_TEMPLATES: dict[str, list[str]] = {
    "billing_dispute":      BILLING_TEMPLATES,
    "hr_record":            HR_TEMPLATES,
    "medical_record":       MEDICAL_TEMPLATES,
    "legal_correspondence": LEGAL_TEMPLATES,
    "customer_support":     SUPPORT_TEMPLATES,
    "it_security":          IT_TEMPLATES,
}

QUERY_TEMPLATES: dict[str, list[str]] = {
    "billing_dispute": [
        "Who raised a payment dispute about invoice #{invoice}?",
        "Which customer complained about an overcharge on their billing statement?",
        "Find all billing disputes involving credit card charges.",
        "Who emailed finance about an incorrect invoice?",
    ],
    "hr_record": [
        "Which employee transferred to the {city} office recently?",
        "Find HR records for staff in the {dept} department.",
        "Who was promoted in the latest HR update?",
        "Which employee started in {dept} this year?",
    ],
    "medical_record": [
        "Find patients diagnosed with {condition}.",
        "Which patient has an upcoming appointment in {city}?",
        "Who was discharged recently after treatment?",
        "Find medical records for patients treated by Dr. {doctor}.",
    ],
    "legal_correspondence": [
        "Which cases are scheduled in {city}?",
        "Find filings by law firm {firm}.",
        "Who is the plaintiff in case number #{case}?",
        "Which legal notices were sent recently?",
    ],
    "customer_support": [
        "Find support tickets about {issue}.",
        "Which customer requested a callback recently?",
        "Who reported a {issue} complaint by email?",
        "Find high-priority support requests.",
    ],
    "it_security": [
        "Which IP addresses triggered security alerts?",
        "Find incidents related to {event}.",
        "Which accounts were affected by unauthorised access attempts?",
        "Find IT tickets involving firewall blocks.",
    ],
}


# ── Generator ──────────────────────────────────────────────────────────────────

def generate(
    output_dir: str,
    n_chunks: int = 400,
    n_queries: int = 80,
    seed: int = 42,
) -> EvalDataset:
    """Generate a synthetic eval dataset and write it to ``output_dir``.

    Args:
        output_dir: Directory where ``chunks.json`` and ``queries.json`` are written.
        n_chunks:   Total number of annotated chunks to generate.
        n_queries:  Total number of queries to generate.
        seed:       Random seed for reproducibility. Same seed → identical output.

    Returns:
        The generated :class:`~eval.dataset.schema.EvalDataset`.
    """
    rng = random.Random(seed)
    fake = Faker()
    fake.seed_instance(seed)

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    chunks_per_cluster = n_chunks // len(CLUSTERS)
    queries_per_cluster = n_queries // len(CLUSTERS)

    all_chunks: list[EvalChunk] = []
    all_queries: list[EvalQuery] = []
    chunk_counter = 0
    query_counter = 0

    for cluster in CLUSTERS:
        cluster_chunks: list[EvalChunk] = []
        cluster_query_objs: list[EvalQuery] = []

        # Generate scenario groups of 4–6 chunks
        while len(cluster_chunks) < chunks_per_cluster:
            group_size = rng.randint(4, 6)
            scenario_data = _make_scenario_data(cluster, fake, rng)
            templates = CLUSTER_TEMPLATES[cluster]
            chosen_templates = rng.sample(templates, min(group_size, len(templates)))

            group_ids: list[str] = []
            for tmpl in chosen_templates:
                if len(cluster_chunks) >= chunks_per_cluster:
                    break
                chunk_counter += 1
                chunk_id = f"chunk_{chunk_counter:04d}"
                text, entities = _render_template(tmpl, scenario_data)
                chunk = EvalChunk(
                    chunk_id=chunk_id,
                    raw_text=text,
                    annotated_entities=entities,
                    topic_cluster=cluster,
                )
                cluster_chunks.append(chunk)
                group_ids.append(chunk_id)

            # Generate 1–2 queries per scenario group
            n_q = rng.randint(1, 2)
            q_templates = QUERY_TEMPLATES[cluster]
            for _ in range(n_q):
                if len(cluster_query_objs) >= queries_per_cluster:
                    break
                query_counter += 1
                q_tmpl = rng.choice(q_templates)
                q_text = _render_query(q_tmpl, scenario_data)
                # Relevant = all chunks in this scenario group
                relevant_ids = list(group_ids)
                cluster_query_objs.append(
                    EvalQuery(
                        query_id=f"q_{query_counter:04d}",
                        query_text=q_text,
                        relevant_chunk_ids=relevant_ids,
                        topic_cluster=cluster,
                    )
                )

        all_chunks.extend(cluster_chunks)
        all_queries.extend(cluster_query_objs)

    # Add 10–15 hard-negative queries (wording from wrong cluster)
    hard_negs = _make_hard_negatives(all_chunks, all_queries, rng, query_counter, n=12)
    all_queries.extend(hard_negs)

    # Shuffle for realism (but reproducibly)
    rng.shuffle(all_chunks)
    rng.shuffle(all_queries)

    dataset = EvalDataset(chunks=all_chunks, queries=all_queries)
    _write_dataset(dataset, output_dir)
    return dataset


# ── Scenario data factories ────────────────────────────────────────────────────

def _make_scenario_data(cluster: str, fake: Faker, rng: random.Random) -> dict[str, str]:
    """Build a dict of placeholder values for one scenario group."""
    base: dict[str, str] = {
        "name":    fake.name(),
        "date":    fake.date_this_year().strftime("%Y-%m-%d"),
        "email":   fake.email(),
        "phone":   fake.phone_number(),
        "city":    fake.city(),
        "amount":  str(rng.randint(50, 5000)),
        "invoice": str(rng.randint(1000, 9999)),
        "ticket":  str(rng.randint(10000, 99999)),
        "ip":      fake.ipv4(),
        "dept":    rng.choice(["Finance", "Engineering", "HR", "Legal", "Sales"]),
        "role":    rng.choice(["Manager", "Analyst", "Engineer", "Director", "Associate"]),
        "salary":  str(rng.randint(60, 180)),
        "cc":      fake.credit_card_number(card_type="visa"),
        "iban":    fake.iban(),
        "condition": rng.choice([
            "hypertension", "type-2 diabetes", "chronic fatigue syndrome",
            "migraine disorder", "anxiety disorder"
        ]),
        "doctor":  fake.last_name() + ", MD",
        "firm":    fake.company() + " LLP",
        "case":    str(rng.randint(100000, 999999)),
        "issue":   rng.choice([
            "billing error", "delivery failure", "account access issue",
            "refund request", "service outage", "product defect"
        ]),
        "event":   rng.choice([
            "brute-force login", "port scan", "SQL injection attempt",
            "credential stuffing", "privilege escalation"
        ]),
    }
    return base


def _render_template(
    template: str, data: dict[str, str]
) -> tuple[str, list[AnnotatedEntity]]:
    """Render a template, tracking PII positions as each value is inserted.

    Builds the output string incrementally so that character offsets are exact
    without requiring any post-hoc regex scanning.
    """
    import re

    # Find all {placeholder} tokens in order.
    tokens = re.findall(r"\{(\w+)\}", template)

    # Map placeholder → PII entity type
    placeholder_entity: dict[str, str | None] = {
        "name":   "PERSON",
        "email":  "EMAIL_ADDRESS",
        "phone":  "PHONE_NUMBER",
        "city":   "LOCATION",
        "cc":     "CREDIT_CARD",
        "iban":   "IBAN_CODE",
        "ip":     "IP_ADDRESS",
    }

    entities: list[AnnotatedEntity] = []
    result = template
    # Replace from right to left so offsets stay valid
    for match in reversed(list(re.finditer(r"\{(\w+)\}", template))):
        key = match.group(1)
        value = data.get(key, f"<{key}>")
        result = result[: match.start()] + value + result[match.end():]

    # Now track positions by scanning the rendered string for each PII value
    seen: set[int] = set()
    for key in tokens:
        entity_type = placeholder_entity.get(key)
        if entity_type is None:
            continue
        value = data.get(key, "")
        if not value:
            continue
        start = 0
        while True:
            pos = result.find(value, start)
            if pos == -1 or pos in seen:
                break
            entities.append(AnnotatedEntity(
                text=value,
                entity_type=entity_type,
                start=pos,
                end=pos + len(value),
            ))
            seen.add(pos)
            start = pos + 1
            break  # Track first occurrence only per chunk

    return result, entities


def _render_query(template: str, data: dict[str, str]) -> str:
    """Render a query template, replacing placeholders with scenario data."""
    import re
    result = template
    for match in reversed(list(re.finditer(r"\{(\w+)\}", template))):
        key = match.group(1)
        value = data.get(key, f"<{key}>")
        result = result[: match.start()] + value + result[match.end():]
    return result


def _make_hard_negatives(
    chunks: list[EvalChunk],
    queries: list[EvalQuery],
    rng: random.Random,
    counter: int,
    n: int,
) -> list[EvalQuery]:
    """Create hard-negative queries: wording from one cluster, answers in another."""
    hard_negs: list[EvalQuery] = []
    cluster_to_chunks: dict[str, list[EvalChunk]] = {}
    for c in chunks:
        cluster_to_chunks.setdefault(c.topic_cluster, []).append(c)

    cross_pairs = [
        ("billing_dispute",      "customer_support"),
        ("hr_record",            "legal_correspondence"),
        ("medical_record",       "hr_record"),
        ("customer_support",     "billing_dispute"),
        ("it_security",          "customer_support"),
        ("legal_correspondence", "medical_record"),
    ]

    for i in range(n):
        src_cluster, tgt_cluster = cross_pairs[i % len(cross_pairs)]
        src_queries = [q for q in queries if q.topic_cluster == src_cluster]
        tgt_chunks = cluster_to_chunks.get(tgt_cluster, [])
        if not src_queries or not tgt_chunks:
            continue
        src_q = rng.choice(src_queries)
        relevant = rng.sample(tgt_chunks, min(2, len(tgt_chunks)))
        counter += 1
        hard_negs.append(EvalQuery(
            query_id=f"q_{counter:04d}_hardneg",
            query_text=src_q.query_text,
            relevant_chunk_ids=[c.chunk_id for c in relevant],
            topic_cluster=tgt_cluster,
        ))
    return hard_negs


# ── I/O ───────────────────────────────────────────────────────────────────────

def _write_dataset(dataset: EvalDataset, output_dir: str) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    chunks_data = [
        {
            "chunk_id": c.chunk_id,
            "raw_text": c.raw_text,
            "annotated_entities": [
                {"text": e.text, "entity_type": e.entity_type,
                 "start": e.start, "end": e.end}
                for e in c.annotated_entities
            ],
            "topic_cluster": c.topic_cluster,
        }
        for c in dataset.chunks
    ]
    queries_data = [
        {
            "query_id": q.query_id,
            "query_text": q.query_text,
            "relevant_chunk_ids": q.relevant_chunk_ids,
            "topic_cluster": q.topic_cluster,
        }
        for q in dataset.queries
    ]

    (out / "chunks.json").write_text(json.dumps(chunks_data, indent=2), encoding="utf-8")
    (out / "queries.json").write_text(json.dumps(queries_data, indent=2), encoding="utf-8")
    print(f"Wrote {len(dataset.chunks)} chunks → {out / 'chunks.json'}")
    print(f"Wrote {len(dataset.queries)} queries → {out / 'queries.json'}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic Lexiredact eval dataset")
    parser.add_argument("--output-dir", default="eval/dataset/data/",
                        help="Directory to write chunks.json and queries.json")
    parser.add_argument("--n-chunks", type=int, default=400)
    parser.add_argument("--n-queries", type=int, default=80)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    ds = generate(
        output_dir=args.output_dir,
        n_chunks=args.n_chunks,
        n_queries=args.n_queries,
        seed=args.seed,
    )
    print(f"\nDataset generated: {len(ds.chunks)} chunks, {len(ds.queries)} queries")
