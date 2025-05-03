
async function loadRecordings() {
    try {
        const response = await fetch('/api/recordings');
        if (!response.ok) throw new Error('Failed to fetch recordings');
        
        const data = await response.json();
        const container = document.getElementById('recordings-list');
        
        data.recordings.forEach(recording => {
            const div = document.createElement('div');
            div.className = 'recording-item';
            div.innerHTML = `
                <h3>${recording.filename}</h3>
                <p class="transcript">${recording.transcript}</p>
                <p class="date">Recorded: ${new Date(recording.created_at).toLocaleString()}</p>
            `;
            container.appendChild(div);
        });
    } catch (error) {
        console.error('Error loading recordings:', error);
    }
}

document.addEventListener('DOMContentLoaded', loadRecordings);
