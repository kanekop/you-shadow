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
});

function logout() {
  fetch('/__replauthlogout')
    .then(() => {
      localStorage.removeItem('username');
      location.reload();
    });
}