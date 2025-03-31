  document.addEventListener("DOMContentLoaded", async () => {
    const currentUser = localStorage.getItem("username") || "（未設定）";
    document.getElementById("userDisplay").textContent = `🧑‍💻 現在のユーザー：${currentUser}`;

    const genreSelect = document.getElementById("genreSelect");
    const levelSelect = document.getElementById("levelSelect");
    const showBtn = document.getElementById("showBtn");

    const res = await fetch("/api/presets");
    const data = await res.json();

    for (const genre in data) {
      const opt = document.createElement("option");
      opt.value = genre;
      opt.textContent = genre;
      genreSelect.appendChild(opt);
    }

    function populateLevels(selectedGenre) {
      levelSelect.innerHTML = "";
      (data[selectedGenre] || []).forEach(level => {
        const opt = document.createElement("option");
        opt.value = level;
        opt.textContent = level;
        levelSelect.appendChild(opt);
      });
    }

    if (genreSelect.value) {
      populateLevels(genreSelect.value);
    }

    genreSelect.addEventListener("change", () => {
      populateLevels(genreSelect.value);
    });

    showBtn.addEventListener("click", () => {
      const genre = genreSelect.value;
      const level = levelSelect.value;
      if (genre && level) {
        window.location.href = `/ranking?genre=${genre}&level=${level}`;
      }
    });

    // ⭐ ハイライト処理とレベル解放チェック
    const entries = document.querySelectorAll("#rankingList li");
    let cleared = false;

    entries.forEach(li => {
      const user = li.dataset.user;
      const wer = parseFloat(li.dataset.wer);
      const timestamp = li.dataset.timestamp.slice(0, 10);

      if (user === currentUser) {
        li.innerHTML = `⭐ <strong>${user}</strong> - ${wer}%（${timestamp}）`;
        li.classList.add("highlight");
        if (wer < 30) {
          cleared = true;
        }
      } else {
        li.innerHTML = `${user} - ${wer}%（${timestamp}）`;
      }
    });

    if (cleared) {
      document.getElementById("nextLevelNotice").textContent =
        "🎉 あなたのWERが30%未満です！次のレベルに進めます！";
    }
  });
