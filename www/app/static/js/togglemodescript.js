    // Step 1: Load the theme from localStorage (if it exists), otherwise use server-side value
    let currentTheme = localStorage.getItem('theme') || "{{ current_user.viewing_mode }}";

    // Step 2: Apply the saved theme on initial load
    if (currentTheme === 'dark') {
        document.body.classList.add('dark-mode');
    } else {
        document.body.classList.remove('dark-mode');
    }

    // Get the toggle button
    const toggleButton = document.getElementById('modeToggle');

    // Step 3: Add event listener for the toggle button
    toggleButton?.addEventListener('click', function() {
        // Toggle the "dark-mode" class on the body
        document.body.classList.toggle('dark-mode');

        // Get the current mode (dark or light)
        const newTheme = document.body.classList.contains('dark-mode') ? 'dark' : 'light';

        // Update localStorage for immediate user experience
        localStorage.setItem('theme', newTheme);

        // Update the server-side viewing mode with an AJAX call
        fetch('/update-viewing-mode', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': '{{ csrf_token() }}'
            },
            body: JSON.stringify({ viewing_mode: newTheme })
        }).then(response => response.json())
          .then(data => {
              if (data.status === 'success') {
                  console.log('Viewing mode updated successfully on the server.');
              } else {
                  console.error('Error updating viewing mode on the server.');
              }
          }).catch(error => {
              console.error('Error:', error);
          });
    });
