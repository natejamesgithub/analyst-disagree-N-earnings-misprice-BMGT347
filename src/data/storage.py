"""Publish each invocation as a complete, new output directory."""

import json
from pathlib import Path
import tempfile


def publish(destination, tables, audit=None):
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError(f"Output directory already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix=".pipeline-") as temp:
        staging = Path(temp) / "output"
        staging.mkdir()
        for name, frame in tables.items():
            frame.to_csv(staging / f"{name}.csv", index=False, date_format="%Y-%m-%d")
        if audit is not None:
            (staging / "audit.json").write_text(
                json.dumps(audit, indent=2, sort_keys=True, default=str) + "\n",
                encoding="utf-8",
            )
        staging.rename(destination)
