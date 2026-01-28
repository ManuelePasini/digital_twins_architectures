import json
import random
import uuid
from pathlib import Path
from typing import List
from datetime import datetime, timedelta
import os

# -----------------------
# Config
# -----------------------

MONKEY_ISLAND_NAMES = [
    "Guybrush Threepwood",
    "Elaine Marley",
    "LeChuck",
    "Herman Toothrot",
    "Stan",
    "Voodoo Lady",
    "Wally B. Feed",
    "Otis",
    "Carla",
    "Meathook",
    "Bob",
    "Largo LaGrande",
]

START_TIMESTAMP = datetime.fromisoformat("2017-11-08T00:00:00.000")
TIMESTAMP_STEP = timedelta(hours=5)

OUTPUT_PATH = os.path.join("digital_twins_architectures", "generator")
JSON_OUTPUT_FILE = os.path.join(OUTPUT_PATH, "syntethic_nodes_dtgraph.json")
NEO4J_OUTPUT_FILE = os.path.join(OUTPUT_PATH, "syntethic_nodes_neo4j.json")
AEONG_OUTPUT_FILE = os.path.join(OUTPUT_PATH, "syntethic_nodes_aeong.json")
# -----------------------
# Helpers
# -----------------------


def random_monkey_island_name() -> str:
    return random.choice(MONKEY_ISLAND_NAMES)


def generate_node_uri(label: str, index: int) -> str:
    return f"urn:{label}:{index}:{uuid.uuid4().hex}"


def to_iso_timestamp(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


# -----------------------
# Main generator
# -----------------------


def generate_property_graph(
    nodes_per_label: int,
    labels: List[str],
    updates_per_node: int,
    json_output_path: str,
    cypher_update_path: str,
    cypher_create_path: str,
) -> None:

    events = []
    cypher_update_statements = []
    cypher_create_statements = []

    current_timestamp = START_TIMESTAMP

    for label in labels:
        for node_index in range(nodes_per_label):
            node_id = generate_node_uri(label, node_index)
            name = random_monkey_island_name()
            ts = to_iso_timestamp(current_timestamp)

            # -------- INITIAL CREATE --------
            events.append({"id": node_id, "type": label, "timestamp": ts, "name": name})

            cypher_update_statements.append(
                f"CREATE (n:{label} {{id: '{node_id}', name: '{name}'}});"
            )
            cypher_create_statements.append(
                f"CREATE (n:{label} {{id: '{node_id}', name: '{name}', timestamp: datetime('{ts}')}});"
            )

            current_timestamp += TIMESTAMP_STEP

            # -------- UPDATES --------
            for _ in range(updates_per_node):
                name = random_monkey_island_name()
                ts = to_iso_timestamp(current_timestamp)

                # JSON registra tutti gli eventi
                events.append(
                    {"id": node_id, "type": label, "timestamp": ts, "name": name}
                )

                # Update senza timestamp
                cypher_update_statements.append(
                    f"MATCH (n:{label} {{id: '{node_id}'}}) " f"SET n.name = '{name}';"
                )

                # Create come nuovo nodo con stesso ID ma timestamp diverso
                cypher_create_statements.append(
                    f"CREATE (n:{label} {{id: '{node_id}', name: '{name}', timestamp: datetime('{ts}')}});"
                )

                current_timestamp += TIMESTAMP_STEP

    # -----------------------
    # Write output files
    # -----------------------

    Path(json_output_path).write_text(
        json.dumps(events, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    Path(cypher_update_path).write_text(
        "\n".join(cypher_update_statements), encoding="utf-8"
    )

    Path(cypher_create_path).write_text(
        "\n".join(cypher_create_statements), encoding="utf-8"
    )


# -----------------------
# Example usage
# -----------------------

if __name__ == "__main__":
    generate_property_graph(
        nodes_per_label=2,
        labels=["Person", "Pirate"],
        updates_per_node=3,
        json_output_path="graph_events.json",
        cypher_update_path="cypher_update.cypher",
        cypher_create_path="cypher_create.cypher",
    )
