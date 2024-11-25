import pickle

# Replace with the path to your PICKLE_FILE
PICKLE_FILE = "/data/image_metadata.pkl"


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
        print(f"Pickle file loaded successfully. Total entries: {len(data)}")

        # Find and display entries with "Unknown" dates
        print("Searching for entries with 'Unknown' dates...")
        unknown_entries = find_unknown_dates(data)

        if unknown_entries:
            print(f"Found {len(unknown_entries)} entries with 'Unknown' dates:")
            for idx, entry in enumerate(unknown_entries, start=1):
                print(f"{idx}: {entry}")
        else:
            print("No entries with 'Unknown' dates found.")
    else:
        print("Failed to load pickle file.")
