import numpy as np
import re
from utils import remove_fillers
import difflib

# Common number mappings and speech variations
NUMBER_MAP = {
    'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
    'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9'
}

def normalize_text(text):
    """
    Enhanced text normalization with number mapping
    """
    if isinstance(text, list):
        return text

    # Convert to lowercase
    text = text.lower()

    # Split into words
    words = text.split()

    # Apply number mapping
    words = [NUMBER_MAP.get(word, word) for word in words]

    # Join back and normalize
    text = ' '.join(words)

    # Remove punctuation
    text = re.sub(r'[^\w\s]', '', text)

    # Remove multiple spaces and trim
    text = ' '.join(text.split())

    return text.split()

def strip_punct(word):
    return ''.join(c for c in word if c not in '.!?,;:-')

def wer(reference, hypothesis, lenient=False):
    """
    Calculate WER and related metrics
    """
    # Remove fillers first, then normalize
    reference = remove_fillers(reference)
    hypothesis = remove_fillers(hypothesis)

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
            r_word = strip_punct(r[i-1]).lower()
            h_word = strip_punct(h[j-1]).lower()

            if lenient:
                ratio = difflib.SequenceMatcher(None, r_word, h_word).ratio()
                cost = 0 if ratio >= 0.85 else 1
            else:
                cost = 0 if r_word == h_word else 1

            d[i][j] = min(
                d[i-1][j] + 1,      # deletion
                d[i][j-1] + 1,      # insertion
                d[i-1][j-1] + cost  # substitution
            )

    i, j = len(r), len(h)
    S = D = I = 0

    while i > 0 and j > 0:
        if r[i-1] == h[j-1] or (lenient and difflib.SequenceMatcher(None, r[i-1], h[j-1]).ratio() >= 0.85):
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

    D += i
    I += j

    N = len(r)
    wer_percent = ((S + D + I) / N) * 100 if N > 0 else 0
    return wer_percent, S, D, I, N

def calculate_wer(reference, hypothesis, lenient=False):
    """
    Return WER score as decimal (0.0 - 1.0)
    """
    wer_percent, _, _, _, _ = wer(reference, hypothesis, lenient)
    return wer_percent / 100.0