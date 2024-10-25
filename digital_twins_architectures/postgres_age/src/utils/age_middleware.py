from sqlalchemy import text
from datetime import datetime
import json


def commit_transactions(conn):
    return conn.execute(text("COMMIT;"))


def load_age_environment(conn, graph):
    try:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS age;"))
        conn.execute(text("LOAD 'age';"))
        conn.execute(text('SET search_path = ag_catalog, "$user", public;'))

        check_query = (
            f"SELECT COUNT(*) FROM ag_catalog.ag_graph WHERE name = '{graph}';"
        )
        result = conn.execute(text(check_query)).fetchone()
        # If graph don't exist
        if result[0] <= 0:
            crete_graph_query = f"SELECT * FROM ag_catalog.create_graph('{graph}');"
            conn.execute(text(crete_graph_query))
        commit_transactions(conn)
        return True
    except Exception as e:
        print(f"Something went wrong, error {e}")
        print(e.__doc__)
        return False


def check_if_edge_exists(conn, graph, source_id, dest_id, edge_label):
    check_query = f"""
        SELECT EXISTS (
            SELECT * FROM cypher('{graph}', $$
                MATCH (source {{id: '{source_id}'}})-[r:{edge_label}]->(dest {{id: '{dest_id}'}})
                RETURN r
            $$) AS (r agtype)
        );
    """

    result = conn.execute(text(check_query)).fetchone()
    return result[0]  # Return wether the edge exists


def check_if_node_exists(conn, graph, node_label, node_id):

    check_query = f"""
        SELECT * FROM cypher('{graph}', $$
            MATCH (n:{node_label})
            WHERE n.id = '{node_id}'
            RETURN n
        $$) AS (n agtype);
    """

    result = conn.execute(text(check_query)).fetchall()
    return len(result) > 0  # Return wether the node exists


def format_value(value):
    """Restituisce la rappresentazione corretta del valore per Cypher."""
    if isinstance(value, str):
        return f"'{value}'"
    elif isinstance(value, list):
        return "[" + ", ".join(map(lambda x: str(format_value(x)), value)) + "]"
    elif isinstance(value, dict):
        return format_properties(value)
    elif isinstance(value, int) or isinstance(value, float):
        return value
    else:
        return str(value)


def format_properties(node_properties):
    props = []
    for key, value in node_properties.items():
        props.append(f"{key}: {format_value(value)}")  # Usa format_value per f
    return "{" + ", ".join(props) + "}"  # Ritorna una stringa formattata


def is_multidevice(node_properties):
    return node_properties["type"] == "Device" and "hasDevice" in node_properties
    # return any(
    #     [isinstance(measurement, dict) for measurement in node_properties["value"]]
    # )


def upload_multidevice(conn, graph, node_label, node_properties):
    sub_devices = [
        sub_device
        for sub_device in node_properties["hasDevice"]
        if isinstance(sub_device, dict)
    ]
    insert_custom_vertex(conn, graph, node_label, node_properties, is_multi=True)
    for sub_device in sub_devices:
        insert_custom_vertex(conn, graph, sub_device["type"], sub_device)
        create_edges(conn, graph, node_properties["id"], "hasDevice", sub_device["id"])


def insert_custom_vertex(conn, graph, node_label, node_properties, is_multi=False):
    node_properties.pop("location", None)
    if not check_if_node_exists(conn, graph, node_label, node_properties["id"]):
        if is_multidevice(node_properties) and not is_multi:
            upload_multidevice(conn, graph, node_label, node_properties)
        else:
            properties_str = format_properties(node_properties)
            insert_query = f"""SELECT * FROM cypher('{graph}', $$
                CREATE (n:{node_label} {properties_str})
                RETURN n
                $$) AS (n agtype); """
            conn.execute(text(insert_query))
            return commit_transactions(conn)
    else:
        return False


