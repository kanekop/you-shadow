document.addEventListener("DOMContentLoaded", () => {
  const nameDisplay = document.getElementById("nameDisplay");
  const username = document.querySelector('[data-username]')?.dataset.username;
  
  if (username) {
    localStorage.setItem('username', username);
  }
  
  if (nameDisplay) {
    const savedName = localStorage.getItem("username");
    if (savedName) {
      nameDisplay.textContent = `Welcome, ${savedName}!`;
    }
  }

  // Toggle additional features
  const toggleBtn = document.getElementById('toggleFeatures');
  const additionalFeatures = document.getElementById('additionalFeatures');
  
  if (toggleBtn && additionalFeatures) {
    toggleBtn.addEventListener('click', () => {
      const isHidden = additionalFeatures.style.display === 'none';
      additionalFeatures.style.display = isHidden ? 'block' : 'none';
      toggleBtn.textContent = isHidden ? 'その他の機能を隠す' : 'その他の機能を表示';
    });
  }
});

function logout() {
  fetch('/__replauthlogout')
    .then(() => {
      localStorage.removeItem('username');
      window.location.href = 'https://replit.com/logout';
    });
}