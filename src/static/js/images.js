let currentGroupImages = [];

async function loadImages() {
    const loadingElement = document.getElementById('loading');
    loadingElement.style.display = 'block';
    try {
        const response = await fetch('/load_images');
        if (!response.ok) {
            throw new Error('Failed to load images');
        }
        window.location.reload();
    } catch (error) {
        console.error('Error loading images:', error);
        alert('Failed to load images');
    } finally {
        loadingElement.style.display = 'none';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    fetchGroups();
    setTimeout(() => {
        const firstGroup = document.querySelector('.group-item');
        if (firstGroup) {
            firstGroup.click();
        }
    }, 500);
});

async function fetchGroups() {
    try {
        const response = await fetch(`/get_groups_paginated?page=1&page_size=400&filter_selections=interesting`);
        if (!response.ok) {
            throw new Error('Failed to fetch group data');
        }
        const data = await response.json();
        displayGroups(data.groups);
    } catch (error) {
        console.error('Error fetching group data:', error);
    }
}

async function displayGroups(groups) {
    const groupsList = document.getElementById('groupsList');
    groupsList.innerHTML = '';
    const groupedByMonth = {};

    // Group by month
    groups.forEach(group => {
        const dateParts = group.group_name.split('-');
        if (dateParts.length >= 2) {
            const yearMonth = `${dateParts[0]}-${dateParts[1]}`;
            if (!groupedByMonth[yearMonth]) {
                groupedByMonth[yearMonth] = [];
            }
            groupedByMonth[yearMonth].push(group);
        }
    });

    // Process each group
    // Process each group asynchronously
    for (const month of Object.keys(groupedByMonth).sort()) {
        const monthDiv = document.createElement('div');
        monthDiv.className = 'month-group';
        monthDiv.innerHTML = `<h5>${month}</h5>`;

        // Create divs for each group asynchronously
        for (const group of groupedByMonth[month]) {
            const hasClassification = await checkGroupHasClassification(group.group_name); // Await for each group's classification check
            const div = document.createElement('div');
            div.className = `group-item ${hasClassification ? 'has-classification' : ''}`;
            
            div.dataset.groupName = group.group_name;
            div.onclick = () => fetchGroupImages(group.group_name);
            div.innerHTML = `
                <strong>${group.group_name}</strong> 
                (${group.list_of_images.length} images)
                ${group.has_new_image ? '<span class="new-icon">🆕</span>' : ''}
            `;
            monthDiv.appendChild(div);
        }

        groupsList.appendChild(monthDiv);
    }
}

async function checkGroupHasClassification(groupName) {
    try {
        const response = await fetch(`/check_group_has_classification?group_name=${encodeURIComponent(groupName)}`);
        if (!response.ok) {
            console.error(`Failed to fetch images for group: ${groupName}`);
            return false;
        }

        const data = await response.json();
        return data.has_classification
    } catch (error) {
        console.error(`Error checking classification for group: ${groupName}`, error);
        return false;
    }
}

async function updateGroupClassificationClass(groupName) {
    try {
        // Call the existing checkGroupHasClassification method
        const hasClassification = await checkGroupHasClassification(groupName);

        // Find the group element using its data attribute
        const groupElement = document.querySelector(`[data-group-name="${groupName}"]`);
        if (!groupElement) {
            console.warn(`Group element for ${groupName} not found`);
            return;
        }

        // Update the class name based on the classification status
        if (hasClassification) {
            groupElement.classList.add('has-classification');
        } else {
            groupElement.classList.remove('has-classification');
        }
    } catch (error) {
        console.error(`Error updating classification class for group: ${groupName}`, error);
    }
}


async function fetchGroupImages(groupName) {
    try {
        const response = await fetch(`/get_group_images?group_name=${encodeURIComponent(groupName)}`);
        if (!response.ok) {
            throw new Error('Failed to fetch group images');
        }
        const images = await response.json();
        highlightSelectedGroup(groupName);
        displayImages(images, groupName);
    } catch (error) {
        console.error('Error fetching group images:', error);
    }
}

