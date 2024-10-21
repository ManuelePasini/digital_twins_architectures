from sqlalchemy import create_engine, text
from sqlalchemy import create_engine, text
import dotenv
import os
import sys
import unittest


def commit_transactions(conn):
    return conn.execute(text("COMMIT;"))


def load_postgres_extensions(conn, graph):
    try:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS age;"))
        conn.execute(text("LOAD 'age';"))
        conn.execute(text('SET search_path = ag_catalog, "$user", public;'))

        check_query = (
            f"SELECT COUNT(*) FROM ag_catalog.ag_graph WHERE name = '{graph}';"
        )
        result = conn.execute(text(check_query)).fetchone()
        if result is not None:
            return True
        crete_graph_query = f"SELECT * FROM ag_catalog.create_graph('{graph}');"
        conn.execute(text(crete_graph_query))
        commit_transactions(conn)
        return True
    except Exception as e:
        print(f"Something went wrong, error {e}")
        print(e.__doc__)
        return False


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
