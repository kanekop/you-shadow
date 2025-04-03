
class SentencePractice {
  constructor() {
    console.log('🏗️ Initializing SentencePractice');
    this.sentences = [];
    this.currentSentenceIndex = 0;
    this.structure = null;
    this.isLoading = false;
    this.loadGenres();
    this.setupEventListeners();
  }

  setupEventListeners() {
    console.log('🎯 Setting up event listeners');
    const genreSelect = document.getElementById('genreSelect');
    const levelSelect = document.getElementById('levelSelect');
    const modeSelect = document.getElementById('practiceMode');

    if (!genreSelect || !levelSelect || !modeSelect) {
      console.error('❌ Failed to find required select elements');
      return;
    }

    // Disable selects initially until data is loaded
    levelSelect.disabled = true;
    modeSelect.disabled = true;

    genreSelect.addEventListener('change', (e) => {
      console.log('📢 Genre changed:', e.target.value);
      this.updateLevelSelect();
    });

    levelSelect.addEventListener('change', (e) => {
      console.log('📢 Level changed:', e.target.value);
      if (e.target.value) {
        modeSelect.disabled = false;
        this.loadSentences();
      }
    });
  }

  async loadGenres() {
    console.log('📚 Loading genres...');
    this.isLoading = true;
    try {
      const response = await fetch('/api/sentence_structure');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const structure = await response.json();
      console.log('📦 Loaded structure:', structure);
      this.structure = structure;
      this.displayGenreSelect();
    } catch (error) {
      console.error('❌ Error loading genres:', error);
    } finally {
      this.isLoading = false;
    }
  }

  displayGenreSelect() {
    console.log('🎨 Displaying genre select');
    const select = document.getElementById('genreSelect');
    if (!select) {
      console.error('❌ Genre select element not found');
      return;
    }
    
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