def create_edges(conn, graph, source_id, edge_label, dest_id):
    if isinstance(source_id, list):
        [create_edges(conn, graph, source, edge_label, dest_id) for source in source_id]
    elif isinstance(dest_id, list):
        [create_edges(conn, graph, source_id, edge_label, dest) for dest in dest_id]
    else:
        if not check_if_edge_exists(conn, graph, source_id, dest_id, edge_label):
            query = f"""
                SELECT * FROM cypher('{graph}', $$
                    MATCH (source {{id: '{source_id}'}}), (dest {{id: '{dest_id}'}})
                    CREATE (source)-[r:{edge_label}]->(dest)
                    RETURN r
                $$) AS (r agtype);
            """

            try:
                conn.execute(text(query))
                print(
                    f"Successfully created edge {edge_label} from {source_id} to {dest_id}"
                )
                return commit_transactions(conn)
            except Exception as e:
                print(f"Failed to create edge from {source_id} to {dest_id}: {e}")
        else:
            print("Edge already existing")
            return True


def insert_test_node(conn, graph):
    conn.execute(
        text(
            f"""SELECT * FROM cypher('{graph}', $$
        CREATE (n:test_node {{name: 'Node1', value: 123}})
        RETURN n
    $$) AS (n agtype); """
        )
    )
    return commit_transactions(conn)


def select_all_nodes(conn, graph):
    result = conn.execute(
        text(
            f"""SELECT * FROM cypher('{graph}', $$
            MATCH (n)
            RETURN n
        $$) AS (n agtype); """
        )
    )
    commit_transactions(conn)
    print("Fetching results...")
    return [node for node in result]


def update_subdevices(conn, graph, node_properties):
    sub_devices = [
        sub_device
        for sub_device in node_properties["hasDevice"]
        if isinstance(sub_device, dict)
    ]
    for subdevice in sub_devices:
        update_node(conn, graph, subdevice["type"], subdevice["id"], subdevice)


def update_node(conn, graph, node_label, node_id, node_properties):
    if is_multidevice(node_properties):
        update_subdevices(conn, graph, node_properties)
        has_device_prop = json.dumps(node_properties["hasDevice"])
        conn.execute(
            text(
                f"""SELECT * FROM cypher('{graph}', $$
            MATCH (n:{node_label} {{id: '{node_id}'}})
            SET n.hasDevice = '{has_device_prop}'
            RETURN n
            $$) AS (n agtype); """
            )
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
        conn.execute(
            text(
                f"""SELECT * FROM cypher('{graph}', $$
            MATCH (n:{node_label} {{id: '{node_id}'}})
            {update_string}
            RETURN n
            $$) AS (n agtype); """
            )
        )
    return commit_transactions(conn)


def update_graph(conn, graph, measurement):
    device_id = measurement["id"]
    device_type = measurement["type"]
    # If it's already present
    if not check_if_node_exists(conn, graph, device_type, device_id):
        return insert_custom_vertex(conn, graph, device_type, measurement)
    else:
        return update_node(conn, graph, device_type, device_id, measurement)


def historicize_measurement(conn, hypertable, row):
    row[0] = f"to_timestamp({row[0]})"
    insert_query = f"""INSERT INTO {hypertable} VALUES ({row[0]}, {", ".join(str(format_value(value)) for value in row[1:])})"""
    conn.execute(text(insert_query))
    return commit_transactions(conn)


def upload_measurement(conn, graph, hypertable, measurement):
    device_id = measurement["id"]
    measurement.pop("location", None)
    timestamp = datetime.fromisoformat(measurement["dateObserved"]).timestamp()

    if update_graph(conn, graph, measurement):
        if is_multidevice(measurement):
            sub_devices = [
                sub_device
                for sub_device in measurement["hasDevice"]
                if isinstance(sub_device, dict)
            ]
            for subdevice in sub_devices:
                if "dateObserved" not in subdevice:
                    subdevice["dateObserved"] = measurement["dateObserved"]
                upload_measurement(conn, graph, hypertable, subdevice)
        else:
            for property, value in zip(
                measurement["controlledProperty"], measurement["value"]
            ):
                if not historicize_measurement(
                    conn, hypertable, [timestamp, device_id, property, value]
                ):
                    return False
            return commit_transactions(conn)
    return False
