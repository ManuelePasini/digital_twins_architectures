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

# Load MongoDB connection parameters
MONGO_IP = os.getenv("MONGODB_IP")
MONGO_PORT = os.getenv("MONGODB_PORT")
MONGO_DB_NAME = os.getenv("MONGODB_DB_NAME")
MONGO_TASK_COLLECTION = os.getenv("MONGO_TASK_COLLECTION")

PG_DATABASE_URL = (
    f"postgresql+psycopg2://{PG_USER}:{PG_PSW}@{PG_HOST}:{PG_PORT}/{PG_DB_NAME}"
)
DATAPATH = "digital_twins_architectures/architectures/postgres_age/input_data"


graph_ts_middleware = age_middleware.Timescale_Age_Postgis_Middleware(
    PG_HOST, PG_PORT, PG_USER, PG_PSW, PG_DB_NAME
)

# List entities in input_data path
input_entities = [
    os.path.join(DATAPATH, json_file)
    for json_file in os.listdir(DATAPATH)
    if json_file.endswith(".json")
]

input_measurements = [
    os.path.join(DATAPATH, "measurements", json_file)
    for json_file in os.listdir(os.path.join(DATAPATH, "measurements"))
    if json_file.endswith(".json")
]

# engine = create_engine(PG_DATABASE_URL)

edge_columns = ["source_id", "edge_label", "dest_id"]
# edges_properties = ["belongsTo", "hasDevice", "hasAgriParcel"]
edges = pd.DataFrame(columns=edge_columns)
entities = []

try:

    entities = [
        json.load(entity)
        for json_file in input_entities
        for entity in [open(json_file, "r")]
    ]

    measurements = [
        doc
        for json_file in input_measurements
        for entity in [open(json_file, "r")]
        for doc in json.load(entity)
    ]

    edges_data = [
        [entity["id"], edge, dest_node]
        for entity in entities
        for edge in utils.get_entity_edges(entity)
        if (dest_node := entity.copy().pop(edge, None)) is not None
    ]

    edges = pd.DataFrame(edges_data, columns=edge_columns)
    edges = edges[~edges["dest_id"].apply(utils.is_dict_or_list_of_dicts)]

    graph_ts_middleware.load_age_environment(GRAPH_NAME)
    for entity in entities:
        graph_ts_middleware.insert_custom_vertex(GRAPH_NAME, entity["type"], entity)
    for _, edge in edges.iterrows():
        graph_ts_middleware.create_edges(
            GRAPH_NAME,
            edge["source_id"],
            edge["edge_label"],
            edge["dest_id"],
        )

    for measurement in measurements:
        measurement.pop("_id", None)
        try:
            graph_ts_middleware.upload_measurement(
                GRAPH_NAME, "ag_catalog.measurements", measurement
            )
        except Exception as e:
            logger.exception(f"Measurement already in db, {e}")

    # Loading Tasks from WeLaSeR
    mongo_connector = mongodb_connector.MongoDBConnector(MONGO_IP, MONGO_PORT)
    mongo_connector.set_database(MONGO_DB_NAME)
    mongo_connector.set_collection(MONGO_TASK_COLLECTION)

    tasks_entities = mongo_connector.find(query={"type": "AgriRobot"}, limit=500)
    tasks_edges = [
        [entity["id"], edge, dest_node]
        for entity in tasks_entities
        for edge in utils.get_entity_edges(entity)
        if (dest_node := entity.copy().pop(edge, None)) is not None
    ]

    edges = pd.DataFrame(tasks_edges, columns=edge_columns)
    edges = edges[~edges["dest_id"].apply(utils.is_dict_or_list_of_dicts)]

    logger.info("Inserting AgriRobot entities...")
    for entity in tasks_entities:
        graph_ts_middleware.insert_custom_vertex(GRAPH_NAME, entity["type"], entity)
    logger.info("Inserting AgriRobot Edges...")
    for _, edge in edges.iterrows():
        graph_ts_middleware.create_edges(
            GRAPH_NAME,
            edge["source_id"],
            edge["edge_label"],
            edge["dest_id"],
        )

except Exception as e:
    logger.exception(f"Something went wrong while testing Apache Age... {e}")
    logger.exception(e.__doc__)
    sys.exit(1)
