import os
import sys
import pathlib as path

dt_benchmarker_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.path.join(".."))
)
sys.path.insert(0, dt_benchmarker_dir)

from benchmarks.dt_benchmarker import DT_Benchmarker
from architectures.postgres_age.benchmarker.age_benchmarker import AGE_Benchmarker

statistics_column = [
    "architecture",
    "test_id",
    "query_number",
    "iteration",
    "start_time",
    "end_time",
    "duration",
    "query_status",
]

conn_dict = {
    "endpoint": "137.204.70.156",
    "port": "45432",
    "user": "postgres",
    "psw": "psw",
    "db_name": "test_postgres_graphs",
}
test_id = 0
iterations = 10


def test_AGE_architecture(conn_dict: dict, statistics_columns: list):
    age_benchmarker = AGE_Benchmarker(conn_dict, statistics_columns)
    my_benchmark = DT_Benchmarker()
    return my_benchmark.benchmark_architecture(
        "./digital_twins_architectures/architectures/postgres_age/benchmarker/queries.yaml",
        test_id,
        iterations,
        age_benchmarker,
    )


test_AGE_architecture(conn_dict, statistics_column)
