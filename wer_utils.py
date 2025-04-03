
import numpy as np
import re
from utils import remove_fillers

# Common number mappings and speech variations
NUMBER_MAP = {
    'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
    'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9'
}

PUNCTUATION_CHARS = '.!?,;:-'

def normalize_text(text):
    """
    Enhanced text normalization with speech-friendly rules
    """
    if isinstance(text, list):
        return text
        
    # Convert to lowercase
    text = text.lower()
    
    # Remove multiple spaces
    text = ' '.join(text.split())
    
    # Handle punctuation more carefully
    for char in PUNCTUATION_CHARS:
        text = text.replace(char, ' ')
    
    # Normalize common contractions
    text = text.replace("'m", " am")
    text = text.replace("'re", " are")
    text = text.replace("'s", " is")
    text = text.replace("'ll", " will")
    text = text.replace("'ve", " have")
    text = text.replace("'d", " would")
    text = text.replace("n't", " not")
    
    # Remove any remaining non-word characters
    text = re.sub(r'[^\w\s]', '', text)
    
    words = text.strip().split()
    
    # Apply number normalization
    normalized = []
    for word in words:
        if word in NUMBER_MAP:
            word = NUMBER_MAP[word]
        normalized.append(word)
    
    return normalized

def wer(reference, hypothesis):
    """
    Word Error Rate (WER) calculation with enhanced normalization
    """
    # Apply filler removal
    reference = remove_fillers(reference)
    hypothesis = remove_fillers(hypothesis)
    
    # Normalize both texts
    r = normalize_text(reference)
    h = normalize_text(hypothesis)

    # Calculate Levenshtein distance matrix
    rows = len(r) + 1
    cols = len(h) + 1
    d = np.zeros((rows, cols), dtype=np.uint16)

    for i in range(rows):
        d[i][0] = i
    for j in range(cols):
        d[0][j] = j

    for i in range(1, rows):
        for j in range(1, cols):
            # Consider words equal if they're similar enough
            cost = 0 if r[i-1] == h[j-1] else 1
            d[i][j] = min(
                d[i-1][j] + 1,      # deletion
                d[i][j-1] + 1,      # insertion
                d[i-1][j-1] + cost  # substitution
            )

    # Count operations
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

    D += i
    I += j

    N = len(r)
    wer_percent = ((S + D + I) / N) * 100 if N > 0 else 0
    return wer_percent, S, D, I, N

def calculate_wer(reference, hypothesis):
    wer_percent, _, _, _, _ = wer(reference, hypothesis)
    return wer_percent / 100.0  # Return as decimal
