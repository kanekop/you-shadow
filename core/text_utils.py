
# core/text_utils.py
import re
import unicodedata

NUMBER_MAP = {
    'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
    'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9'
}

FILLER_WORDS = {
    "uh", "um", "you know", "like", "i mean", "you see",
    "well", "so", "basically", "actually", "literally",
    "kind of", "sort of", "you know what i mean"
}

def remove_fillers(text: str) -> str:
    tokens = text.lower().split()
    return ' '.join([t for t in tokens if t not in FILLER_WORDS])

def normalize_text(text: str) -> list:
    if not isinstance(text, str):
        return []
    text = unicodedata.normalize('NFKC', text)
    text = text.lower()

    words = text.split()
    normalized_words = []

    i = 0
    while i < len(words):
        word = words[i]
        word = NUMBER_MAP.get(word, word)

        if word == "gen" and i + 1 < len(words) and words[i + 1].isdigit():
            normalized_words.append("genre")
            normalized_words.append(words[i + 1])
            i += 1
        elif word.startswith("genre") and len(word) > 5 and word[5:].isdigit():
            normalized_words.append("genre")
            normalized_words.append(word[5:])
        elif word == "im":
            normalized_words.append("i'm")
        else:
            cleaned_word = re.sub(r'[^\w\s\']', '', word)
            cleaned_word = cleaned_word.strip('.,;:!?(){}[]"\'')
            if cleaned_word:
                normalized_words.append(cleaned_word)
        i += 1

    final_text = ' '.join(normalized_words)
    final_text = re.sub(r'\s+', ' ', final_text).strip()
    return final_text.split() if final_text else []
