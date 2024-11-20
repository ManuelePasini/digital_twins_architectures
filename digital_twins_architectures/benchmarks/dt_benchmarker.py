from benchmarks.architecture_benchmarker import Architecture_Benchmarker
import os
import sys
import yaml

utils_dir = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        os.path.join("..", "utils"),
    )
)
sys.path.insert(0, utils_dir)

from utils import setup_logger


class DT_Benchmarker:

    def __init__(self) -> None:
        self.logger = setup_logger("Architecture_Benchmarker")

    def load_queries(self, path: str):
        with open(path, "r") as file:
            yaml_queries = yaml.safe_load(file)
            self.queries = {
                query_id: query_data["query"]
                for query_id, query_data in yaml_queries["queries"].items()
            }
        return self.queries

    def build_output_directory(self, parent_path: str):
        os.makedirs(os.path.join(parent_path, "output"), exist_ok=True)
        self.logger.info("Successfully built output directory")
        return os.path.join(parent_path, "output")

    def benchmark_architecture(
        self,
        queries_path: str,
        test_id: int,
        iterations: int,
        benchmarker: Architecture_Benchmarker,
    ):
        [
            benchmarker.query(-1, 0, query, 0)
            for query in [
                "CREATE EXTENSION IF NOT EXISTS age;",
                "CREATE EXTENSION IF NOT EXISTS postgis;",
                "LOAD 'age';",
                'SET search_path = ag_catalog, "$user", public;',
            ]
        ]

        queries_dict = self.load_queries(queries_path)
        output_path = self.build_output_directory(os.path.dirname(queries_path))
        statistics = benchmarker.bulk_query(test_id, queries_dict, iterations)
        statistics.to_csv(output_path)
        return statistics