function displayImages(images, groupName) {
    currentGroupImages = images; // Assign to global variable
    const grid = document.getElementById('grid');
    grid.innerHTML = '';
    images.sort((image1, image2)=> image2.size - image1.size);
    images.forEach((image, index) => {
        const resolutionTag = getImageQualityTag(image.size); // Use file size from the server
        const div = document.createElement('div');
        div.className = 'grid-item';
        div.innerHTML = `
            <img src="${image.full_client_path}" alt="Image ${index + 1}" onclick="enlargeImage(${index}, '${groupName}')">
            <div class="mt-2">
                ${resolutionTag} <!-- Include resolution tag -->
                <button class="ron-btn ${image.ron_in_image ? '' : 'no'}" onclick="toggleRonInImage(${index}, '${groupName}', '${image.name}')">Ron in the image: ${image.ron_in_image ? 'Yes' : 'No'}</button>
            </div>
            <div class="classify-controls">
                <div class="btn-group" role="group" aria-label="Image Classification">
                    <input type="radio" class="btn-check" name="classification-${index}" value="Historical" id="historical-${index}" ${image.classification === 'Historical' ? 'checked' : ''}>
                    <label class="btn btn-outline-primary" for="historical-${index}" onclick="updateClassification(${index}, '${groupName}', '${image.name}', 'Historical')">Historical</label>
                    
                    <input type="radio" class="btn-check" name="classification-${index}" value="Nature" id="nature-${index}" ${image.classification === 'Nature' ? 'checked' : ''}>
                    <label class="btn btn-outline-primary" for="nature-${index}" onclick="updateClassification(${index}, '${groupName}', '${image.name}', 'Nature')">Nature</label>
                    
                    <input type="radio" class="btn-check" name="classification-${index}" value="Family Trips" id="family-trips-${index}" ${image.classification === 'Family Trips' ? 'checked' : ''}>
                    <label class="btn btn-outline-primary" for="family-trips-${index}" onclick="updateClassification(${index}, '${groupName}', '${image.name}', 'Family Trips')">Family Trips</label>
                    
                    <input type="radio" class="btn-check" name="classification-${index}" value="Family Gatherings" id="family-gatherings-${index}" ${image.classification === 'Family Gatherings' ? 'checked' : ''}>
                    <label class="btn btn-outline-primary" for="family-gatherings-${index}" onclick="updateClassification(${index}, '${groupName}', '${image.name}', 'Family Gatherings')">Family Gatherings</label>
                    
                    <input type="radio" class="btn-check" name="classification-${index}" value="Archaeology" id="archaeology-${index}" ${image.classification === 'Archaeology' ? 'checked' : ''}>
                    <label class="btn btn-outline-primary" for="archaeology-${index}" onclick="updateClassification(${index}, '${groupName}', '${image.name}', 'Archaeology')">Archaeology</label>
                    
                    <input type="radio" class="btn-check" name="classification-${index}" value="None" id="none-${index}" ${image.classification === 'None' ? 'checked' : ''}>
                    <label class="btn btn-outline-primary" for="none-${index}" onclick="updateClassification(${index}, '${groupName}', '${image.name}', 'None')">None</label>
                </div>
            </div>
        `;
        grid.appendChild(div);
    });
}

async function toggleRonInImage(index, groupName, imageName) {
    const button = document.querySelector(`.grid-item:nth-child(${index + 1}) .ron-btn`);
    const currentValue = button.textContent.includes('Yes');
    const newValue = !currentValue;

    button.textContent = `Ron in the image: ${newValue ? 'Yes' : 'No'}`;
    button.classList.toggle('no', !newValue);

    await fetch('/update_ron_in_image', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            group_name: groupName,
            image_name: imageName,
            ron_in_image: newValue
        })
    });

    await updateGroupClassificationClass(groupName)
}

async function updateClassification(index, groupName, imageName, classification) {
    currentGroupImages[index].classification = classification; // Update in memory
    await fetch('/update_image_classification', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            group_name: groupName,
            image_name: imageName,
            classification: classification
        })
    });

    // Check if any image in the group has a classification other than "None"
    const hasClassification = currentGroupImages.some(image => image.classification !== 'None');
    const groupElement = document.querySelector(`.group-item[data-group-name="${groupName}"]`);
    if (groupElement) {
        if (hasClassification) {
            groupElement.classList.add('has-classification'); // Add grey background
        } else {
            groupElement.classList.remove('has-classification'); // Remove grey background
        }
    }
}

