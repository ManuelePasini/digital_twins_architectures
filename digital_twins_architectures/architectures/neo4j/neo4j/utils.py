import logging
import sys


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