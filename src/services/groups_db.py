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


def sort_and_save_groups(grouped_metadata: List[Dict]):
    """
    Sort the groups by date and save them to the grouped metadata file.

    Args:
        grouped_metadata (List[Dict]): The list of grouped metadata to save.
    """
    grouped_metadata.sort(key=lambda x: x.get("group_name", "Unknown"))
    with open(GROUPED_FILE, "wb") as f:
        pickle.dump(grouped_metadata, f)
