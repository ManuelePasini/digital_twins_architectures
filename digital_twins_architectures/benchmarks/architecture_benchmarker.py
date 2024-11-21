from abc import ABC, abstractmethod
import pandas as pd


class Architecture_Benchmarker(ABC):
    def query(
        self, test_id: int, query_id: str, query: str, iteration: int
    ) -> pd.DataFrame:
        pass

    @abstractmethod
    def bulk_query(self, test_id: int, queries: dict, iterations: int) -> pd.DataFrame:
        pass

    def load_age_environment(self):
        [
            self.query(-1, 0, query, 0)
            for query in [
                "CREATE EXTENSION IF NOT EXISTS age;",
                "CREATE EXTENSION IF NOT EXISTS postgis;",
                "LOAD 'age';",
                'SET search_path = ag_catalog, "$user", public;',
            ]
        ]
