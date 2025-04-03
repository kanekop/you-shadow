
from difflib import SequenceMatcher
import difflib
from utils import remove_fillers
import unicodedata

# Common number mappings
NUMBER_MAP = {
    'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
    'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9'
}

def normalize_text(text: str) -> list:
    import unicodedata
    text = text.lower()

    # Split into words and apply number mapping
    words = text.split()
    words = [NUMBER_MAP.get(word, word) for word in words]
    
    # Join back for further normalization
    text = ' '.join(words)

    # Smart quotes normalization
    smart_quotes = [''', ''', '‛', '＇']
    for quote in smart_quotes:
        text = text.replace(quote, "'")

    # Unicode normalization
    text = unicodedata.normalize("NFKC", text)

    # Clean up punctuation and spaces
    text = text.replace(", ", " ")
    text = text.replace(". ", " ")
    words = text.strip().split()
    normalized = []
    for word in words:
        word = word.strip('.,;:!?(){}[]"\'')
        if word == "im":
            word = "i'm"
        normalized.append(word)
    return normalized

def color_diff(correct_script, user_transcript):
    correct_words = normalize_text(correct_script)
    transcript_words = normalize_text(user_transcript)

    diff = list(difflib.ndiff(correct_words, transcript_words))

    print("=== Meld-style Diff ===")
    for token in diff:
        if token.startswith("- "):
            print(f"{RED}{token[2:]}{RESET}", end=" ")
        elif token.startswith("+ "):
            print(f"{GREEN}{token[2:]}{RESET}", end=" ")
        elif token.startswith("  "):
            print(token[2:], end=" ")
    print("\n")

def diff_html(correct: str, transcript: str) -> str:
    """Creates HTML diff with insert/delete spans for evaluation results"""
    correct_words = normalize_text(correct)
    transcript_words = normalize_text(transcript)

    matcher = difflib.SequenceMatcher(None, correct_words, transcript_words)
    result_html = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            result_html.append(' '.join(correct_words[i1:i2]))
        elif tag == 'replace':
            result_html.append(
                f'<span class="delete">{" ".join(correct_words[i1:i2])}</span> '
                f'<span class="insert">{" ".join(transcript_words[j1:j2])}</span>'
            )
        elif tag == 'insert':
            result_html.append(f'<span class="insert">{" ".join(transcript_words[j1:j2])}</span>')
        elif tag == 'delete':
            result_html.append(f'<span class="delete">{" ".join(correct_words[i1:i2])}</span>')

    return ' '.join(result_html)

def get_diff_html(reference: str, hypothesis: str, mode='user') -> str:
    """Creates HTML diff with insert/delete spans for shadowing view"""
    ref_words = normalize_text(remove_fillers(reference))
    hyp_words = normalize_text(remove_fillers(hypothesis))

    if mode == 'original':
        base_words = ref_words
        compare_words = hyp_words
    else:  # default 'user'
        base_words = hyp_words
        compare_words = ref_words

    sm = SequenceMatcher(None, base_words, compare_words)
    result_html = []

    for opcode, i1, i2, j1, j2 in sm.get_opcodes():
        if opcode == 'equal':
            result_html.append(' '.join(base_words[i1:i2]))
        elif opcode == 'insert':
            result_html.append(f'<span class="insert">{" ".join(compare_words[j1:j2])}</span>')
        elif opcode == 'delete':
            result_html.append(f'<span class="delete">{" ".join(base_words[i1:i2])}</span>')
        elif opcode == 'replace':
            result_html.append(
                f'<span class="delete">{" ".join(base_words[i1:i2])}</span> '
                f'<span class="insert">{" ".join(compare_words[j1:j2])}</span>'
            )

    return ' '.join(result_html)
