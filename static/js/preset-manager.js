class PresetManager {
  constructor() {
    this.presetData = {};
    this.currentGenre = "";
    this.currentLevel = "";
  }

  async fetchPresets() {
    const response = await fetch('/api/presets');
    return await response.json();
  }

  async loadPreset(genre, level) {
    if (!genre || !level) return null;

    const audioUrl = `/presets/shadowing/${genre}/${level}/audio.mp3`;
    const scriptUrl = `/presets/shadowing/${genre}/${level}/script.txt`;

    const audioBlob = await fetch(audioUrl).then(res => res.blob());
    const script = await fetch(scriptUrl).then(res => res.text());

    this.currentGenre = genre;
    this.currentLevel = level;

    return { audioBlob, script };
  }

  async fetchHighestLevels(username) {
    const response = await fetch(`/api/highest_levels/${username}`);
    return await response.json();
  }
}

// Make PresetManager available globally
window.PresetManager = PresetManager;