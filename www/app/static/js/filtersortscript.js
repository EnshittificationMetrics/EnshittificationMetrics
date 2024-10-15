// Function to handle AJAX requests
function updateFilterSort(type, value) {
    fetch('/update-filtersort', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ [type]: value }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            window.location.reload();  // Reload page on success
        } else {
            console.error('Error updating filter/sort:', data);
        }
    })
    .catch(error => console.error('Fetch error:', error));
}

// Attach event listeners to buttons

document.addEventListener('DOMContentLoaded', () => {
    
    document.getElementById('catAll').addEventListener('click', () => {
        updateFilterSort('ranking_cats', 'All');
    });
    
    document.getElementById('catSocial').addEventListener('click', () => {
        updateFilterSort('ranking_cats', 'Social');
    });
    
    document.getElementById('catCloud').addEventListener('click', () => {
        updateFilterSort('ranking_cats', 'Cloud');
    });
    
    document.getElementById('catB2B').addEventListener('click', () => {
        updateFilterSort('ranking_cats', 'B2B');
    });
    
    document.getElementById('catB2C').addEventListener('click', () => {
        updateFilterSort('ranking_cats', 'B2C');
    });
    
    document.getElementById('catC2C').addEventListener('click', () => {
        updateFilterSort('ranking_cats', 'C2C');
    });
    
    document.getElementById('catPlatform').addEventListener('click', () => {
        updateFilterSort('ranking_cats', 'tech platform');
    });
    
    document.getElementById('catP2P').addEventListener('click', () => {
        updateFilterSort('ranking_cats', 'P2P');
    });
    
    document.getElementById('sortAlph').addEventListener('click', () => {
        updateFilterSort('ranking_sort', 'name');
    });
    
    document.getElementById('sortStage').addEventListener('click', () => {
        updateFilterSort('ranking_sort', 'stage');
    });
    
    document.getElementById('sortAge').addEventListener('click', () => {
        updateFilterSort('ranking_sort', 'age');
    });
    
    document.getElementById('statusLive').addEventListener('click', () => {
        updateFilterSort('ranking_stat', 'live');
    });
    
    document.getElementById('statusPotential').addEventListener('click', () => {
        updateFilterSort('ranking_stat', 'potential');
    });
    
    document.getElementById('statusAll').addEventListener('click', () => {
        updateFilterSort('ranking_stat', 'not disabled');
    });
    
    document.getElementById('statusDisabled	').addEventListener('click', () => {
        updateFilterSort('ranking_stat', 'disabled');
    });
    
    document.getElementById('sortAsc').addEventListener('click', () => {
        updateFilterSort('display_order', 'recent first');
    });
    
    document.getElementById('sortDesc').addEventListener('click', () => {
        updateFilterSort('display_order', 'oldest first');
    });
    
});