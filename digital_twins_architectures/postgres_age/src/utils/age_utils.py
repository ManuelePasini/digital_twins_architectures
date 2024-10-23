from sqlalchemy import text
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
        return f"'{value}'"  # Aggiungi apici attorno a stringhe
    elif isinstance(value, list):
        # Gestisci le liste, formattandole in modo appropriato
        return "[" + ", ".join(map(format_value, value)) + "]"
    elif isinstance(value, dict):
        # Gestisci i dizionari annidati
        return format_properties(
            value
        )  # Chiama la funzione di formattazione per le proprietà
    else:
        return str(value)  # Per numeri o booleani, restituisci semplicemente la stringa


def format_properties(node_properties):
    """Formatta le proprietà in una stringa per Cypher."""
    props = []
    for key, value in node_properties.items():
        props.append(f"{key}: {format_value(value)}")  # Usa format_value per f
    return "{" + ", ".join(props) + "}"  # Ritorna una stringa formattata


def insert_custom_vertex(conn, graph, node_label, node_properties):
    node_properties.pop("location", None)
    if not check_if_node_exists(conn, graph, node_label, node_properties["id"]):
        properties_str = format_properties(node_properties)

        insert_query = f"""SELECT * FROM cypher('{graph}', $$
            CREATE (n:{node_label} {properties_str})
            RETURN n
            $$) AS (n agtype); """
        conn.execute(text(insert_query))
    return commit_transactions(conn)


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
