async loadGenres() {
    const response = await fetch('/api/sentence_structure');
    const structure = await response.json();
    this.displayGenreSelect(structure);
  }

  displayGenreSelect(structure) {
    const select = document.getElementById('genreSelect');
    select.innerHTML = '<option value="">-- ジャンル選択 --</option>';

    for (const genre in structure) {
      const option = document.createElement('option');
      option.value = genre;
      option.textContent = genre;
      select.appendChild(option);
    }

    // Remove any existing listeners before adding a new one
    const newSelect = select.cloneNode(true);
    select.parentNode.replaceChild(newSelect, select);
    newSelect.addEventListener('change', () => this.updateLevelSelect(structure));
  }

  updateLevelSelect(structure) {
    const genre = document.getElementById('genreSelect').value;
    const select = document.getElementById('levelSelect');
    select.innerHTML = '<option value="">-- レベル選択 --</option>';

    if (!genre) return;

    structure[genre].forEach(level => {
      const option = document.createElement('option');
      option.value = level;
      option.textContent = level;
      select.appendChild(option);
    });

    // Remove any existing listeners before adding a new one
    const newSelect = select.cloneNode(true);
    select.parentNode.replaceChild(newSelect, select);
    newSelect.addEventListener('change', () => this.loadSentences());
  }

  async loadSentences() {
    const genre = document.getElementById('genreSelect').value;
    const level = document.getElementById('levelSelect').value;

    if (!genre || !level) return;

    const response = await fetch(`/api/sentences/${genre}/${level}`);
    this.sentences = await response.json();
    this.displaySentences();
  }