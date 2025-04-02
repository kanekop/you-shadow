
export export class PresetManager {
  constructor() {
    this.presetData = {};
    this.currentGenre = "";
    this.currentLevel = "";
  }

  async fetchPresets() {
    const res = await fetch("/api/presets");
    this.presetData = await res.json();
    return this.presetData;
  }

  async loadPreset(genre, level) {
    if (!genre || !level) return null;
    
    const audioUrl = `/presets/${genre}/${level}/audio.mp3`;
    const scriptUrl = `/presets/${genre}/${level}/script.txt`;

    const audioBlob = await fetch(audioUrl).then(res => res.blob());
    const script = await fetch(scriptUrl).then(res => res.text());

    this.currentGenre = genre;
    this.currentLevel = level;

    return { audioBlob, script };
  }

  async fetchHighestLevels(username) {
    const res = await fetch(`/api/highest_levels/${username}`);
    return await res.json();
  }
}
