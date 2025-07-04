
# Diff表示機能仕様書

## 概要

Language Learning Assistantアプリケーションにおけるテキスト差分表示機能の詳細仕様です。ユーザーの発話とお手本テキストの違いを視覚的に表示し、発音・読み上げ練習の評価結果を分かりやすく提供します。

## 機能の目的

- ユーザーの音声認識結果とお手本テキストの差異を可視化
- 言語学習における発音精度の向上支援
- 間違いやすい部分の特定と改善点の明確化

## 対象機能

1. **シャドウイング練習** (`/shadowing`)
2. **カスタムシャドウイング** (`/custom-shadowing`)
3. **音読練習** (`/read-aloud`)
4. **テキスト比較** (`/compare`)

## 実装ファイル

### バックエンド
- `core/diff_viewer.py` - Diff生成ロジック
- `core/wer_utils.py` - WER計算
- `core/text_utils.py` - テキスト正規化

### フロントエンド
- `static/style.css` - Diff表示スタイル
- `templates/*.html` - 各機能のHTML表示

## Diff表示の仕様

### 1. テキスト前処理

#### 正規化処理
```python
# 実行順序
1. 小文字変換 (lower())
2. 前後空白削除 (strip())
3. フィラー語除去 (remove_fillers)
4. テキスト正規化 (normalize_text)
```

#### フィラー語除去対象
- "um", "uh", "er", "ah", "mm", "hmm"
- "you know", "like", "actually", "basically"
- "so", "well", "okay", "right"

#### 正規化処理内容
- 句読点の統一処理
- 連続空白の単一空白化
- 単語間区切りの正規化

### 2. Diff生成アルゴリズム

#### 使用ライブラリ
- `difflib.SequenceMatcher` - Python標準ライブラリ
- `difflib.ndiff` - 詳細差分表示用

#### 処理フロー
1. 両テキストを単語単位で分割
2. `SequenceMatcher`でオペレーションコード取得
3. オペレーションに基づいてHTML生成

#### オペレーションタイプ
| タイプ | 説明 | HTML出力 |
|--------|------|----------|
| `equal` | 一致 | そのまま表示 |
| `replace` | 置換 | `<span class="delete">元</span> <span class="insert">新</span>` |
| `insert` | 挿入 | `<span class="insert">追加テキスト</span>` |
| `delete` | 削除 | `<span class="delete">削除テキスト</span>` |

### 3. CSS表示スタイル

#### クラス定義
```css
.diff-result .insert {
    background-color: #ffe0e0;
    text-decoration: line-through;
    padding: 2px 4px;
    border-radius: 3px;
    display: inline;
    margin: 0 2px;
}

.diff-result .delete {
    /* 削除部分のスタイル */
    padding: 2px 4px;
    border-radius: 3px;
    display: inline;
    margin: 0 2px;
}
```

#### 表示特性
- **挿入部分**: 薄赤背景 + 取り消し線
- **削除部分**: 標準表示（デフォルトスタイル）
- **パディング**: 2px上下、4px左右
- **マージン**: 左右2px
- **角丸**: 3px

### 4. 表示モード

#### 評価結果モード (`diff_html`)
```python
def diff_html(correct: str, transcript: str) -> str
```
- **用途**: 評価結果表示
- **基準**: 正解テキスト
- **出力**: 正解との差異をHTML形式で表示

#### シャドウイング表示モード (`get_diff_html`)
```python
def get_diff_html(reference: str, hypothesis: str, mode='user') -> str
```
- **mode='user'**: ユーザー発話を基準とした差異表示
- **mode='original'**: 元テキストを基準とした差異表示

### 5. HTML出力フォーマット

#### 基本構造
```html
<div class="diff-result">
    <span class="delete">削除されたテキスト</span>
    <span class="insert">挿入されたテキスト</span>
    正常なテキスト
</div>
```

#### 評価結果表示例
```html
<div class="diff-section">
    <h4>🔍 Diff (お手本 vs あなたの発話):</h4>
    <div class="diff-result">
        <!-- 生成されたDiff HTML -->
    </div>
</div>
```

### 6. 機能別実装詳細

#### シャドウイング練習
- **ファイル**: `routes/api_routes.py` - `/api/evaluate_shadowing`
- **表示**: プリセット教材との比較
- **WER計算**: あり

#### カスタムシャドウイング
- **ファイル**: `routes/api_routes.py` - `/api/evaluate_custom_shadowing`
- **表示**: アップロードした音声の文字起こしとの比較
- **WER計算**: あり

#### 音読練習
- **ファイル**: `routes/api_routes.py` - `/api/evaluate_read_aloud`
- **表示**: 指定されたテキストとの比較
- **WER計算**: あり

#### テキスト比較
- **ファイル**: `static/js/compare.js`
- **表示**: 任意の2つのテキスト比較
- **WER計算**: あり

### 7. エラーハンドリング

#### 入力検証
- 空文字列チェック
- テキスト長制限
- 文字エンコーディング検証

#### 例外処理
- Diff生成失敗時のフォールバック表示
- HTMLエスケープ処理
- 不正なオペレーションコードの処理

### 8. パフォーマンス考慮事項

#### 最適化ポイント
- 長文テキストの分割処理
- メモリ使用量の制限
- レスポンス時間の最適化

#### 制限事項
- 最大テキスト長: 10,000文字
- 処理タイムアウト: 30秒
- 同時処理数制限

### 9. 今後の拡張予定

#### 機能追加案
- 音声波形との同期表示
- 詳細なエラー分析レポート
- カスタマイズ可能な表示スタイル
- 多言語対応

#### 改善予定
- より精密なテキスト正規化
- 機械学習ベースの差異分析
- リアルタイム差分表示

---

## 更新履歴

| 日付 | 版数 | 更新内容 |
|------|------|----------|
| 2025-07-04 | 1.0 | 初版作成 |
