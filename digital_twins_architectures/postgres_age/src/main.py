from sqlalchemy import create_engine, text
import dotenv
import os
import sys
import unittest
from utils import age_utils

if not dotenv.load_dotenv("digital_twins_architectures/postgres_age/.env"):
    print("Something went wrong while finding .env")
    sys.exit(1)

# Configura i parametri di connessione

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

engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as connection:
        age_utils.load_postgres_extensions(connection, GRAPH_NAME)


except Exception as e:
    print(f"Something went wrong while testing Apache Age... {e}")
    print(e.__doc__)
    sys.exit(1)
finally:
    connection.close()
