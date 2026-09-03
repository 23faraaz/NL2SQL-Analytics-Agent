from __future__ import annotations

import argparse
import json
from pathlib import Path

from etl.dataset_bundle import create_bundle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a deterministic, checksummed Olist import bundle."
    )
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = create_bundle(args.raw_dir, args.output)
    print(
        json.dumps({"dataset_id": manifest["dataset_id"], "output": str(args.output)})
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
