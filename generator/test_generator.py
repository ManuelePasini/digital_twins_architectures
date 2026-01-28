import csv
from datetime import datetime
from pathlib import Path
import json

PERSON_CSV = "person.csv"
KNOWS_CSV = "person_knows_person.csv"
OUTPUT_CYPHER = "aeong_graph_full.cypher"
OUTPUT_COMMIT_MAP = "commit_to_ts_map.json"


def parse_ts(ts_str):
    return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))


events = []
commit_map = {}  # commit timestamp -> indice progressivo
commit_counter = 1


# Funzione helper per aggiungere eventi e aggiornare commit_map
def add_event(ts, cypher_line):
    global commit_counter
    ts_key = ts.isoformat()
    if ts_key not in commit_map:
        commit_map[ts_key] = commit_counter
        commit_counter += 1
    events.append({"timestamp": ts, "cypher": cypher_line})


# Carica nodi Person
with open(PERSON_CSV, newline="", encoding="utf-8") as f:
    reader = csv.reader(f, delimiter="|")
    for row in reader:
        person_id = row[3]
        creation = parse_ts(row[0])
        deletion_str = row[1]
        deletion = (
            parse_ts(deletion_str) if deletion_str and deletion_str != "NULL" else None
        )

        props = {
            "id": person_id,
            "firstName": row[4],
            "lastName": row[5],
            "gender": row[6],
            "birthDate": row[7],
            "ipAddress": row[8],
            "browserUsed": row[9],
            "locationIP": row[10] if len(row) > 10 else None,
            "languages": row[11] if len(row) > 11 else None,
            "emails": row[12] if len(row) > 12 else None,
        }
        props_str = ", ".join(f"{k}: '{v}'" for k, v in props.items() if v)

        add_event(creation, f"CREATE (p_{person_id}:Person {{ {props_str} }});")
        if deletion:
            add_event(
                deletion,
                f"MATCH (p_{person_id}:Person {{id: '{person_id}'}}) SET p_{person_id}.deleted = true;",
            )

# Carica archi KNOWS
with open(KNOWS_CSV, newline="", encoding="utf-8") as f:
    reader = csv.reader(f, delimiter="|")
    for row in reader:
        from_id, to_id = row[0], row[1]
        creation = parse_ts(row[2])
        deletion_str = row[3]
        deletion = (
            parse_ts(deletion_str) if deletion_str and deletion_str != "NULL" else None
        )

        add_event(
            creation,
            f"MATCH (a:Person {{id: '{from_id}'}}), (b:Person {{id: '{to_id}'}}) CREATE (a)-[:KNOWS {{created: datetime('{creation.isoformat()}')}}]->(b);",
        )
        if deletion:
            add_event(
                deletion,
                f"MATCH (a:Person {{id: '{from_id}'}})-[r:KNOWS]->(b:Person {{id: '{to_id}'}}) SET r.deleted = true;",
            )

# Ordina eventi cronologicamente
events.sort(key=lambda e: e["timestamp"])

# Scrivi il file Cypher
with open(OUTPUT_CYPHER, "w", encoding="utf-8") as f:
    for e in events:
        f.write(e["cypher"] + "\n")

# Salva la mappa commit -> indice progressivo
with open(OUTPUT_COMMIT_MAP, "w", encoding="utf-8") as f:
    json.dump(commit_map, f, indent=2)

print(f"Cypher generato: {OUTPUT_CYPHER}, eventi totali: {len(events)}")
print(f"Mappa commit->timestamp salvata in: {OUTPUT_COMMIT_MAP}")
