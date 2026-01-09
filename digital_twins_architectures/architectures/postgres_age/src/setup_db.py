from sqlalchemy import create_engine, Table, MetaData
import dotenv
import os
import sys
from age_utils import age_middleware, measurement_mappings
import json
import pandas as pd
import psycopg2
from psycopg2.errors import UndefinedFunction

connection_manager_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.path.join("..", ".."))
)
sys.path.insert(0, connection_manager_dir)
from connection_manager import mongodb_connector, pg_connector
from utils import utils

logger = utils.setup_logger("Timescale_PostGIS_Age_setup_DB")

if not dotenv.load_dotenv("./architectures/postgres_age/.env"):
    logger.exception("Something went wrong while finding .env")
    sys.exit(1)

# Load Postgres connection parameters
PG_USER = os.getenv("POSTGRES_USER")
PG_PSW = os.getenv("POSTGRES_PSW")
PG_DB_NAME = os.getenv("DB_NAME")
PG_HOST = os.getenv("POSTGRES_HOST")
PG_PORT = os.getenv("POSTGRES_PORT")

# Apache AGE graph name
GRAPH_NAME = os.getenv("GRAPH_NAME")

PG_DATABASE_URL = (
    f"postgresql+psycopg2://{PG_USER}:{PG_PSW}@{PG_HOST}:{PG_PORT}/{PG_DB_NAME}"
)

MEASUREMENT_TABLE_SCHEMA = [
    "timestamp",
    "device_id",
    "controlled_property",
    "location",
    "value",
    "raw_value",
]
MEASUREMENT_TABLE = "public.measurements"

graph_middleware = age_middleware.Timescale_Age_Postgis_Middleware(
    PG_HOST, PG_PORT, PG_USER, PG_PSW, PG_DB_NAME
)

db_connector = pg_connector.PG_Connector(PG_HOST, PG_PORT, PG_USER, PG_PSW, PG_DB_NAME)

try:
    graph_middleware.load_age_environment(GRAPH_NAME)
    logger.info("Apache Age is correctly installed and configured.")
    db_connector.query(
        f"""
        CREATE TABLE IF NOT EXISTS {MEASUREMENT_TABLE} (
            timestamp timestamp NOT NULL,
            device_id text NOT NULL,
            "controlled_property" text NOT NULL,
            location geometry,
            value double precision,
            raw_value text NOT NULL
        );

        SELECT create_hypertable('{MEASUREMENT_TABLE}', 'timestamp', if_not_exists => TRUE);

        -- Add PK only if missing
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'measurements'::regclass
                AND contype = 'p'
            ) THEN
                ALTER TABLE measurements
                ADD PRIMARY KEY ("timestamp", device_id, controlled_property);
            END IF;
        END$$;
        """
    )
    logger.info("TimescaleDB is correctly installed and configured.")


except Exception as e:
    logger.exception(f"Something went wrong while testing Apache Age... {e}")
    logger.exception(e.__doc__)
    sys.exit(1)
