from sqlalchemy import create_engine, Table, MetaData
import dotenv
import os
import sys
from utils import age_middleware, utils
import json
import pandas as pd

connection_manager_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.path.join("..", ".."))
)
sys.path.insert(0, connection_manager_dir)
from connection_manager import mongodb_connector


if not dotenv.load_dotenv("digital_twins_architectures/postgres_age/.env"):
    print("Something went wrong while finding .env")
    sys.exit(1)

# Load connection parameters
PG_USER = os.getenv("POSTGRES_USER")
PG_PSW = os.getenv("POSTGRES_PSW")
PG_DB_NAME = os.getenv("DB_NAME")
PG_HOST = os.getenv("POSTGRES_HOST")
PG_PORT = os.getenv("POSTGRES_PORT")
MONGO_IP = os.getenv("MONGODB_IP")
MONGO_PORT = os.getenv("MONGODB_PORT")
GRAPH_NAME = os.getenv("GRAPH_NAME")
DATABASE_URL = (
    f"postgresql+psycopg2://{PG_USER}:{PG_PSW}@{PG_HOST}:{PG_PORT}/{PG_DB_NAME}"
)
DATAPATH = "digital_twins_architectures/postgres_age/input_data"

mongo_connector = mongodb_connector.MongoDBConnector(MONGO_IP, MONGO_PORT)
print(mongo_connector.__current_db)

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

engine = create_engine(DATABASE_URL)

edge_columns = ["source_id", "edge_label", "dest_id"]
edges_properties = ["belongsTo", "hasDevice", "hasAgriParcel"]
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
        for edge in edges_properties
        if (dest_node := entity.copy().pop(edge, None)) is not None
    ]

    edges = pd.DataFrame(edges_data, columns=edge_columns)
    edges = edges[~edges["dest_id"].apply(utils.is_dict_or_list_of_dicts)]

    with engine.connect() as connection:
        age_middleware.load_age_environment(connection, GRAPH_NAME)
        for entity in entities:
            age_middleware.insert_custom_vertex(
                connection, GRAPH_NAME, entity["type"], entity
            )
        for _, edge in edges.iterrows():
            age_middleware.create_edges(
                connection,
                GRAPH_NAME,
                edge["source_id"],
                edge["edge_label"],
                edge["dest_id"],
            )

        for measurement in measurements:
            measurement.pop("_id", None)
            try:
                age_middleware.upload_measurement(
                    connection, GRAPH_NAME, "ag_catalog.measurements", measurement
                )
            except Exception as e:
                print(f"Measurement already in db, {e}")

except Exception as e:
    print(f"Something went wrong while testing Apache Age... {e}")
    print(e.__doc__)
    sys.exit(1)
finally:
    connection.close()
