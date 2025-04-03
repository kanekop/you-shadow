
document.getElementById('compareBtn').addEventListener('click', async () => {
  const passage1 = document.getElementById('passage1').value.trim();
  const passage2 = document.getElementById('passage2').value.trim();
  
  if (!passage1 || !passage2) {
    alert('Please enter both passages');
    return;
  }

  try {
    const response = await fetch('/api/compare_passages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        passage1,
        passage2
      })
    });

    const data = await response.json();
    
    document.getElementById('werScore').textContent = data.wer.toFixed(1);
    document.getElementById('diffResult').innerHTML = data.diff_html;
    document.getElementById('results').style.display = 'block';
  } catch (error) {
    console.error('Error:', error);
    alert('An error occurred while comparing the passages');
  }
});
