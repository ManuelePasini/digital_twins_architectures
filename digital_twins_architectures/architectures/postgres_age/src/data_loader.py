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

logger = utils.setup_logger("Timescale_PostGIS_Age_main")

if not dotenv.load_dotenv(
    "digital_twins_architectures/architectures/postgres_age/.env"
):
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

# Load WeLaSeR connection parameters
WELASER_IP = os.getenv("WELASER_IP")
WELASER_PORT = os.getenv("WELASER_PORT")
WELASER_DB_NAME = os.getenv("WELASER_DB_NAME")
WELASER_TASK_COLLECTION = os.getenv("WELASER_TASK_COLLECTION")

# Load Agritech connection parameters
AGRITECH_IP = os.getenv("AGRITECH_IP")
AGRITECH_PORT = os.getenv("AGRITECH_PORT")
AGRITECH_DB_NAME = os.getenv("AGRITECH_DB_NAME")
AGRITECH_TASK_COLLECTION = os.getenv("AGRITECH_TASK_COLLECTION")

PG_DATABASE_URL = (
    f"postgresql+psycopg2://{PG_USER}:{PG_PSW}@{PG_HOST}:{PG_PORT}/{PG_DB_NAME}"
)

MEASUREMENT_TABLE_SCHEMA = os.getenv("MEASUREMENT_TABLE_SCHEMA")
MEASUREMENT_TABLE = "public.measurements"

graph_ts_middleware = age_middleware.Timescale_Age_Postgis_Middleware(
    PG_HOST, PG_PORT, PG_USER, PG_PSW, PG_DB_NAME
)


def load_bulk_entities(entities):
    for entity in entities:
        try:
            entity.pop("_id", None)
            graph_ts_middleware.process_entity(
                entity,
                GRAPH_NAME,
                MEASUREMENT_TABLE,
                json.loads(MEASUREMENT_TABLE_SCHEMA),
                measurement_mappings.get_mapping_function(entity),
            )
        except Exception as e:
            logger.exception(f"Something went wrong while processing entities, {e}")
            graph_ts_middleware.load_age_environment(GRAPH_NAME)


try:
    graph_ts_middleware.load_age_environment(GRAPH_NAME)

    agritech_connector = mongodb_connector.MongoDBConnector(AGRITECH_IP, AGRITECH_PORT)
    agritech_connector.set_database(AGRITECH_DB_NAME)
    agritech_connector.set_collection("unibo")

    agritech_farm = agritech_connector.find(query={"type": "AgriFarm"})
    agritech_parcels = agritech_connector.find(query={"type": "AgriParcel"})
    agritech_entities = agritech_connector.find(
        query={"namespace": {"$not": {"$regex": "ndr"}}},
    )

    load_bulk_entities(agritech_farm)
    load_bulk_entities(agritech_parcels)
    load_bulk_entities(agritech_entities)

    # Loading Tasks from WeLaSeR
    welaser_connector = mongodb_connector.MongoDBConnector(WELASER_IP, WELASER_PORT)
    welaser_connector.set_database(WELASER_DB_NAME)
    welaser_connector.set_collection(WELASER_TASK_COLLECTION)

    welaser_entities = welaser_connector.find(query={"type": "AgriRobot"})

    welaser_agri_farm = welaser_connector.find(
        query={"type": "AgriFarm"},
    )

    welaser_agri_parcel = welaser_connector.find(
        query={"type": "AgriParcel"},
    )

    load_bulk_entities(welaser_agri_farm)
    load_bulk_entities(welaser_agri_parcel)
    load_bulk_entities(welaser_entities)


except Exception as e:
    logger.exception(f"Something went wrong while testing Apache Age... {e}")
    logger.exception(e.__doc__)
    sys.exit(1)
