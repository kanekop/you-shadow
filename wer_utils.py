import numpy as np
import re

def normalize_text(text):
    """
    テキストを正規化：
    - 小文字化
    - 句読点の除去
    - 単語のリストに変換
    """
    if isinstance(text, list):  # すでにトークンリストならスルー
        return text
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    return text.strip().split()

def wer(reference, hypothesis):
    """
    Word Error Rate (WER) を計算
    引数:
        reference: 正しいスクリプト (str or list)
        hypothesis: 認識結果 (str or list)
    戻り値:
        wer_percent: WER (%)
        S: 置換数
        D: 削除数
        I: 挿入数
        N: 正解単語数
    """
    r = normalize_text(reference)
    h = normalize_text(hypothesis)

    rows = len(r) + 1
    cols = len(h) + 1
    d = np.zeros((rows, cols), dtype=np.uint16)

    for i in range(rows):
        d[i][0] = i
    for j in range(cols):
        d[0][j] = j

    for i in range(1, rows):
        for j in range(1, cols):
            cost = 0 if r[i-1] == h[j-1] else 1
            d[i][j] = min(
                d[i-1][j] + 1,      # 削除
                d[i][j-1] + 1,      # 挿入
                d[i-1][j-1] + cost  # 置換
            )

    i, j = len(r), len(h)
    S = D = I = 0
    while i > 0 and j > 0:
        if r[i-1] == h[j-1]:
            i -= 1
            j -= 1
        elif d[i][j] == d[i-1][j-1] + 1:
            S += 1
            i -= 1
            j -= 1
        elif d[i][j] == d[i-1][j] + 1:
            D += 1
            i -= 1
        elif d[i][j] == d[i][j-1] + 1:
            I += 1
            j -= 1
        else:
            break

    # 残りの処理
    D += i
    I += j

    N = len(r)
    wer_percent = ((S + D + I) / N) * 100 if N > 0 else 0
    return wer_percent, S, D, I, N

def calculate_wer(reference, hypothesis):
    wer_percent, _, _, _, _ = wer(reference, hypothesis)
    return wer_percent / 100.0  # 小数にして返す
