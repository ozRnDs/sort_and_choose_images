import pickle

from loguru import logger
from tqdm import tqdm

# Replace with the path to your PICKLE_FILE
PICKLE_FILE = "/workspaces/sort_and_choose_images/data/mor-data/backup-0.10.0/group.pkl"
# PICKLE_FILE = "/workspaces/sort_and_choose_images/data/mor-data/backup-0.10.0/images.pkl"


def load_pickle(file_path):
    """
    Load a pickle file and return its content.
    """
    try:
        with open(file_path, "rb") as file:
            data = pickle.load(file)
        return data
    except FileNotFoundError:
        print(f"Error: File not found - {file_path}")
        return None
    except Exception as e:
        print(f"Error loading pickle file: {e}")
        return None


def find_unknown_dates(data):
    """
    Find all entries with "Unknown" date in the given data.
    """
    if not isinstance(data, list):
        print("Error: Expected data to be a list of entries.")
        return []

    unknown_dates = [entry for entry in data if entry.get("creationDate") == "Unknown"]
    return unknown_dates


if __name__ == "__main__":
    # Load the pickle file
    print("Loading pickle file...")
    data = load_pickle(PICKLE_FILE)

    if data is not None:
        list_of_images = []
        for group in tqdm(data):
            list_of_images += group["list_of_images"]
        print(f"Pickle file loaded successfully. Total entries: {len(data)}")

        for current_image in tqdm(list_of_images):
            images_with_same_name = [
                image
                for image in list_of_images
                if image["name"] == current_image["name"]
            ]
            if len(images_with_same_name) == 1:
                continue
            classifications = {
                image["full_client_path"]: image["classification"]
                for image in images_with_same_name
                if image["classification"] != "None"
            }
            if current_image["size"] == 3235668:
                logger.info(f"Got here: {images_with_same_name} | {classifications}")
            if len(images_with_same_name) > 1 and len(classifications) > 0:
                logger.info(
                    f"Image with multiple instances and classification: {classifications}"
                )

        # Find and display entries with "Unknown" dates
        # print("Searching for entries with 'Unknown' dates...")
        # unknown_entries = find_unknown_dates(data)

        # if unknown_entries:
        #     print(f"Found {len(unknown_entries)} entries with 'Unknown' dates:")
        #     for idx, entry in enumerate(unknown_entries, start=1):
        #         print(f"{idx}: {entry}")
        # else:
        #     print("No entries with 'Unknown' dates found.")
    else:
        print("Failed to load pickle file.")
