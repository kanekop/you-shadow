document.addEventListener("DOMContentLoaded", () => {
  const nameDisplay = document.getElementById("nameDisplay");
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