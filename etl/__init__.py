from collections.abc import Callable
from typing import Any


def run_transformation_pipeline(*args: Any, **kwargs: Any) -> None:
    """Import the pandas-backed pipeline only when it is actually executed."""

    pipeline: Callable[..., None]
    from etl.pipeline import run_transformation_pipeline as pipeline

    pipeline(*args, **kwargs)


__all__ = [
    "run_transformation_pipeline",
]
