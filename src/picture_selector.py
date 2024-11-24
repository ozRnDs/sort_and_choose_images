import os
import pickle

import streamlit as st
from PIL import Image

# Path to store the progress file
PROGRESS_FILE = "progress.pkl"
ANNOTATIONS_FILE = "annotations.pkl"


# Load progress and annotations if they exist
def load_state():
    # Load the current progress from a file if it exists, otherwise return 0 (start from the beginning)
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "rb") as f:
            return pickle.load(f)
    return 0


# Save current progress
def save_state(current_index):
    # Save the current index to track progress
    with open(PROGRESS_FILE, "wb") as f:
        pickle.dump(current_index, f)


# Load annotations if they exist
def load_annotations():
    # Load previously saved annotations from a file if it exists, otherwise return an empty dictionary
    if os.path.exists(ANNOTATIONS_FILE):
        with open(ANNOTATIONS_FILE, "rb") as f:
            return pickle.load(f)
    return {}


# Save annotations
def save_annotations(annotations):
    # Save annotations to a file
    with open(ANNOTATIONS_FILE, "wb") as f:
        pickle.dump(annotations, f)


# Streamlit app
st.title("Image Annotation Tool")

# Directory input
# Input field to enter the path of the directory containing images
image_dir = st.text_input("Enter the local directory containing images:")

if image_dir:
    # Get all image files from directory
    # Filter out all image files (with common extensions) from the given directory
    image_files = [
        f
        for f in os.listdir(image_dir)
        if f.lower().endswith(("png", "jpg", "jpeg", "bmp", "gif"))
    ]
    image_files.sort()  # Sort the files to ensure consistent order

    # Load current progress and annotations
    current_index = load_state()  # Load the index of the last annotated image
    annotations = load_annotations()  # Load previous annotations if any

    # Check if there are images left to annotate
    if current_index < len(image_files):
        # Show current image
        image_path = os.path.join(image_dir, image_files[current_index])
        image = Image.open(image_path)
        # Display the image with its index and total number of images
        st.image(
            image,
            caption=f"Image {current_index + 1} of {len(image_files)}",
            use_container_width=True,
        )

        # Annotation options
        # Provide radio buttons for the user to annotate the current image
        annotation = st.radio(
            "Annotate this image as:",
            ("Not interesting", "Recent", "History", "General"),
        )

        # Mark as done button
        # Button to move to the next image after annotation
        if st.button("Next Image"):
            # Save annotation for the current image
            annotations[image_files[current_index]] = annotation
            save_annotations(annotations)

            # Move to the next image by incrementing the index
            current_index += 1
            save_state(current_index)

            # Refresh the app to show the next image
            st.experimental_set_query_params()
    else:
        # All images have been annotated
        st.write("All images have been annotated!")

    # Option to reset progress
    # Button to reset the progress and annotations if the user wants to start over
    if st.button("Reset Progress"):
        current_index = 0
        save_state(current_index)  # Reset the progress index
        annotations = {}
        save_annotations(annotations)  # Clear all annotations
        st.experimental_set_query_params()  # Reload the app to reflect the reset
