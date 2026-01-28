import pandas as pd
from datetime import datetime


def device(device, measurement_schema):
    timestamp = datetime.fromisoformat(
        device["dateObserved"].replace("Z", "")
    ).timestamp()

    measurements_list = []
    for property, value in zip(device["controlledProperty"], device["value"]):
        # Crea una nuova riga
        new_row = [
            timestamp,
            device["id"],
            property,
            extract_location(device),
            value,
            str(value),
        ]
        measurements_list.append(new_row)

    measurements = pd.DataFrame(measurements_list, columns=measurement_schema)
    return measurements


def temperature(measurement):
    return (
        measurement["timestamp"],
        measurement["sensor"]["id"],
        "Temperature",
        measurement["payload"]["temperature"],
        extract_location(measurement),
    )


def agri_robot(device, measurement_schema):
    timestamp = device["timestamp_kafka"]
    measurements = pd.DataFrame(columns=measurement_schema)
    for property, value in zip(device["serviceProvided"], device["status"]):
        new_row = pd.DataFrame(
            [
                [
                    timestamp,
                    device["id"],
                    property,
                    extract_location(device),
                    value,
                    str(value),
                ]
            ],
            columns=measurement_schema,
        )
        measurements = pd.concat(
            [measurements, new_row],
            ignore_index=True,
        )
    return measurements


def get_mapping_function(entity_type):
    return MAPPING_FUNCS.get(entity_type)


MAPPING_FUNCS = {
    "Device": device,
    "AgriRobot": agri_robot,
    "Temperature": temperature,
}


def extract_location(device):
    return device["location"] if device["location"] is not None else "POINT EMPTY"
