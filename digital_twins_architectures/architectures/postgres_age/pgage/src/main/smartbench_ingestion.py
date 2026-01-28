import dotenv
import os
import sys
import age_middleware
import measurement_mappings
import json
import pandas as pd
import time
import uuid
import utils
from pathlib import Path


def stream_json_measurements(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


logger = utils.setup_logger("Timescale_PostGIS_Age_Ingestion")

# if not dotenv.load_dotenv(
#     "digital_twins_architectures/architectures/postgres_age/.env"
# ):
#     logger.exception("Something went wrong while finding .env")
#     sys.exit(1)

# --- PATH MANAGEMENT ---
# Resolve the absolute path of the current script's directory
BASE_DIR = Path(__file__).resolve().parent
# Define the root of the project (two levels up)
PROJECT_ROOT = BASE_DIR.parents[1]
# Insert the project root into sys.path to allow imports from 'utils'
sys.path.insert(0, str(PROJECT_ROOT))

# --- FILESYSTEM SETUP ---
RESOURCES_DIR = BASE_DIR / "resources"
QUERIES_DIR = RESOURCES_DIR / "queries"
RESULTS_DIR = BASE_DIR.parent / "results" / "pgage" / "ingestion_time"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

DATASET_PATH = Path(RESOURCES_DIR) / "dataset" / "smartbench"
PG_USER = os.getenv("POSTGRES_USER", "postgres")
PG_PSW = os.getenv("POSTGRES_PSW", "password")
PG_DB_NAME = os.getenv("PGAGE_DB_NAME", "smartbench_eval")
PG_HOST = os.getenv("POSTGRES_HOST", "pgage")
PG_PORT = os.getenv("POSTGRES_PORT", "5432")
DATASET_SIZE = os.getenv("DATASET_SIZE", "small")

INGESTION_ITERATIONS = int(os.getenv("INGESTION_ITERATIONS", 1))

# Apache AGE graph name
GRAPH_NAME = os.getenv("GRAPH_NAME", "smartbench")
DATAFILES = [
    f"{DATASET_PATH}/{DATASET_SIZE}/group.json",
    f"{DATASET_PATH}/{DATASET_SIZE}/user.json",
    f"{DATASET_PATH}/{DATASET_SIZE}/platformType.json",
    f"{DATASET_PATH}/{DATASET_SIZE}/sensorType.json",
    f"{DATASET_PATH}/{DATASET_SIZE}/platform.json",
    f"{DATASET_PATH}/{DATASET_SIZE}/infrastructureType.json",
    f"{DATASET_PATH}/{DATASET_SIZE}/infrastructure.json",
    f"{DATASET_PATH}/{DATASET_SIZE}/sensor.json",
    f"{DATASET_PATH}/{DATASET_SIZE}/virtualSensorType.json",
    f"{DATASET_PATH}/{DATASET_SIZE}/virtualSensor.json",
    f"{DATASET_PATH}/{DATASET_SIZE}/semanticObservationType.json",
]
TS_DIRECTORY = f"{DATASET_PATH}/{DATASET_SIZE}/timeseries/"
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 20_000))
buffer = []

MEASUREMENT_TABLE = "public.measurements"
MEASUREMENT_SCHEMA = "time,sensor_id,type,val,location".split(",")

### STATISTICS_SETUP ###

ingestion_statistics_output_file = os.path.join(RESULTS_DIR, "ingestion_statistics.csv")
ingestion_csv_header = "test_id,model,startTimestamp,endTimestamp,dataset,datasetSize,threads,graphElapsedTime,tsElapsedTime,elapsedTime,numMachines,storage,iteration"
ingestion_statistics = pd.DataFrame(columns=ingestion_csv_header.split(","))

graph_ts_middleware = age_middleware.Timescale_Age_Postgis_Middleware(
    PG_HOST, PG_PORT, PG_USER, PG_PSW, PG_DB_NAME
)

myUUID = uuid.uuid4()

