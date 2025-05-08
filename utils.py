# utils.py
import re # re を normalize_text で使うのであればインポート
import unicodedata # normalize_text で使うのであればインポート

NUMBER_MAP = {
    'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
    'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9'
    # 他の必要なマッピングがあれば追加
}

FILLER_WORDS = {
    "uh", "um", "you know", "like", "i mean", "you see",
    "well", "so", "basically", "actually", "literally",
    "kind of", "sort of", "you know what i mean"
}

def remove_fillers(text: str) -> str:
    # FILLER_WORDS をこのファイル内の定義から参照
    tokens = text.lower().split()
    # 完全一致だけでなく、句読点を含むフィラーワードも考慮するなら、
    # ここでトークンごとに句読点除去を行うか、FILLER_WORDSの定義を工夫する必要がある
    # シンプルな実装としては現状のままで、正規化後に行うのが一般的
    return ' '.join([t for t in tokens if t not in FILLER_WORDS])

def normalize_text(text: str) -> list:
    if not isinstance(text, str): # ガード処理
        return []
    text = unicodedata.normalize('NFKC', text) # Unicode正規化を追加するとより堅牢
    text = text.lower()

    words = text.split()
    normalized_words = []

    i = 0
    while i < len(words):
        word = words[i]

        # NUMBER_MAP をこのファイル内の定義から参照
        word = NUMBER_MAP.get(word, word)

        # "gen 1" -> "genre 1" のような処理 (diff_viewer.py から)
        if word == "gen" and i + 1 < len(words) and words[i + 1].isdigit():
            normalized_words.append("genre")
            normalized_words.append(words[i + 1])
            i += 1 # 次の単語も処理したのでスキップ
        # "genre1" -> "genre 1" のような処理 (より一般的に)
        elif word.startswith("genre") and len(word) > 5 and word[5:].isdigit():
            normalized_words.append("genre")
            normalized_words.append(word[5:])
        # "im" -> "i'm" (diff_viewer.py から)
        elif word == "im":
            normalized_words.append("i'm")
        else:
            # 句読点の除去 (単語ごとに行う)
            # \w は英数字とアンダースコアにマッチ, \s は空白文字にマッチ
            # これだとハイフンなども除去されるので、要件に応じて調整
            cleaned_word = re.sub(r'[^\w\s\']', '', word) # アポストロフィは保持する例
            # さらに不要な句読点を strip で除去
            cleaned_word = cleaned_word.strip('.,;:!?(){}[]"\'')
            if cleaned_word: # 空文字列でなければ追加
                normalized_words.append(cleaned_word)
        i += 1

    # 最終的にリストではなくスペースで結合した文字列を返し、それを split する方が
    # wer_utils.py の既存の使われ方と互換性があるかもしれない
    # ここではリストを返す想定で進める (呼び出し側で .split() するか、この関数で .split() するか)
    # wer_utils.py の normalize_text は .split() したリストを返しているので、それに合わせる

    # 最終的なクリーニング (連続する空白など)
    final_text = ' '.join(normalized_words)
    final_text = re.sub(r'\s+', ' ', final_text).strip() # 連続空白を一つにし、前後の空白除去
    return final_text.split() if final_text else [] # 空文字列の場合は空リストを返す