function enlargeImage(imageIndex, groupName) {
    const images = currentGroupImages;
    const image = images[imageIndex];

    // Remove existing overlay if present
    const existingOverlay = document.querySelector('.enlarge-overlay');
    if (existingOverlay) {
        document.body.removeChild(existingOverlay);
    }

    // Create overlay
    const overlay = document.createElement('div');
    overlay.className = 'enlarge-overlay';

    // Close overlay on clicking the background
    overlay.onclick = (e) => {
        if (e.target === overlay) {
            document.body.removeChild(overlay);
            displayImages(currentGroupImages, groupName); // Refresh the image grid on exit
        }
    };

    // Create enlarged image container
    const container = document.createElement('div');
    container.className = 'enlarge-container';

    // Add resolution tag based on file size
    const resolutionTag = getImageQualityTag(image.size);
    container.innerHTML = `
        <img src="${image.full_client_path}" class="enlarge">
        <div>${resolutionTag}</div>
    `;

    // Add RON tagging button
    const ronButton = document.createElement('button');
    ronButton.className = `ron-btn ${image.ron_in_image ? '' : 'no'}`;
    ronButton.textContent = `Ron in the image: ${image.ron_in_image ? 'Yes' : 'No'}`;
    ronButton.onclick = async () => {
        const newValue = !image.ron_in_image;
        image.ron_in_image = newValue;
        ronButton.textContent = `Ron in the image: ${newValue ? 'Yes' : 'No'}`;
        ronButton.classList.toggle('no', !newValue);

        await fetch('/update_ron_in_image', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                group_name: groupName,
                image_name: image.name,
                ron_in_image: newValue,
            }),
        });
    };
    container.appendChild(ronButton);

    // Add classification buttons
    const classifyControls = document.createElement('div');
    classifyControls.className = 'classify-controls';
    classifyControls.innerHTML = `
        <div class="btn-group" role="group" aria-label="Image Classification">
            <input type="radio" class="btn-check" name="classification" value="Historical" id="historical" ${image.classification === 'Historical' ? 'checked' : ''}>
            <label class="btn btn-outline-primary" for="historical" onclick="updateClassification(${imageIndex}, '${groupName}', '${image.name}', 'Historical')">Historical</label>

            <input type="radio" class="btn-check" name="classification" value="Nature" id="nature" ${image.classification === 'Nature' ? 'checked' : ''}>
            <label class="btn btn-outline-primary" for="nature" onclick="updateClassification(${imageIndex}, '${groupName}', '${image.name}', 'Nature')">Nature</label>

            <input type="radio" class="btn-check" name="classification" value="Family Trips" id="family-trips" ${image.classification === 'Family Trips' ? 'checked' : ''}>
            <label class="btn btn-outline-primary" for="family-trips" onclick="updateClassification(${imageIndex}, '${groupName}', '${image.name}', 'Family Trips')">Family Trips</label>

            <input type="radio" class="btn-check" name="classification" value="Family Gatherings" id="family-gatherings" ${image.classification === 'Family Gatherings' ? 'checked' : ''}>
            <label class="btn btn-outline-primary" for="family-gatherings" onclick="updateClassification(${imageIndex}, '${groupName}', '${image.name}', 'Family Gatherings')">Family Gatherings</label>

            <input type="radio" class="btn-check" name="classification" value="Archaeology" id="archaeology" ${image.classification === 'Archaeology' ? 'checked' : ''}>
            <label class="btn btn-outline-primary" for="archaeology" onclick="updateClassification(${imageIndex}, '${groupName}', '${image.name}', 'Archaeology')">Archaeology</label>

            <input type="radio" class="btn-check" name="classification" value="None" id="none" ${image.classification === 'None' ? 'checked' : ''}>
            <label class="btn btn-outline-primary" for="none" onclick="updateClassification(${imageIndex}, '${groupName}', '${image.name}', 'None')">None</label>
        </div>
    `;
    container.appendChild(classifyControls);

    // Add navigation buttons
    const navigation = document.createElement('div');
    navigation.className = 'navigation-controls';
    navigation.innerHTML = `
        <button class="btn btn-secondary" onclick="navigateImage(${imageIndex - 1}, '${groupName}')" ${imageIndex === 0 ? 'disabled' : ''}>Previous</button>
        <button class="btn btn-secondary" onclick="navigateImage(${imageIndex + 1}, '${groupName}')" ${imageIndex === images.length - 1 ? 'disabled' : ''}>Next</button>
    `;
    container.appendChild(navigation);

    overlay.appendChild(container);
    document.body.appendChild(overlay);
}


// Navigate to the next or previous image
function navigateImage(newIndex, groupName) {
    if (newIndex >= 0 && newIndex < currentGroupImages.length) {
        enlargeImage(newIndex, groupName);
    }
}

function highlightSelectedGroup(groupName) {
    // Remove the 'selected-group' class from all group items
    const allGroups = document.querySelectorAll('.group-item');
    allGroups.forEach(group => group.classList.remove('selected-group'));

    // Add the 'selected-group' class to the clicked group
    const selectedGroup = Array.from(allGroups).find(group => group.dataset.groupName === groupName);
    if (selectedGroup) {
        selectedGroup.classList.add('selected-group');
    }
}

function getImageQualityTag(fileSize) {
    if (fileSize < 2 * 1024 * 1024) { // Less than 2MB
        return '<span class="badge bg-warning text-dark">Low Resolution</span>';
    } else if (fileSize > 3.5 * 1024 * 1024) { // Greater than 4MB
        return '<span class="badge bg-lilac">High Resolution</span>';
    } else {
        return '<span class="badge bg-burnt-orange">Medium Resolution</span>';
    }
}