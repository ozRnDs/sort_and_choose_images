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
        const response = await fetch(`/get_groups_paginated?page=1&page_size=100&filter_selections=interesting`);
        if (!response.ok) {
            throw new Error('Failed to fetch group data');
        }
        const data = await response.json();
        displayGroups(data.groups);
    } catch (error) {
        console.error('Error fetching group data:', error);
    }
}

function displayGroups(groups) {
    const groupsList = document.getElementById('groupsList');
    groupsList.innerHTML = '';
    const groupedByMonth = {};

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

    Object.keys(groupedByMonth).sort().forEach(month => {
        const monthDiv = document.createElement('div');
        monthDiv.className = 'month-group';
        monthDiv.innerHTML = `<h5>${month}</h5>`;
        groupedByMonth[month].forEach(group => {
            const div = document.createElement('div');
            div.className = 'group-item';
            div.dataset.groupName = group.group_name;
            div.onclick = () => fetchGroupImages(group.group_name);
            div.innerHTML = `<strong>${group.group_name}</strong> (${group.list_of_images.length} images)`;
            monthDiv.appendChild(div);
        });
        groupsList.appendChild(monthDiv);
    });
}

async function fetchGroupImages(groupName) {
    try {
        const response = await fetch(`/get_groups_paginated?page=1&page_size=100&filter_selections=interesting`);
        if (!response.ok) {
            throw new Error('Failed to fetch group data');
        }
        const data = await response.json();
        const group = data.groups.find(g => g.group_name === groupName);
        if (group) {
            highlightSelectedGroup(groupName);
            displayImages(group.list_of_images, group.group_name);
        }
    } catch (error) {
        console.error('Error fetching group data:', error);
    }
}
function displayImages(images, groupName) {
    const grid = document.getElementById('grid');
    grid.innerHTML = '';
    images.forEach((image, index) => {
        const div = document.createElement('div');
        div.className = 'grid-item';
        div.innerHTML = `
            <img src="${image.full_client_path}" alt="Image ${index + 1}" onclick="enlargeImage('${image.full_client_path}')">
            <div class="mt-2">
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
}

async function updateClassification(index, groupName, imageName, classification) {
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
}

function enlargeImage(imageSrc) {
    const overlay = document.createElement('div');
    overlay.className = 'enlarge-overlay';
    overlay.onclick = () => document.body.removeChild(overlay);

    const img = document.createElement('img');
    img.src = imageSrc;
    img.className = 'enlarge';
    overlay.appendChild(img);

    document.body.appendChild(overlay);
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
