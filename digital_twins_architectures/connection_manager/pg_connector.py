from sqlalchemy import create_engine, text
from sqlalchemy.engine.base import Engine
import utils
import pandas as pd
import os, sys

# utils_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.join("..")))
# sys.path.insert(0, utils_dir)
# from utils import utils


class PG_Connector:
    def __init__(self, pg_ip, pg_port, pg_user, pg_psw, pg_db) -> None:
        self.__ip = pg_ip
        self.__port = pg_port
        self.__user = pg_user
        self.__psw = pg_psw
        self.__current_db = pg_db
        self.__logger = utils.setup_logger("PG_Connector")
        self.__engine = self.__connect_to_db()

    def __connect_to_db(self) -> Engine:
        return create_engine(
            f"postgresql+psycopg2://{self.__user}:{self.__psw}@{self.__ip}:{self.__port}/{self.__current_db}",
            pool_recycle=2000,
        )

    def query(self, query: str) -> list:
        with self.__engine.connect() as connection:
            result = connection.execute(text(query))
            connection.execute(text("COMMIT;"))
            if result.returns_rows:
                return result.fetchall()
            else:
                return result.rowcount

    def insert_stream(self, table: str, data: pd.DataFrame):
        queries = [
            f"INSERT INTO {table} ({','.join(row)})" for _, row in data.iterrows()
        ]
        with self.__engine.connect() as connection:
            try:
                queries.map(lambda query: connection.execute(query))
            except Exception as e:
                self.__logger.exception(e)
