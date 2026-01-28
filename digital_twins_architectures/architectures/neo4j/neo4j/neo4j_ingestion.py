import subprocess
import time
from pathlib import Path
import os
import pandas as pd
import uuid
import utils
import re
import json
from neo4j import GraphDatabase

DATASET = os.getenv("DATASET", "smartbench")
DATASET_SIZE = os.getenv("DATASET_SIZE", "small")
ITERATIONS = os.getenv("INGESTION_ITERATIONS", "1")
THREADS = os.getenv("THREAD", "1")
NEO4J_BATCH_SIZE = os.getenv("NEO4J_BATCH_SIZE", 1000)
RESOURCES_PATH = Path("/") / "neo4j" / "neo4j" / "resources"
DATASET_PATH = RESOURCES_PATH / "datasets" / DATASET / DATASET_SIZE
GRAPH_FILE = DATASET_PATH / "graph.cypher"
TIMESERIES_FILE = DATASET_PATH / "ts.cypher"
TIMESERIES_JSON_PATH = DATASET_PATH / "timeseries"
RESULTS_DIR = Path("/") / "neo4j" / "neo4j" / "tests" / "results" / "neo4j" / "ingestion_stats"

ingestion_statistics_output_file = os.path.join(RESULTS_DIR, "ingestion_statistics.csv")
ingestion_csv_header = "test_id,model,startTimestamp,endTimestamp,dataset,datasetSize,threads,graphElapsedTime,tsElapsedTime,elapsedTime,numMachines,storage"

logger = utils.setup_logger("NEO4J_SmartBench_Ingestion")

TS_REGEX = re.compile(
    r"timestamp\s*:\s*'([^']+)'"
)

def get_driver(uri, user, password):
    return GraphDatabase.driver(uri, auth=(user, password))


# ---------- Ingestion logic ----------

UNWIND_QUERY = """
MATCH (s:Sensor {id: $sensor_id})
UNWIND $rows AS row
CREATE (s)-[:hasTemperature]->(
    :Temperature {
        id: row.id,
        timestamp: datetime(row.timestamp),
        temperature: row.temperature,
        location: point({
            x: row.x,
            y: row.y,
            z: row.z
        })
    }
)
"""


def ingest_temperature_file_unwind(
    driver,
    jsonl_path: Path,
    batch_size: int = 1000
):
    """
    Ingests a JSONL temperature file using UNWIND batching.
    Parsing time is excluded from ingestion timing.
    """

    if not jsonl_path.exists():
        raise FileNotFoundError(jsonl_path)

    batch = []
    sensor_id = None

    ingestion_start = None
    ingestion_end = None

    with jsonl_path.open() as f, driver.session() as session:
        for line in f:
            # -------- parsing (excluded from timing) --------
            obj = json.loads(line)

            if sensor_id is None:
                sensor_id = obj["sensor"]["id"]

            loc = obj["location"].replace("POINT(", "").replace(")", "")
            x, y, z = map(float, loc.split())

            batch.append({
                "id": obj["id"],
                "timestamp": obj["timestamp"],
                "temperature": obj["payload"]["temperature"],
                "x": x,
                "y": y,
                "z": z
            })

            # -------- ingestion --------
            if len(batch) == batch_size:
                if ingestion_start is None:
                    ingestion_start = time.time()

                session.run(
                    UNWIND_QUERY,
                    sensor_id=sensor_id,
                    rows=batch
                )
                batch.clear()

        # flush final batch
        if batch:
            if ingestion_start is None:
                ingestion_start = time.time()

            session.run(
                UNWIND_QUERY,
                sensor_id=sensor_id,
                rows=batch
            )

    ingestion_end = time.time()

    return ingestion_start, ingestion_end, ingestion_end - ingestion_start


def ingest_cypher_file_full(cypher_path: Path):
    if not cypher_path.exists():
        raise FileNotFoundError(cypher_path)

    with cypher_path.open() as f:
        raw_content = f.read()

    # Eventuale processing del timestamp
    processed = TS_REGEX.sub(r"timestamp: datetime('\1')", raw_content)

    start = time.time()

    proc = subprocess.run(
        ["cypher-shell"],
        input=processed,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE
    )

    if proc.returncode != 0:
        print(proc.stderr)
        raise RuntimeError("Ingestion failed")

    print(f"Ingestion done in {time.time() - start:.2f}s")
    total_end = time.time()
    return start, total_end, total_end - start

def main():
    ingestion_statistics = pd.DataFrame(columns=ingestion_csv_header.split(","))
    driver = get_driver(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="neo4j"
    )
    for iteration in range(int(ITERATIONS)):
        myUUID = uuid.uuid4()

        logger.info(f"--- Ingestion iteration {iteration} of {ITERATIONS} - DATASET {DATASET} - SIZE {DATASET_SIZE} ---")

        logger.info(f"Ingesting {GRAPH_FILE} ...")

        graph_start, _, graph_elapsed = ingest_cypher_file_full(GRAPH_FILE)
        logger.info(f"Done {GRAPH_FILE} in {graph_elapsed:.3f}s")

        logger.info(f"Ingesting timeseries...")
        if DATASET_SIZE != "big" or DATASET_SIZE == "large":
            _, ts_end, ts_elapsed = ingest_cypher_file_full(TIMESERIES_FILE)
        else:
            ts_elapsed = 0
            ts_end = 0
            for id, file in enumerate(os.listdir(TIMESERIES_JSON_PATH)):
                _, ts_end, elapsed = ingest_temperature_file_unwind(
                    driver,
                    Path(os.path.join(TIMESERIES_JSON_PATH, file)),
                    batch_size=10000
                )
                ts_elapsed = ts_elapsed + elapsed
            
                logger.info(f"Processed {id}th timeseries file")
        logger.info(f"Ingested timeseries in {ts_elapsed:.3f}s")
        ingestion_statistics = pd.concat(
            [
                ingestion_statistics,
                pd.DataFrame(
                    [
                        [
                            myUUID,
                            "Neo4j",
                            graph_start,
                            ts_end,
                            DATASET,
                            DATASET_SIZE,
                            THREADS,
                            graph_elapsed,
                            ts_elapsed,
                            graph_elapsed + ts_elapsed,
                            1,
                            -1,
                        ]
                    ],
                    columns=ingestion_csv_header.split(","),
                ),
            ],
            ignore_index=True,
        )

        ingestion_statistics.to_csv(
            ingestion_statistics_output_file,
            index=False,
            mode="a",
            header=not os.path.exists(ingestion_statistics_output_file),
        )



if __name__ == "__main__":
    main()
