import sys

from etl.logging_config import configure_logging, get_logger
from etl.pipeline import run_transformation_pipeline


configure_logging()
logger = get_logger(__name__)


def main() -> int:
    try:
        run_transformation_pipeline()
    except Exception:
        logger.error("ETL execution failed")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())