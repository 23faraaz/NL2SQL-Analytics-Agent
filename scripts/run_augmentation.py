import sys

from etl.augment.pipeline import run_augmentation_pipeline
from etl.logging_config import configure_logging, get_logger


configure_logging()
logger = get_logger(__name__)


def main() -> int:
    try:
        run_augmentation_pipeline()
    except Exception:
        logger.error("Synthetic augmentation execution failed")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
