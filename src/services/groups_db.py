import pickle
from pathlib import Path
from typing import Dict, List

from fastapi import exceptions, status

GROUPED_FILE = "/data/grouped_metadata.pkl"


def load_groups_from_file() -> List[Dict]:
    # Load existing grouped metadata
    grouped_file_path = Path(GROUPED_FILE)
    if not grouped_file_path.exists():
        raise exceptions.HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Grouped metadata not found"
        )

    with open(GROUPED_FILE, "rb") as f:
        grouped_metadata = pickle.load(f)

    return grouped_metadata
