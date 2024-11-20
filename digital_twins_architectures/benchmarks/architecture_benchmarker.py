from abc import ABC, abstractmethod
import pandas as pd


class Architecture_Benchmarker(ABC):
    def query(self, query) -> pd.DataFrame:
        pass

    @abstractmethod
    def bulk_query(self, test_id: int, queries: dict, iterations: int) -> pd.DataFrame:
        pass
