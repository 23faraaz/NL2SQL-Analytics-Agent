from pathlib import Path
from typing import Any

import pandas as pd

from etl.config import PROCESSED_DATA_DIR, RAW_DATA_DIR
from etl.logging_config import get_logger


logger = get_logger(__name__)


def load_raw_csv(
    filename: str,
    **read_csv_kwargs: Any,
) -> pd.DataFrame:
    """Load a CSV file from the immutable raw-data layer."""

    file_path = RAW_DATA_DIR / filename

    if not file_path.exists():
        raise FileNotFoundError(
            f"Raw dataset file does not exist: {file_path}"
        )

    if file_path.stat().st_size == 0:
        raise ValueError(
            f"Raw dataset file is empty: {file_path}"
        )

    try:
        dataframe = pd.read_csv(
            file_path,
            **read_csv_kwargs,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Could not read raw dataset file {file_path}: {exc}"
        ) from exc

    logger.info(
        "Loaded raw file %s (%d rows, %d columns)",
        filename,
        len(dataframe),
        len(dataframe.columns),
    )

    return dataframe


def save_processed_csv(
    dataframe: pd.DataFrame,
    filename: str,
) -> Path:
    """Save a transformed dataframe into the processed-data layer."""

    PROCESSED_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = PROCESSED_DATA_DIR / filename
    temporary_path = output_path.with_suffix(".tmp")

    try:
        dataframe.to_csv(
            temporary_path,
            index=False,
        )

        temporary_path.replace(output_path)

    except Exception as exc:
        temporary_path.unlink(missing_ok=True)

        raise RuntimeError(
            f"Could not save processed dataset {output_path}: {exc}"
        ) from exc

    logger.info(
        "Saved processed file %s (%d rows)",
        filename,
        len(dataframe),
    )

    return output_path