for iteration in range(INGESTION_ITERATIONS):
    graph_ts_middleware.delete_graph(GRAPH_NAME)
    graph_ts_middleware.clear_timeseries_storage(MEASUREMENT_TABLE)
    graph_ts_middleware.load_age_environment(GRAPH_NAME)
    graph_ts_middleware.query("SET max_parallel_workers_per_gather = 0;")
    logger.info("Apache Age is correctly installed and configured.")
    graph_ts_middleware.query(
        f"""
        CREATE TABLE IF NOT EXISTS {MEASUREMENT_TABLE} (
            time timestamp NOT NULL,
            sensor_id text NOT NULL,
            type text,
            val double precision,
            location geometry(PointZ),
            PRIMARY KEY(time, sensor_id, type)
        );

        SELECT create_hypertable('{MEASUREMENT_TABLE}', 'time', if_not_exists => TRUE);
        """
    )
    logger.info("TimescaleDB is correctly installed and configured.")
    logger.info("Loading graph data...")
    start_time = time.time()
    for file in DATAFILES:
        logger.info(f"Uploading {file}")
        with open(file, "r") as f:
            entities = json.load(f)
            for entity in entities:
                try:
                    graph_ts_middleware.process_entity(
                        entity,
                        GRAPH_NAME,
                        MEASUREMENT_TABLE,
                    )
                except Exception as e:
                    logger.error(f"Error processing entity: {e}")
    graph_ingestion_time = time.time() - start_time
    logger.info(f"Graph data uploaded in {graph_ingestion_time:.2f} seconds.")
    logger.info(f"Uploading timeseries data...")
    start_time_ts = time.time()
    for file in os.listdir(TS_DIRECTORY):
        if not file.endswith(".json"):
            continue

        logger.info(f"Uploading {file}")
        first = True
        for measurement in stream_json_measurements(os.path.join(TS_DIRECTORY, file)):
            if first:
                graph_ts_middleware.process_entity(
                    measurement,
                    GRAPH_NAME,
                    MEASUREMENT_TABLE,
                )
                first = False
            mapper = measurement_mappings.get_mapping_function(measurement["type"])
            if mapper is None:
                continue

            row = mapper(measurement)
            buffer.append(row)

            if len(buffer) >= BATCH_SIZE:
                df = pd.DataFrame(buffer, columns=MEASUREMENT_SCHEMA)
                graph_ts_middleware.process_timeseries_batch(
                    df,
                    MEASUREMENT_TABLE,
                )
                buffer.clear()

        # flush finale
        if buffer:
            df = pd.DataFrame(buffer, columns=MEASUREMENT_SCHEMA)
            graph_ts_middleware.process_timeseries_batch(
                df,
                MEASUREMENT_TABLE,
            )
            buffer.clear()
    end_time = time.time()
    timeseries_ingestion_time = end_time - start_time_ts
    graph_ts_middleware.query(
        f"""
            ALTER TABLE {MEASUREMENT_TABLE}
            ALTER COLUMN location TYPE geometry(PointZ, 4326)
            USING ST_Force3D(location);

            DROP INDEX IF EXISTS measurements_location_gist;
            CREATE INDEX measurements_location_gist
            ON {MEASUREMENT_TABLE}
            USING GIST (location);
        """
    )

    logger.info(f"Timeseries data uploaded in {timeseries_ingestion_time:.2f} seconds.")
    logger.info(
        "Data ingestion completed. Total ingestion time: {:.2f} seconds.".format(
            graph_ingestion_time + timeseries_ingestion_time
        )
    )

    ingestion_statistics = pd.concat(
        [
            ingestion_statistics,
            pd.DataFrame(
                [
                    [
                        myUUID,
                        "PGAge",
                        start_time,
                        end_time,
                        os.getenv("DATASET", "smartbench"),
                        os.getenv("DATASET_SIZE", "small"),
                        os.getenv("THREAD", 1),
                        graph_ingestion_time * 1000,
                        timeseries_ingestion_time * 1000,do
                        (graph_ingestion_time + timeseries_ingestion_time) *1000,
                        1,
                        -1,
                        iteration
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
