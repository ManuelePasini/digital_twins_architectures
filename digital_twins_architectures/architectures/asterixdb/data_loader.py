import requests
import json
import os
import sys
import dotenv
import pandas as pd
import re

connection_manager_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.path.join("..", ".."))
)
sys.path.insert(0, connection_manager_dir)

from connection_manager import mongodb_connector
from utils import utils

logger = utils.setup_logger("AsterixDB_Data_Loader")

if not dotenv.load_dotenv("digital_twins_architectures/architectures/asterixdb/.env"):
    logger.exception("Something went wrong while finding .env")
    sys.exit(1)

# Configurazione AsterixDB
DATASET_NAME = os.getenv("DATASET_NAME")
DATAVERSE = os.getenv("DATAVERSE")

# CONFIGURAZIONE
ASTERIXDB_HOST = f"http://{os.getenv('ASTERIXDB_IP')}:{os.getenv('ASTERIX_PORT')}"  # Cambia con l'host del tuo cluster
DATASET_NAME = os.getenv("DATASET_NAME")  # Nome del dataset in AsterixDB
# Load Agritech connection parameters
AGRITECH_IP = os.getenv("AGRITECH_IP")
AGRITECH_PORT = os.getenv("AGRITECH_PORT")
AGRITECH_DB_NAME = os.getenv("AGRITECH_DB_NAME")
AGRITECH_TASK_COLLECTION = os.getenv("AGRITECH_TASK_COLLECTION")


def parse_geometry(geometry):
    """
    Converts a spatial geometry (Point, Polygon, Circle, Line) into the WKT-like format required by AsterixDB.

    Args:
    geometry (dict): A dictionary containing a 'type' and 'coordinates'.

    Returns:
    str: A string formatted for AsterixDB.
    """
    if "type" not in geometry or "coordinates" not in geometry:
        raise ValueError(
            "The dictionary must contain the keys 'type' and 'coordinates'."
        )

    geom_type = geometry["type"].lower()
    coords = geometry["coordinates"]

    if geom_type == "point":
        if len(coords) != 2:
            raise ValueError(
                "A point must have exactly 2 coordinates (longitude, latitude)."
            )
        return f'point("{coords[0]},{coords[1]}")'

    elif geom_type == "polygon":
        if len(coords) < 3:
            raise ValueError("A polygon must have at least 3 points.")
        coord_str = " ".join(f"{x},{y}" for x, y in coords)
        return f'polygon("{coord_str}")'

    elif geom_type == "circle":
        if len(coords) != 3:
            raise ValueError(
                "A circle must have 3 values: longitude, latitude, radius."
            )
        return f'circle("{coords[0]},{coords[1]} {coords[2]}")'

    elif geom_type == "line":
        if len(coords) < 2:
            raise ValueError("A line must have at least 2 points.")
        coord_str = " ".join(f"{x},{y}" for x, y in coords)
        return f'line("{coord_str}")'

    else:
        raise ValueError(f"Geometry type '{geom_type}' is not supported.")


def remove_surrounding_geometry_chars(s: str) -> str:
    """
    Cerca la prima occorrenza di una funzione geometrica (point, polygon, circle, line)
    e rimuove il carattere immediatamente precedente alla sottostringa della geometria
    e il carattere immediatamente successivo, se presenti.

    Per esempio, dato:
      'apoint("23,12")'
    rimuoverà il carattere all'indice 0 (la 'a') e il carattere all'indice match.end()
    (se presente), restituendo:
      'point("23,12")'

    Args:
        s (str): La stringa di input.

    Returns:
        str: La stringa con il carattere a (match.start()-1) e (match.end()) rimosso.
    """
    # Pattern per trovare una geometria: punto, poligono, cerchio, o linea
    pattern = r"(point|polygon|circle|line)\([^)]*\)"

    # Trova tutte le occorrenze della geometria
    matches = list(re.finditer(pattern, s, re.IGNORECASE))

    if not matches:
        # Se non viene trovato niente, restituisce la stringa invariata.
        return s

    # Itera su tutte le occorrenze trovate e modifica la stringa
    new_s = s
    for match in matches:
        start = match.start()
        end = match.end()

        # Prepara gli indici da rimuovere:
        # Rimuoviamo il carattere immediatamente precedente al match (se esiste)
        # e il carattere immediatamente successivo al match (se esiste).
        indices_to_remove = []
        if start - 1 >= 0:
            indices_to_remove.append(start - 1)
        if end < len(s):
            indices_to_remove.append(end)

        # Rimuoviamo i caratteri da rimuovere in ordine decrescente per non alterare le posizioni
        for idx in sorted(indices_to_remove, reverse=True):
            new_s = new_s[:idx] + new_s[idx + 1 :]

    return new_s


