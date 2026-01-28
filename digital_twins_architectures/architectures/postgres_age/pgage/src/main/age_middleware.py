from sqlalchemy import text
import pandas as pd
from shapely.geometry import shape
from shapely import wkt, geometry
import logging
import pg_connector
import utils


ENABLE_LOGS = False


class ConditionalFilter(logging.Filter):
    def filter(self, record):
        return ENABLE_LOGS  # True per loggare, False per ignorare


class Timescale_Age_Postgis_Middleware:

    def __init__(self, pg_ip, pg_port, pg_user, pg_psw, pg_db) -> None:
        self.__pg_connector = pg_connector.PG_Connector(
            pg_ip, pg_port, pg_user, pg_psw, pg_db
        )
        self.__logger = utils.setup_logger("Timescale_Age_PostGIS_Middleware")
        self.__logger.addFilter(ConditionalFilter())

    def query(
        self,
        query_text,
        evaluating: bool = False,
    ) -> list:
        return self.__pg_connector.query(query_text, evaluating=evaluating)

    def __convert_to_seconds(self, timestamp):

        if len(str(int(timestamp))) > 10:
            return timestamp / 1000
        return float(timestamp)

    def __commit_transactions(self):

        return self.__pg_connector.query("COMMIT;")

    def delete_graph(self, graph) -> bool:
        try:
            self.__pg_connector.query(
                f"SELECT * FROM ag_catalog.drop_graph('{graph}', true);"
            )
            self.__commit_transactions()
            return True
        except Exception as e:
            self.__logger.exception(f"Something went wrong, error {e}")
            self.__logger.exception(e.__doc__)
            return False

    def clear_timeseries_storage(self, hypertable) -> bool:
        try:
            return self.__pg_connector.query(f"TRUNCATE TABLE {hypertable};")
        except Exception as e:
            self.__logger.exception(f"Something went wrong, error {e}")
            self.__logger.exception(e.__doc__)
            return False

    def load_age_environment(self, graph) -> bool:
        try:
            self.__pg_connector.query("CREATE EXTENSION IF NOT EXISTS age;")
            self.__pg_connector.query("CREATE EXTENSION IF NOT EXISTS postgis;")
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

    def check_if_edge_exists(self, graph, source_id, dest_id, edge_label) -> bool:
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

    def check_if_node_exists(self, graph, node_label, node_id) -> bool:
        label_filter = f":{node_label}" if node_label is not None else ""

        check_query = f"""
            SELECT * FROM cypher('{graph}', $$
                MATCH (n{label_filter})
                WHERE n.id = '{node_id}'
                RETURN n
            $$) AS (n agtype);
        """

        result = self.__pg_connector.query(check_query)
        return len(result) > 0  # Return wether the node exists

    def __format_value(self, value) -> str:
        if isinstance(value, str):
            if value == "NULL":
                return value
            return f"'{value}'"
        elif isinstance(value, list):
            return (
                "[" + ", ".join(map(lambda x: str(self.__format_value(x)), value)) + "]"
            )
        elif isinstance(value, dict):
            if "type" in value and "coordinates" in value:
                return self.__wkt_to_geom(value)
            else:
                return self.__format_properties(value)
        elif isinstance(value, int) or isinstance(value, float):
            return value
        else:
            return str(value)

    def __wkt_to_geom(self, location) -> str:
        return f"st_geomfromtext('{self.__json_to_wkt(location)}')"

    def __format_properties(self, node_properties) -> str:
        props = []
        for key, value in node_properties.items():
            if key == "location":
                props.append(f"""{key}: '{self.__json_to_wkt(value)}'""")
            else:
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
            for key, _ in entity_dict.items()
            if key != "id"
            and (isinstance(entity_dict[key], dict) and "id" in entity_dict[key])
            or (
                isinstance(entity_dict[key], list)
                and any(
                    [
                        isinstance(item, dict) and "id" in item
                        for item in entity_dict[key]
                    ]
                )
            )
        ]

    def __is_multidevice(self, node_properties):
        return node_properties["type"] == "Device" and "hasDevice" in node_properties

    def __extract_edges(self, entity):
        edges = []

        for edge in self.__get_entity_edges(entity):
            dest = entity.get(edge)

            if dest is None:
                continue

            edge_label = f"has{edge.capitalize()}"
            source_id = entity["id"]

            # Caso 1: singolo ID
            if isinstance(dest, (int, str)):
                edges.append([source_id, edge_label, dest])

            # Caso 2: dict singolo
            elif isinstance(dest, dict):
                if "id" in dest:
                    edges.append([source_id, edge_label, dest["id"]])

            # Caso 3: lista di dict
            elif isinstance(dest, list):
                for d in dest:
                    if isinstance(d, dict) and "id" in d:
                        edges.append([source_id, edge_label, d["id"]])

        return pd.DataFrame(edges, columns=["source_id", "edge_label", "dest_id"])

    def __json_to_wkt(self, data):
        if isinstance(data, str):
            try:
                # prova a parsare come WKT
                return wkt.loads(data).wkt
            except Exception as e:
                raise ValueError(f"Cannot parse WKT: {data}, error = {e}")
        elif isinstance(data, dict):
            try:
                return geometry.shape(data).wkt
            except Exception as e:
                raise ValueError(
                    f"Unsupported geometry type: {data.get('type')}, error = {e}"
                )
        else:
            raise TypeError(f"Unsupported geometry input type: {type(data)}")

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
        if self.__is_multidevice(node_properties) and not is_multi:
            self.upload_multidevice(graph, node_label, node_properties)
        else:
            properties_str = self.__format_properties(node_properties)
            insert_query = f"""SELECT * FROM cypher('{graph}', $$
                CREATE (n:{node_label} {properties_str})
                RETURN n
                $$) AS (n agtype); """
            result = self.__pg_connector.query(insert_query)
            if result:
                self.__logger.info(f"Node {node_properties['id']} successfully created")
            else:
                self.__logger.error(f"Could insert node {node_properties['id']}")

            edges = self.__extract_edges(node_properties).itertuples(
                index=False, name=None
            )

            return all(
                [
                    (
                        self.create_edges(graph, source, edge_label, dest)
                        if edge_label != "hasSensor"
                        else self.create_edges(graph, dest, "hasTemperature", source)
                    )
                    for (source, edge_label, dest) in edges
                ]
            )

    def create_edges(self, graph, source_id, edge_label, dest_id):
        creation_result = True
        if isinstance(source_id, list):
            creation_result = all(
                [
                    self.create_edges(graph, source, edge_label, dest_id)
                    for source in source_id
                ]
            )
        elif isinstance(dest_id, list):
            creation_result = creation_result and all(
                [
                    self.create_edges(graph, source_id, edge_label, dest)
                    for dest in dest_id
                ]
            )
        else:
            if not self.check_if_node_exists(
                graph, None, source_id
            ) or not self.check_if_node_exists(graph, None, dest_id):
                self.__logger.error(
                    f"Failed to create edge from {source_id} to {dest_id}, some/all nodes do not exist"
                )
                creation_result = False
            elif not self.check_if_edge_exists(graph, source_id, dest_id, edge_label):
                query = f"""
                    SELECT * FROM cypher('{graph}', $$
                        MATCH (source {{id: '{source_id}'}}), (dest {{id: '{dest_id}'}})
                        CREATE (source)-[r:{edge_label}]->(dest)
                        RETURN r
                    $$) AS (r agtype);
                """
                try:
                    creation_result = len(self.__pg_connector.query(query)) > 0
                    (
                        self.__logger.info(
                            f"Successfully created edge {edge_label} from {source_id} to {dest_id}"
                        )
                        if creation_result
                        else self.__logger.warning(
                            f"Failed to create edge from {source_id} to {dest_id}"
                        )
                    )
                    return creation_result
                except Exception as e:
                    self.__logger.exception(
                        f"Failed to create edge from {source_id} to {dest_id}: {e}"
                    )
                    creation_result = False
            else:
                self.__logger.info(
                    f"Edge already existing between {source_id}-[{edge_label}]->{dest_id}"
                )
                creation_result = True
            return creation_result

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
        # if self.__is_multidevice(node_properties):
        #     self.update_subdevices(graph, node_properties)
        #     has_device_prop = json.dumps(node_properties["hasDevice"])
        #     self.__pg_connector.query(
        #         f"""SELECT * FROM cypher('{graph}', $$
        #         MATCH (n:{node_label} {{id: '{node_id}'}})
        #         SET n.hasDevice = '{has_device_prop}'
        #         RETURN n
        #         $$) AS (n agtype); """
        #     )
        # else:
        #     update_string = "SET " + ", ".join(
        #         [
        #             (
        #                 f"n.{key} = '{value}'"
        #                 if isinstance(value, str)
        #                 else (
        #                     f"n.{key} = '{self.__json_to_wkt(value)}'"
        #                     if key == "location"
        #                     else (
        #                         f"n.{key} = '{json.dumps(value)}'"
        #                         if isinstance(value, dict)
        #                         else f"n.{key} = {value}"
        #                     )
        #                 )
        #             )
        #             for key, value in node_properties.items()
        #         ]
        #     )
        #     result = self.__pg_connector.query(
        #         f"""SELECT * FROM cypher('{graph}', $$
        #         MATCH (n:{node_label} {{id: '{node_id}'}})
        #         {update_string}
        #         RETURN n
        #         $$) AS (n agtype); """
        #     )
        #     if len(result) > 0:
        #         self.__logger.info(f"Updated node {node_properties['id']}")
        return self.update_edges(graph, self.__extract_edges(node_properties))

    def update_edges(self, graph_name, edges):
        new_edges = [
            self.create_edges(
                graph_name, row["source_id"], row["edge_label"], row["dest_id"]
            )
            for _, row in edges.iterrows()
        ]
        return all(new_edges)

    def update_graph(self, graph, measurement):
        device_id = measurement["id"]
        device_type = measurement["type"]
        # If it's already present
        if not self.check_if_node_exists(graph, device_type, device_id):
            return self.insert_custom_vertex(graph, device_type, measurement)
        else:
            # return True
            self.update_node(graph, device_type, device_id, measurement)

    def process_timeseries_batch(
        self,
        batch_df: pd.DataFrame,
        table_name: str,
    ):
        self.__pg_connector.insert_dataframe_batch(
            batch_df,
            table_name,
            page_size=20_000,
        )

    def historicize_measurement(self, hypertable, row):
        row[0] = f"to_timestamp({self.__convert_to_seconds(row[0])})"
        insert_query = f"""INSERT INTO {hypertable} VALUES ({row[0]}, {", ".join(str(self.__format_value(value)) for value in row[1:])})"""
        try:
            self.__pg_connector.query(insert_query)
            return True
        except Exception as e:
            self.__logger.exception(f"Something went wrong!! { e}")
            return True

    def upload_measurement(self, hypertable, measurements: pd.DataFrame):
        return all(
            [
                self.historicize_measurement(
                    hypertable,
                    [
                        row["timestamp"],
                        row["device_id"],
                        row["controlledProperty"],
                        row["location"],
                        (
                            row["value"]
                            if isinstance(row["value"], (int, float))
                            else "NULL"
                        ),
                        str(row["value"]),
                    ],
                )
                for _, row in measurements.iterrows()
            ]
        )

    def process_entity(
        self,
        entity,
        graph_name,
        measurement_table,
        measurement_schema=None,
        extract_measurement_func=None,
        isUpdate=False,
    ):
        entity.pop("_id", None)
        if isUpdate:
            if self.update_graph(graph_name, entity):
                if extract_measurement_func:
                    if self.__is_multidevice(entity):
                        sub_devices = [
                            sub_device
                            for sub_device in entity["hasDevice"]
                            if isinstance(sub_device, dict)
                        ]
                        for subdevice in sub_devices:
                            if "dateObserved" not in subdevice:
                                subdevice["dateObserved"] = entity["dateObserved"]
                            self.upload_measurement(
                                measurement_table,
                                extract_measurement_func(entity, measurement_schema),
                            )

                    else:
                        return self.upload_measurement(
                            measurement_table,
                            extract_measurement_func(entity, measurement_schema),
                        )
        else:
            if extract_measurement_func:
                return self.upload_measurement(
                    measurement_table,
                    extract_measurement_func(entity, measurement_schema),
                )
            else:
                return self.insert_custom_vertex(graph_name, entity["type"], entity)
