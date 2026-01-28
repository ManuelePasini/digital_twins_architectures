import time
from pathlib import Path
from neo4j import GraphDatabase
import os
import yaml
import sys
import utils
import uuid
import pandas as pd

def run_query(driver, query):
        start = time.time()
        results, summary, keys = driver.execute_query(query)
        end = time.time()

        logger.info(f"Elapsed time: {end - start:.3f} seconds")
        logger.info(f"Records retrieved: {len(results)}")

        return start, end, end - start, len(results)

# Cambia questi valori con quelli del tuo Neo4j locale
NEO4J_URI = "neo4j://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "neo4j"

# Lista dei file .txt contenenti query Cypher
DATASET = os.getenv("DATASET", "smartbench")
DATASET_SIZE = os.getenv("DATASET_SIZE", "small")
ITERATIONS = int(os.getenv("QUERY_ITERATIONS", "1"))
THREADS = os.getenv("THREAD", "1")
QUERY_SELECTIVITY = os.getenv("QUERY_SELECTIVITY", "increased")

RESOURCES_PATH = Path("/") / "neo4j" / "neo4j" / "resources"
QUERIES_PATH = RESOURCES_PATH / "queries"
CONSTRAINTS_FILE = QUERIES_PATH / "time_constraints.yaml"
RESULTS_DIR = Path("/") / "neo4j" / "neo4j" / "results" / "neo4j" / "query_evaluation"


QUERY_LIST = [
    "EnvironmentCoverage",
    "EnvironmentAggregate",
    "MaintenanceOwners",
    "EnvironmentOutlier",
    "AgentOutlier",
    "AgentHistory",
]

logger = utils.setup_logger("NEO4J_SmartBench_QueryEvaluation")

# --- RESOURCE LOADING ---
def get_temporal_constraints(yaml_path):
    """
    Parses the YAML file and returns constraints for the selected selectivity level.
    """
    try:
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)
        return data["temporalConstraints"][QUERY_SELECTIVITY]
    except (FileNotFoundError, KeyError) as e:
        logger.error(f"Critical error loading YAML constraints: {e}")
        sys.exit(1)

TIME_CONSTRAINTS = get_temporal_constraints(CONSTRAINTS_FILE)
driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD),
)

# List to accumulate dictionary records (more efficient than pd.concat)
performance_records = []

# --- BENCHMARK EXECUTION LOOP ---
for iteration in range(ITERATIONS):
    logger.info(f"--- Starting Iteration {iteration} ---")
    # Generate a unique ID for this specific batch of constraints
    batch_uuid = str(uuid.uuid4())

    for query_name in QUERY_LIST:
        logger.info(f"Executing Query: {query_name}")

        # Retrieve constraints for the specific query and dataset size
        query_constraints = TIME_CONSTRAINTS.get(query_name, {}).get(
            DATASET_SIZE, []
        )

        # Load SQL/Cypher query template from text file
        query_file = QUERIES_PATH / f"{query_name}.txt"
        if not query_file.exists():
            logger.warning(f"Query file missing: {query_file}")
            continue

        with open(query_file, "r", encoding="utf-8") as f:
            query_template = f.read().strip()
        query_template.strip()
        for idx, time_range in query_constraints.items():
            logger.debug(f"Running range index {idx}: {time_range}")

            # Inject temporal parameters into the template
            processed_query = query_template.replace(
                "{TSTAMPFROM_PARAM}", str(time_range[0])
            ).replace("{TSTAMPTO_PARAM}", str(time_range[1]))

            try:
                driver.verify_connectivity()
                logger.info("Driver successfully connected to Neo4j")

                tstart, tend, elapsed, entity_count = run_query(driver, processed_query)

                # Append execution data to our accumulator
                performance_records.append(
                    {
                        "test_id": batch_uuid,
                        "model": "Neo4J",
                        "dataset": "smartbench",
                        "datasetSize": DATASET_SIZE,
                        "threads": 1,
                        "queryName": query_name,
                        "queryType": "edgesDirection",
                        "elapsedTime": round(elapsed * 1000, 2),
                        "numEntities": entity_count,
                        "numMachines": 1,
                        "querySelectivity": QUERY_SELECTIVITY,
                        "temporalRangeIndex": idx,
                        "iteration": iteration,
                    }
                )
            except Exception as e:
                logger.error(f"Execution failed for {query_name} at range {idx}: {e}")
            finally:
                driver.close()


# --- RESULTS PERSISTENCE ---
if performance_records:
    df_results = pd.DataFrame(performance_records)
    output_file = RESULTS_DIR / "statistics.csv"

    # Append data if the file exists, otherwise write with header
    df_results.to_csv(
        output_file, mode="a", index=False, header=not output_file.exists()
    )
    logger.info(f"Benchmark completed. Statistics saved to: {output_file}")
else:
    logger.warning("No performance data was collected.")
