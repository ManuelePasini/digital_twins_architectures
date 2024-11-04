CREATE EXTENSION IF NOT EXISTS age;
CREATE EXTENSION IF NOT EXISTS postgis;
LOAD 'age';

SET search_path = ag_catalog, "$user", public;

SELECT postgis_full_version();

SELECT * 
FROM cypher('watering_adf_graph', $$
	MATCH (v:test_node)
	DELETE v
$$) as (v agtype);

SELECT * 
FROM cypher('watering_adf_graph', $$
	MATCH (v)
	DETACH DELETE v
$$) as (v agtype);

SELECT * FROM ag_catalog.drop_graph('watering_adf_graph', cascade := true);

CREATE TABLE Measurements(
	timestamp timestamp NOT NULL,
	device_id text NOT NULL,
	controlledProperty text NOT NULL,
	location geometry,
	value float NOT NULL
)

SELECT create_hypertable('Measurements', 'timestamp');
ALTER TABLE measurements ADD PRIMARY KEY ("timestamp","device_id", "controlledproperty")

SELECT  *  from measurements where controlledproperty = 'speed'
where timestamp = (select max(timestamp) from measurements where controlledproperty <> 'speed' )

SELECT  *  from measurements
where controlledproperty = 'speed'
order by timestamp desc 
and timestamp = (select min(timestamp) from measurements where controlledproperty <> 'speed' )


INSERT INTO ag_catalog.measurements VALUES (to_timestamp(1717541105.0), 'urn:ngsi-ld:Device:unibo:f7b82d1d75e79188f5efc73c7a6d34f6', 'wind_gust_max', ST_GeomFromGeoJSON('{"type": "Point", "coordinates": [11.798998, 44.235024]}'), 0)

SELECT * FROM cypher('watering_adf_graph', $$
    MATCH (n)
    WHERE n.id = 'urn:ngsi-ld:Device:unibo:ace4b1adb69da4c71c3e02e6509e859e'
    DETACH DELETE n
$$) AS (n agtype);


SELECT * 
FROM cypher('watering_adf_graph', $$
    MATCH (n:Device) 
    RETURN n.location.coordinates[0]
$$) AS (n agtype);


create table spatial_measurements (
timestamp timestamp DEFAULT CURRENT_TIMESTAMP,
device_id text,
controlled_property text,
location geometry,
value float
);

CREATE INDEX geom_index
  ON spatial_measurements
  USING GIST (location);

SELECT count(*) FROM measurements

SELECT * 
FROM measurements AS s1
WHERE ST_Within(
    s1.location,
    (SELECT st_geomfromtext(location)
     FROM cypher('watering_adf_graph', $$
         MATCH (n:AgriParcel)
         WHERE n.name = 'Fondo Errano 2024 T0'
         RETURN n.location
     $$) AS (location text))
)

SELECT * FROM cypher('watering_adf_graph', $$
                CREATE (n:Device {id: 'urn:ngsi-ld:Device:unibo:a316ef4f55a925842cca39af7280f4d8',
				type: 'Device',
				belongsTo: 'urn:ngsi-ld:AgriParcel:unibo:647c399b2188ff484f7416389f94885c',
				controlledProperty: ['dripper'],
				dateCreated: '2024-10-17T07:00:02',
				dateObserved: '2024-10-15T12:45:09',
				deviceCategory: ['sensor'],
				domain: 'unibo',
				location: st_geomfromtext('{"type": "Point", "coordinates": [11.798998, 44.235024]}'),
				name: 'Dripper Fondo Errano 2024 T0 T0',
				namespace: 'unibo.watering.',
				unixtimestampCreated: 1729141203,
				unixtimestampModified: 1728989109,
				value: [0]})
                RETURN n
                $$) AS (ne agtype); 

INSERT INTO ag_catalog.measurements VALUES (to_timestamp(1728989109.0), 'urn:ngsi-ld:Device:unibo:a316ef4f55a925842cca39af7280f4d8', 'dripper', st_geomfromtext('POINT(11.798998 44.235024)'), 0)