def custom_json_dumps(data):
    """
    Custom function to serialize the JSON data without escaping the quotes
    around the geometries like "point(...)". It also converts the 'timestamp'
    to a datetime format without enclosing quotes.

    Args:
        data (dict): The data to serialize.

    Returns:
        str: The serialized string.
    """
    serialized_data = json.dumps(data, separators=(",", ":"))

    # Troviamo e modifichiamo solo il campo "timestamp"
    timestamp_pattern = r'"timestamp":"(.*?)"'
    match = re.search(timestamp_pattern, serialized_data)

    if match:
        timestamp_value = match.group(1)
        # Sostituiamo il campo 'timestamp' con il formato richiesto
        serialized_data = serialized_data.replace(
            match.group(0), f'"timestamp":datetime("{timestamp_value}")'
        )

    # Rimuoviamo le backslashes che precedono le virgolette nelle geometrie
    serialized_data = serialized_data.replace(r"\"", '"')

    return serialized_data


def remove_quotes_around_point(json_str):
    # Usa una regex per rimuovere gli apici esterni che racchiudono 'point(...)'
    json_str = re.sub(r'"point\(([^)]+)\)"', r"point(\1)", json_str)
    return json_str


def load_dataframe_to_asterixdb(df):
    """
    Carica un DataFrame Pandas su AsterixDB eseguendo un UPSERT.
    """
    if df.empty:
        print("DataFrame vuoto, nessun dato da caricare.")
        return
    json_data = df.to_dict(orient="records")
    # Crea la query SQL++ per l'inserimento
    query = """
    USE Measurements_Dataverse;
    insert into Measurements ([
    """
    query += ",".join([custom_json_dumps(d) for d in json_data]) + "])"
    query = remove_quotes_around_point(query)
    print(query)
    # Parametri della richiesta
    params = {
        "statement": query,  # La query da eseguire
        "pretty": "true",  # Facoltativo, per una risposta più leggibile
        "mode": "immediate",  # Modalità di risposta
        "dataverse": f"{DATAVERSE}",  # Facoltativo, se non usi il dataverse di default
    }

    # Esegui la richiesta POST
    response = requests.post(f"{ASTERIXDB_HOST}/query/service", params=params)

    if response.status_code == 200:
        logger.info(f"Dati caricati con successo in {DATASET_NAME}!")
    else:
        logger.error(
            f"Errore nel caricamento: {response.status_code} - {response.text}"
        )


agritech_connector = mongodb_connector.MongoDBConnector(AGRITECH_IP, AGRITECH_PORT)
agritech_connector.set_database(AGRITECH_DB_NAME)
agritech_connector.set_collection("unibo")

agritech_devices = agritech_connector.find(query={"type": "Device"}, limit=1)
logger.info(f"Dowloaded {len(agritech_devices)} devices from Agritech MongoDB")
devices_df = pd.DataFrame(agritech_devices)

devices_df = devices_df[
    ["id", "dateObserved", "controlledProperty", "location", "value"]
]

devices_df["location"] = devices_df["location"].apply(parse_geometry)

devices_df = devices_df.explode(["controlledProperty", "value"], ignore_index=True)

devices_df["meas_id"] = devices_df.apply(
    lambda row: f"{row['id']}{row['controlledProperty']}{row['dateObserved']}", axis=1
)

print(len(devices_df))

devices_df.rename(
    columns={
        "id": "device_id",
        "controlledProperty": "controlled_property",
        "dateObserved": "timestamp",
    },
    inplace=True,
)


# Esempio di utilizzo
if __name__ == "__main__":

    batch_size = 1  # Definisci la dimensione del batch

    # Suddividi il DataFrame in batch di 1000 righe
    for i in range(0, len(devices_df), batch_size):
        batch = devices_df.iloc[i : i + batch_size]  # Seleziona il batch corrente
        load_dataframe_to_asterixdb(batch)
