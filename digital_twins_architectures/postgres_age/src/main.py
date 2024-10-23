from sqlalchemy import create_engine, text
import dotenv
import os
import sys
from utils import age_utils
import json
import pandas as pd


if not dotenv.load_dotenv("digital_twins_architectures/postgres_age/.env"):
    print("Something went wrong while finding .env")
    sys.exit(1)

# Load connection parameters
db_user = os.getenv("POSTGRES_USER")
db_password = os.getenv("POSTGRES_PSW")
db_name = os.getenv("DB_NAME")
db_host = os.getenv("POSTGRES_HOST")
db_port = os.getenv("POSTGRES_PORT")

GRAPH_NAME = os.getenv("GRAPH_NAME")
DATABASE_URL = (
    f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
)

DATAPATH = "digital_twins_architectures/postgres_age/input_data"

# List entities in input_data path
input_entities = [
    os.path.join(DATAPATH, json_file)
    for json_file in os.listdir(DATAPATH)
    if json_file.endswith(".json")
]

engine = create_engine(DATABASE_URL)
edge_columns = ["source_id", "edge_label", "dest_id"]
edges_properties = ["belongsTo", "hasDevice", "hasAgriParcel"]
edges = pd.DataFrame(columns=edge_columns)
nodes = []
entities = []

try:

    entities = [
        json.load(entity)
        for json_file in input_entities
        for entity in [open(json_file, "r")]
    ]

    edges_data = [
        [entity["id"], edge, dest_node]
        for entity in entities
        for edge in edges_properties
        if (dest_node := entity.pop(edge, None)) is not None
    ]

    edges = pd.DataFrame(edges_data, columns=edge_columns)

    with engine.connect() as connection:
        age_utils.load_age_environment(connection, GRAPH_NAME)
        for entity in entities:
            age_utils.insert_custom_vertex(
                connection, GRAPH_NAME, entity["type"], entity
            )
        for _, edge in edges.iterrows():
            age_utils.create_edges(
                connection,
                GRAPH_NAME,
                edge["source_id"],
                edge["edge_label"],
                edge["dest_id"],
            )

except Exception as e:
    print(f"Something went wrong while testing Apache Age... {e}")
    print(e.__doc__)
    sys.exit(1)
finally:
    connection.close()
