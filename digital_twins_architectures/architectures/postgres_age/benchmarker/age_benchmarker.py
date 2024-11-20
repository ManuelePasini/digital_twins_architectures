import sys
import os
import time
import pandas as pd

age_middleware_dir = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        os.path.join("..", "src", "age_utils"),
    )
)
sys.path.insert(0, age_middleware_dir)

dt_benchmarker_dir = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__), os.path.join("..", "..", "..", "benchmarks")
    )
)
sys.path.insert(0, dt_benchmarker_dir)

connection_manager_dir = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__), os.path.join("..", "..", "..", "connection_manager")
    )
)
sys.path.insert(0, connection_manager_dir)

import architecture_benchmarker as Architecture_Benchmarker
from connection_manager import pg_connector
from utils import utils


class AGE_Benchmarker(Architecture_Benchmarker):
    def __init__(self, conn_dict: dict, statistics_columns: list) -> None:
        self.logger = utils.setup_logger("AGE_Benchmarker")
        self.statistics_columns = statistics_columns
        self.graph_ts_middleware = pg_connector.PG_Connector(
            conn_dict["endpoint"],
            conn_dict["port"],
            conn_dict["user"],
            conn_dict["psw"],
            conn_dict["db_name"],
        )

    def query(
        self, test_id: int, query_id: str, query: str, iteration: int
    ) -> pd.DataFrame:
        try:
            start_time = time.time()
            query_result = self.graph_ts_middleware.query(query)
            end_time = time.time()
            return pd.DataFrame(
                [
                    [
                        test_id,
                        query_id,
                        iteration,
                        start_time,
                        end_time,
                        end_time - start_time,
                        query_result is None,
                    ]
                ],
                columns=self.statistics_columns,
            )
        except Exception as e:
            self.logger.exception(f"Something went wrong while querying endpoint, {e}")
            self.logger.exception(f"Doc: {e.__doc__}")

    def bulk_query(self, test_id, queries: dict, iterations: int) -> pd.DataFrame:
        query_statistics = []
        for iteration in range(0, iterations):
            for query_index, query in queries.items():
                query_statistics.append(
                    self.query(test_id, query_index, query, iteration),
                    ignore_index=True,
                )
        return pd.concat(query_statistics, ignore_index=True)
