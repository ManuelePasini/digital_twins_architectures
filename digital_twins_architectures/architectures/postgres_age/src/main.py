from sqlalchemy import create_engine, Table, MetaData
import dotenv
import os
import sys
from age_utils import age_middleware
import json
import pandas as pd

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
DATAPATH = "digital_twins_architectures/architectures/postgres_age/input_data"


graph_ts_middleware = age_middleware.Timescale_Age_Postgis_Middleware(
    PG_HOST, PG_PORT, PG_USER, PG_PSW, PG_DB_NAME
)

try:
    graph_ts_middleware.load_age_environment(GRAPH_NAME)

    # agritech_connector = mongodb_connector.MongoDBConnector(AGRITECH_IP, AGRITECH_PORT)
    # agritech_connector.set_database(AGRITECH_DB_NAME)
    # agritech_connector.set_collection("unibo")
    # agritech_entities = agritech_connector.find(
    #     query={
    #         "$and": [
    #             {"namespace": {"$regex": "unibo.watering"}},
    #             {"controlledProperty": {"$ne": "dripper"}},
    #             {"dateObserved": {"$gt": "2024-10-09T17:15:000"}},
    #         ]
    #     }
    # )

    # for entity in agritech_entities:
    #     entity.pop("_id", None)
    #     graph_ts_middleware.process_entity(entity, GRAPH_NAME, "public.measurements")

    # Loading Tasks from WeLaSeR
    welaser_connector = mongodb_connector.MongoDBConnector(WELASER_IP, WELASER_PORT)
    welaser_connector.set_database(WELASER_DB_NAME)
    welaser_connector.set_collection(WELASER_TASK_COLLECTION)

    welaser_entities = welaser_connector.find(
        query={
            "$and": [
                {"type": "AgriRobot"},
                {"timestamp_kafka": {"$gt": 1695836778675}},
            ]
        }
    )

    agri_farm = welaser_connector.find(
        query={"id": "urn:ngsi-ld:AgriFarm:6991ac61-8db8-4a32-8fef-c462e2369055"},
        limit=500,
    )

    for entity in agri_farm:
        graph_ts_middleware.process_entity(entity, GRAPH_NAME, "public.measurements")
    for entity in welaser_entities:
        graph_ts_middleware.process_entity(entity, GRAPH_NAME, "public.measurements")

except Exception as e:
    logger.exception(f"Something went wrong while testing Apache Age... {e}")
    logger.exception(e.__doc__)
    sys.exit(1)
