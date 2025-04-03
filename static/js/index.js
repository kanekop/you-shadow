  document.addEventListener("DOMContentLoaded", () => {
    const savedName = localStorage.getItem("username");
    const nameForm = document.getElementById("nameForm");
    const nameInput = document.getElementById("username");
    const nameDisplay = document.getElementById("nameDisplay");

    if (savedName) {
      nameForm.style.display = "none";
      nameDisplay.textContent = `こんにちは、${savedName} さん！`;
    }

    document.getElementById("saveNameBtn").addEventListener("click", () => {
      const name = nameInput.value.trim();
      if (name) {
        localStorage.setItem("username", name);
        nameForm.style.display = "none";
        nameDisplay.textContent = `こんにちは、${name} さん！`;
      }
    });

    // ✅ デバッグ用：テストユーザー切り替え
    const testButtons = document.querySelectorAll(".test-user-btn");
    testButtons.forEach(btn => {
      btn.addEventListener("click", () => {
        const user = btn.dataset.user;
        localStorage.setItem("username", user);
        location.reload();
      });
    });
  });
function logout() {
  fetch('/__replauthlogout')
    .then(() => {
      localStorage.removeItem('username');
      window.location.reload();
    });
}
