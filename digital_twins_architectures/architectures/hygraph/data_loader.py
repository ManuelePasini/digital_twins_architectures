from hygraph_core import HyGraph, HyGraphQuery
import pandas as pd

      # Initialize HyGraph
    hygraph = HyGraph()

    # Sample data for nodes and edges
    # Creating nodes
    node1 = hygraph.add_pgnode(oid=1, label="Node1", start_time=pd.to_datetime("2023-01-01"))
    node2 = hygraph.add_pgnode(oid=2, label="Node2", start_time=pd.to_datetime("2023-01-01"))

    # Adding static properties to nodes
    node1.add_static_property("description", "This is node 1", hygraph)
    node2.add_static_property("description", "This is node 2", hygraph)

    # Create an edge with static and dynamic properties
    edge = hygraph.add_pgedge(
        oid=10,
        source=node1.getId(),
        target=node2.getId(),
        label="Edge1",
        start_time=pd.to_datetime("2023-01-01"),
        properties={"weight": 5}
    )
    # Define timestamps and values
    timestamps = pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"])
    values = [[1], [3], [5]]

    # Create the time series
    metadata = TimeSeriesMetadata(owner_id=edge.getId(), element_type='edge')  # or whatever the correct metadata is
    time_series = TimeSeries(tsid='traffic_series', timestamps=timestamps, variables=['traffic'], data=values,
                             metadata=metadata)
    # Add a dynamic property to the edge (if supported in your implementation)
    edge.add_temporal_property("traffic", time_series, hygraph)

    # Query example: retrieve all edges between `Node1` and `Node2`
    query = HyGraphQuery(hygraph) \
        .match_node(alias='node1', node_id=node1.getId()) \
        .match_edge(alias='edge') \
        .match_node(alias='node2', node_id=node2.getId()) \
        .connect('node1', 'edge', 'node2') \
        .return_(edge=lambda result: result['edge'])

    # Execute query and print results
    edges = query.execute()
    print("Edges between Node1 and Node2:", edges)

    # Display nodes, edges, and properties
    print("Nodes and their properties:")
    for node_id, data in hygraph.graph.nodes(data=True):
        print(f"Node ID: {node_id}, Data: {data}")

    print("\nEdges and their properties:")
    for u, v, data in hygraph.graph.edges(data=True):
        print(f"Edge from {u} to {v}, Data: {data}")