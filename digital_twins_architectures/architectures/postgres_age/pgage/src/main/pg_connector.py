import time
from sqlalchemy import create_engine, text
from sqlalchemy.engine.base import Engine
from sqlalchemy import event
import pandas as pd
import os, sys
from psycopg2.extras import execute_values
import psycopg2
from sqlalchemy import event
import utils


class PG_Connector:
    def __init__(self, pg_ip, pg_port, pg_user, pg_psw, pg_db) -> None:
        self.__ip = pg_ip
        self.__port = pg_port
        self.__user = pg_user
        self.__psw = pg_psw
        self.__current_db = pg_db
        self.__logger = utils.setup_logger("PG_Connector")
        self.__engine = self.__connect_to_db()
        event.listen(self.__engine, "connect", self._disable_parallelism)

    @staticmethod
    def _disable_parallelism(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("SET max_parallel_workers_per_gather = 0;")
        cursor.execute("SET max_parallel_workers = 0;")
        cursor.close()

    def __connect_to_db(self) -> Engine:
        return create_engine(
            f"postgresql+psycopg2://{self.__user}:{self.__psw}@{self.__ip}:{self.__port}/{self.__current_db}",
            pool_recycle=2000,
        )

    def insert_dataframe_batch(
        self,
        df: pd.DataFrame,
        table: str,
        page_size: int = 20_000,
    ):
        if df.empty:
            return

        cols = list(df.columns)
        values = df.to_records(index=False).tolist()

        insert_sql = f"""
            INSERT INTO {table} ({', '.join(cols)})
            VALUES %s
        """

        # usa raw_connection per ottenere cursore psycopg2
        raw_conn = self.__engine.raw_connection()
        try:
            cur = raw_conn.cursor()
            try:
                cur.execute("SET max_parallel_workers_per_gather = 0;")
                cur.execute("SET max_parallel_workers = 0;")
                execute_values(cur, insert_sql, values, page_size=page_size)
                raw_conn.commit()
            finally:
                cur.close()
        finally:
            raw_conn.close()

    def query(self, query: str, evaluating: bool = False) -> list:
        """
        Esegue una query su PostgreSQL + AGE.
        Se evaluating=True, ritorna anche tempi di esecuzione.
        """
        # ottieni la connessione raw psycopg2
        raw_conn = self.__engine.raw_connection()
        try:
            cur = raw_conn.cursor()
            cur.execute("LOAD 'age';")
            cur.execute('SET search_path = ag_catalog, "$user", public;')
            cur.execute("SET max_parallel_workers_per_gather = 0;")
            cur.execute("SET max_parallel_workers = 0;")
            try:
                start_time = time.time()
                cur.execute(query)  # Cypher come stringa, senza text()
                end_time = time.time()
                raw_conn.commit()  # commit obbligatorio per TRUNCATE o INSERT

                # tenta di leggere i risultati
                try:
                    res = cur.fetchall()
                except psycopg2.ProgrammingError:
                    # se la query non ritorna righe, restituisci rowcount
                    res = cur.rowcount

                self.__logger.debug(
                    f"Query executed in {end_time - start_time:.4f} seconds."
                )

                if evaluating:
                    return res, start_time, end_time, end_time - start_time

                return res
            finally:
                cur.close()
        finally:
            raw_conn.close()

    def insert_stream(self, table: str, data: pd.DataFrame):
        queries = [
            f"INSERT INTO {table} ({','.join(row)})" for _, row in data.iterrows()
        ]
        with self.__engine.connect() as connection:
            try:
                queries.map(lambda query: connection.execute(query))
            except Exception as e:
                self.__logger.exception(e)

    def close(self):
        self.conn.close()
