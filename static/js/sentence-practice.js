
class SentencePractice {
  constructor() {
    this.sentences = [];
    this.currentSentenceIndex = 0;
    this.loadGenres();
    this.setupEventListeners();
  }

  setupEventListeners() {
    const genreSelect = document.getElementById('genreSelect');
    const levelSelect = document.getElementById('levelSelect');

    genreSelect.addEventListener('change', () => {
      this.updateLevelSelect();
    });

    levelSelect.addEventListener('change', () => {
      this.loadSentences();
    });
  }

  async loadGenres() {
    try {
      const response = await fetch('/api/sentence_structure');
      const structure = await response.json();
      this.structure = structure;
      this.displayGenreSelect();
    } catch (error) {
      console.error('Error loading genres:', error);
    }
  }

  displayGenreSelect() {
    const select = document.getElementById('genreSelect');
    select.innerHTML = '<option value="">-- ジャンル選択 --</option>';
    select.style.backgroundColor = '#fff';
    select.style.color = '#000';

    for (const genre in this.structure) {
      const option = document.createElement('option');
      option.value = genre;
      option.textContent = genre;
      select.appendChild(option);
    }
  }

  updateLevelSelect() {
    const genre = document.getElementById('genreSelect').value;
    const select = document.getElementById('levelSelect');
    select.innerHTML = '<option value="">-- レベル選択 --</option>';
    select.style.backgroundColor = '#fff';
    select.style.color = '#000';

    if (!genre || !this.structure[genre]) return;

    this.structure[genre].forEach(level => {
      const option = document.createElement('option');
      option.value = level;
      option.textContent = level;
      select.appendChild(option);
    });
  }

  async loadSentences() {
    const genre = document.getElementById('genreSelect').value;
    const level = document.getElementById('levelSelect').value;

    if (!genre || !level) return;

    try {
      const response = await fetch(`/api/sentences/${genre}/${level}`);
      this.sentences = await response.json();
      this.displaySentences();
    } catch (error) {
      console.error('Error loading sentences:', error);
    }
  }

  displaySentences() {
    // Display logic will go here
    console.log("Loaded sentences:", this.sentences);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  new SentencePractice();
  
  // Style mode select as well
  const modeSelect = document.getElementById('practiceMode');
  if (modeSelect) {
    modeSelect.style.backgroundColor = '#fff';
    modeSelect.style.color = '#000';
  }
});
