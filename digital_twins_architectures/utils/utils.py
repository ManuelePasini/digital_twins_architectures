import logging
import sys
import pandas as pd
from datetime import datetime


def is_dict_or_list_of_dicts(value):
    if isinstance(value, dict):
        return True
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return True
    return False


def setup_logger(logger_name, log_level=logging.INFO):
    log_format = "[%(asctime)s][%(levelname)s] %(name)s: %(message)s"
    formatter = logging.Formatter(log_format)

    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)

    # Create stream handler to print logs to standard output
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(log_level)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


def is_FIWARE_id(property_value):
    id_regex = "urn:ngsi-ld:"
    if isinstance(property_value, int):
        return False
    elif isinstance(property_value, str):
        return id_regex in property_value
    if isinstance(property_value, list):
        return all([is_FIWARE_id(prop) for prop in property_value])


def get_entity_edges(entity_dict: dict):
    return [
        key
        for key, value in entity_dict.items()
        if is_FIWARE_id(value) and not key == "id"
    ]



