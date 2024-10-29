from sqlalchemy import text
from datetime import datetime
import json
import os
import sys
import pandas as pd

connection_manager_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.path.join("..", "..", "..", ".."))
)
sys.path.insert(0, connection_manager_dir)
from connection_manager import pg_connector
from utils import utils


class Timescale_Age_Postgis_Middleware:

    def __init__(self, pg_ip, pg_port, pg_user, pg_psw, pg_db) -> None:
        self.__pg_connector = pg_connector.PG_Connector(
            pg_ip, pg_port, pg_user, pg_psw, pg_db
        )
        self.__logger = utils.setup_logger("Timescale_Age_PostGIS_Middleware")

    def __commit_transactions(self):
        return self.__pg_connector.query("COMMIT;")

    def load_age_environment(self, graph):
        try:
            self.__pg_connector.query("CREATE EXTENSION IF NOT EXISTS age;")
            self.__pg_connector.query("LOAD 'age';")
            self.__pg_connector.query('SET search_path = ag_catalog, "$user", public;')

            result = self.__pg_connector.query(
                f"SELECT COUNT(*) FROM ag_catalog.ag_graph WHERE name = '{graph}';"
            )
            # If graph don't exist
            if result[0][0] <= 0:
                self.__pg_connector.query(
                    f"SELECT * FROM ag_catalog.create_graph('{graph}');"
                )
            self.__commit_transactions()
            return True
        except Exception as e:
            self.__logger.exception(f"Something went wrong, error {e}")
            self.__logger.exception(e.__doc__)
            return False

    def check_if_edge_exists(self, graph, source_id, dest_id, edge_label):
        check_query = f"""
            SELECT EXISTS (
                SELECT * FROM cypher('{graph}', $$
                    MATCH (source {{id: '{source_id}'}})-[r:{edge_label}]->(dest {{id: '{dest_id}'}})
                    RETURN r
                $$) AS (r agtype)
            );
        """

        result = self.__pg_connector.query(check_query)
        return result[0][0]  # Return wether the edge exists

    def check_if_node_exists(self, graph, node_label, node_id):

        check_query = f"""
            SELECT * FROM cypher('{graph}', $$
                MATCH (n:{node_label})
                WHERE n.id = '{node_id}'
                RETURN n
            $$) AS (n agtype);
        """

        result = self.__pg_connector.query(check_query)
        return len(result) > 0  # Return wether the node exists

    def __format_value(self, value):
        """Restituisce la rappresentazione corretta del valore per Cypher."""
        if isinstance(value, str):
            return f"'{value}'"
        elif isinstance(value, list):
            return (
                "[" + ", ".join(map(lambda x: str(self.__format_value(x)), value)) + "]"
            )
        elif isinstance(value, dict):
            return self.__format_properties(value)
        elif isinstance(value, int) or isinstance(value, float):
            return value
        else:
            return str(value)

    def __format_properties(self, node_properties):
        props = []
        for key, value in node_properties.items():
            props.append(
                f"{key}: {self.__format_value(value)}"
            )  # Usa self.__format_value per f
        return "{" + ", ".join(props) + "}"  # Ritorna una stringa formattata

    def __is_FIWARE_id(self, property_value):
        id_regex = "urn:ngsi-ld:"
        if isinstance(property_value, int):
            return False
        elif isinstance(property_value, str):
            return id_regex in property_value
        if isinstance(property_value, list):
            return all([self.__is_FIWARE_id(prop) for prop in property_value])

    def __get_entity_edges(self, entity_dict: dict):
        return [
            key
            for key, value in entity_dict.items()
            if self.__is_FIWARE_id(value) and not key == "id"
        ]

    def __is_multidevice(self, node_properties):
        return node_properties["type"] == "Device" and "hasDevice" in node_properties

    def upload_multidevice(self, graph, node_label, node_properties):
        sub_devices = [
            sub_device
            for sub_device in node_properties["hasDevice"]
            if isinstance(sub_device, dict)
        ]
        self.insert_custom_vertex(graph, node_label, node_properties, is_multi=True)
        for sub_device in sub_devices:
            self.insert_custom_vertex(graph, sub_device["type"], sub_device)
            self.create_edges(
                graph, node_properties["id"], "hasDevice", sub_device["id"]
            )

    def insert_custom_vertex(self, graph, node_label, node_properties, is_multi=False):
        node_properties.pop("location", None)
        node_properties.pop("_id", None)
        if not self.check_if_node_exists(graph, node_label, node_properties["id"]):
            if self.__is_multidevice(node_properties) and not is_multi:
                self.upload_multidevice(graph, node_label, node_properties)
            else:
                properties_str = self.__format_properties(node_properties)
                insert_query = f"""SELECT * FROM cypher('{graph}', $$
                    CREATE (n:{node_label} {properties_str})
                    RETURN n
                    $$) AS (n agtype); """
                self.__pg_connector.query(insert_query)
                return True
        else:
            self.__logger.info("Node already in graph")
            return False

    def create_edges(self, graph, source_id, edge_label, dest_id):
        if isinstance(source_id, list):
            [
                self.create_edges(graph, source, edge_label, dest_id)
                for source in source_id
            ]
        elif isinstance(dest_id, list):
            [self.create_edges(graph, source_id, edge_label, dest) for dest in dest_id]
        else:
            if not self.check_if_edge_exists(graph, source_id, dest_id, edge_label):
                query = f"""
                    SELECT * FROM cypher('{graph}', $$
                        MATCH (source {{id: '{source_id}'}}), (dest {{id: '{dest_id}'}})
                        CREATE (source)-[r:{edge_label}]->(dest)
                        RETURN r
                    $$) AS (r agtype);
                """
                try:
                    self.__pg_connector.query(query)
                    self.__logger.info(
                        f"Successfully created edge {edge_label} from {source_id} to {dest_id}"
                    )
                    return True
                except Exception as e:
                    self.__logger.exception(
                        f"Failed to create edge from {source_id} to {dest_id}: {e}"
                    )
            else:
                self.__logger.info("Edge already existing")
                return True

    def insert_test_node(self, graph):
        self.__pg_connector.query(
            f"""SELECT * FROM cypher('{graph}', $$
            CREATE (n:test_node {{name: 'Node1', value: 123}})
            RETURN n
        $$) AS (n agtype); """
        )
        return True

    def select_all_nodes(self, graph):
        result = self.__pg_connector.query(
            f"""SELECT * FROM cypher('{graph}', $$
                MATCH (n)
                RETURN n
            $$) AS (n agtype); """
        )
        return [node for node in result]

    def update_subdevices(self, graph, node_properties):
        sub_devices = [
            sub_device
            for sub_device in node_properties["hasDevice"]
            if isinstance(sub_device, dict)
        ]
        for subdevice in sub_devices:
            self.update_node(graph, subdevice["type"], subdevice["id"], subdevice)

    def update_node(self, graph, node_label, node_id, node_properties):
        if self.__is_multidevice(node_properties):
            self.update_subdevices(graph, node_properties)
            has_device_prop = json.dumps(node_properties["hasDevice"])
            self.__pg_connector.query(
                f"""SELECT * FROM cypher('{graph}', $$
                MATCH (n:{node_label} {{id: '{node_id}'}})
                SET n.hasDevice = '{has_device_prop}'
                RETURN n
                $$) AS (n agtype); """
            )
        else:
            update_string = "SET " + ", ".join(
                [
                    (
                        f"n.{key} = '{value}'"
                        if isinstance(value, str)
                        else f"n.{key} = {value}"
                    )
                    for key, value in node_properties.items()
                ]
            )
            self.__pg_connector.query(
                f"""SELECT * FROM cypher('{graph}', $$
                MATCH (n:{node_label} {{id: '{node_id}'}})
                {update_string}
                RETURN n
                $$) AS (n agtype); """
            )
        return True

    def update_graph(self, graph, measurement):
        device_id = measurement["id"]
        device_type = measurement["type"]
        # If it's already present
        if not self.check_if_node_exists(graph, device_type, device_id):
            return self.insert_custom_vertex(graph, device_type, measurement)
        else:
            return self.update_node(graph, device_type, device_id, measurement)

    def historicize_measurement(self, hypertable, row):
        row[0] = f"to_timestamp({row[0]})"
        insert_query = f"""INSERT INTO {hypertable} VALUES ({row[0]}, {", ".join(str(self.__format_value(value)) for value in row[1:])})"""
        self.__pg_connector.query(insert_query)
        return True

    def upload_measurement(self, graph, hypertable, measurement):
        device_id = measurement["id"]
        measurement.pop("location", None)
        timestamp = datetime.fromisoformat(measurement["dateObserved"]).timestamp()

        if self.update_graph(graph, measurement):
            if self.__is_multidevice(measurement):
                sub_devices = [
                    sub_device
                    for sub_device in measurement["hasDevice"]
                    if isinstance(sub_device, dict)
                ]
                for subdevice in sub_devices:
                    if "dateObserved" not in subdevice:
                        subdevice["dateObserved"] = measurement["dateObserved"]
                    self.upload_measurement(graph, hypertable, subdevice)
            else:
                for property, value in zip(
                    measurement["controlledProperty"], measurement["value"]
                ):
                    if not self.historicize_measurement(
                        hypertable, [timestamp, device_id, property, value]
                    ):
                        return False
                return True
        return False

    def update_edges(graph_name, edges):
        return True

    def process_entity(self, entity, graph_name, measurement_table):
        edges = [
            [entity["id"], edge, dest_node]
            for edge in self.__get_entity_edges(entity)
            if (dest_node := entity.copy().pop(edge, None)) is not None
        ]
        entity_edges = pd.DataFrame(
            edges, columns=["source_id", "edge_label", "dest_id"]
        )
        entity_edges = entity_edges[
            ~entity_edges["dest_id"].apply(utils.is_dict_or_list_of_dicts)
        ]
        # If node does not exist, add to graph
        if self.update_graph(graph_name, entity):
            for _, edge in edges.iterrows():
                self.create_edges(
                    graph_name,
                    edge["source_id"],
                    edge["edge_label"],
                    edge["dest_id"],
                )
        else:
            # Else, this entity is an update!
            self.upload_measurement(graph_name, measurement_table, entity)
            self.update_edges(graph_name, edges)
