import os
import sys
import uuid
import yaml
import dotenv
import pandas as pd
from pathlib import Path
import logging
import age_middleware
import utils


# --- PATH MANAGEMENT ---
# Resolve the absolute path of the current script's directory
BASE_DIR = Path(__file__).resolve().parent
# Define the root of the project (two levels up)
PROJECT_ROOT = BASE_DIR.parents[1]
# Insert the project root into sys.path to allow imports from 'utils'
sys.path.insert(0, str(PROJECT_ROOT))


# --- ENVIRONMENT CONFIGURATION ---
DOTENV_PATH = PROJECT_ROOT / ".." / ".env"
logger = utils.setup_logger("PGAGE_SmartBench_QueryEvaluation")

# if not dotenv.load_dotenv(DOTENV_PATH):
#     logger.error(f"Failed to load .env from: {DOTENV_PATH}")
#     sys.exit(1)

# --- CONFIGURATION OBJECTS ---
DB_CONFIG = {
    "pg_ip": os.getenv("POSTGRES_HOST", "pgage"),
    "pg_port": os.getenv("POSTGRES_PORT", "5432"),
    "pg_user": os.getenv("POSTGRES_USER", "postgres"),
    "pg_psw": os.getenv("POSTGRES_PSW", "password"),
    "pg_db": os.getenv("PGAGE_DB_NAME", "smartbench_eval"),
}

BENCHMARK_SETTINGS = {
    "dataset_size": os.getenv("DATASET_SIZE", "small"),
    "query_selectivity": os.getenv("QUERY_SELECTIVITY", "increased"),
    "iterations": int(os.getenv("QUERY_ITERATIONS", 1)),
    "graph_name": os.getenv("GRAPH_NAME", "SmartBench"),
}

# --- FILESYSTEM SETUP ---
RESOURCES_DIR = BASE_DIR / "resources"
QUERIES_DIR = RESOURCES_DIR / "queries"
RESULTS_DIR = BASE_DIR.parent / "results" / "pgage" / "query_evaluation"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# --- RESOURCE LOADING ---
def get_temporal_constraints():
    """
    Parses the YAML file and returns constraints for the selected selectivity level.
    """
    yaml_path = QUERIES_DIR / "time_constraints.yaml"
    try:
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)
        return data["temporalConstraints"][BENCHMARK_SETTINGS["query_selectivity"]]
    except (FileNotFoundError, KeyError) as e:
        logger.error(f"Critical error loading YAML constraints: {e}")
        sys.exit(1)


TIME_CONSTRAINTS = get_temporal_constraints()

# --- MIDDLEWARE INITIALIZATION ---
# Initialize the middleware using dictionary unpacking for DB parameters
graph_ts_middleware = age_middleware.Timescale_Age_Postgis_Middleware(**DB_CONFIG)
graph_ts_middleware.load_age_environment(BENCHMARK_SETTINGS["graph_name"])

# --- QUERY WORKLOAD DEFINITION ---
QUERY_LIST = [
    "EnvironmentCoverage",
    "EnvironmentAggregate",
    "MaintenanceOwners",
    "EnvironmentOutlier",
    "AgentOutlier",
    "AgentHistory",
]

# List to accumulate dictionary records (more efficient than pd.concat)
performance_records = []

# --- BENCHMARK EXECUTION LOOP ---
for iteration in range(BENCHMARK_SETTINGS["iterations"]):
    logger.info(f"--- Starting Iteration {iteration} ---")
    # Generate a unique ID for this specific batch of constraints
    batch_uuid = str(uuid.uuid4())

    for query_name in QUERY_LIST:
        logger.info(f"Executing Query: {query_name}")

        # Retrieve constraints for the specific query and dataset size
        query_constraints = TIME_CONSTRAINTS.get(query_name, {}).get(
            BENCHMARK_SETTINGS["dataset_size"], []
        )

        # Load SQL/Cypher query template from text file
        query_file = QUERIES_DIR / f"{query_name}.txt"
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
                # Execute query and capture performance metrics
                # Middleware returns: result, start_time, end_time, elapsed_time
                execution_result, _, _, elapsed = graph_ts_middleware.query(
                    processed_query, evaluating=True
                )

                # Count returned entities (handling potential non-list returns)
                entity_count = (
                    len(execution_result) if isinstance(execution_result, list) else 0
                )

                # Append execution data to our accumulator
                performance_records.append(
                    {
                        "test_id": batch_uuid,
                        "model": "PGAge",
                        "dataset": "smartbench",
                        "datasetSize": BENCHMARK_SETTINGS["dataset_size"],
                        "threads": 1,
                        "queryName": query_name,
                        "queryType": "edgesDirection",
                        "elapsedTime": round(elapsed * 1000, 2),
                        "numEntities": entity_count,
                        "numMachines": 1,
                        "querySelectivity": BENCHMARK_SETTINGS["query_selectivity"],
                        "temporalRangeIndex": idx,
                        "iteration": iteration,
                    }
                )

            except Exception as e:
                logger.error(f"Execution failed for {query_name} at range {idx}: {e}")

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
