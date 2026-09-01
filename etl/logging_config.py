import logging
import sys

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | " "%(name)s | %(message)s"

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(
    level: int = logging.INFO,
) -> None:
    """
    Configure logging for the ETL pipeline.
    """

    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )


def get_logger(
    name: str,
) -> logging.Logger:
    """
    Return a logger for a module.
    """

    return logging.getLogger(name)
