#!/bin/bash

# ルートディレクトリに presets を作成
mkdir -p presets

# ジャンルの数（例：3）
for genre_num in {1..3}; do
  genre_name="genre$genre_num"
  mkdir -p "presets/$genre_name"

  # 各ジャンルに 10 レベル作成
  for level in {1..10}; do
    level_dir="presets/$genre_name/level$level"
    mkdir -p "$level_dir"

    # ダミーファイルを追加
    echo "This is sample script text for $genre_name level $level." > "$level_dir/script.txt"
    touch "$level_dir/audio.mp3"  # 空のダミー音声ファイル
  done
done

echo "✅ /presets ディレクトリ構造を作成しました。"
