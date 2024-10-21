// Function to handle AJAX requests
function updateFuncStage(type, value) {
    fetch('/update-funcstage', {
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
    
    document.getElementById('stageOne').addEventListener('click', () => {
        updateFuncStage('func_stage', 1);
    });
    
    document.getElementById('stageTwo').addEventListener('click', () => {
        updateFuncStage('func_stage', 2);
    });
    
    document.getElementById('stageThree').addEventListener('click', () => {
        updateFuncStage('func_stage', 3);
    });
    
    document.getElementById('stageFour').addEventListener('click', () => {
        updateFuncStage('func_stage', 4);
    });
    
});