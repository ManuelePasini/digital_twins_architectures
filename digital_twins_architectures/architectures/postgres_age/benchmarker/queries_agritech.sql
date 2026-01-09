-- Queries to get entities of Agritech graph
-- Example: Get all entities with namespace starting with 'unibo.'
SELECT * FROM cypher('agri_graph', $$ MATCH (n) WHERE n.namespace STARTS WITH 'unibo.' RETURN n $$) AS (n agtype);

SELECT * FROM cypher('agri_graph', $$ MATCH (n) WHERE n.id = id RETURN n $$) AS (n agtype);

-- Group the nodes by their namespace and type, and collect their ids into a list
SELECT * FROM cypher('agri_graph', $$ MATCH (d) RETURN d.namespace AS namespace, d.type AS type, collect(d.id) as ids $$) AS (namespace agtype, type agtype, ids agtype);