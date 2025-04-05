
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
    normalized = []
    
    for i, word in enumerate(words):
        # Handle number mapping
        word = NUMBER_MAP.get(word, word)
        
        # Handle genre variations
        if word == "gen" and i + 1 < len(words) and words[i + 1].isdigit():
            word = "genre"
        elif word.startswith("genre"):
            word = "genre"
            
        # Clean punctuation
        word = word.strip('.,;:!?(){}[]"\'')
        
        # Special cases
        if word == "im":
            word = "i'm"
            
        normalized.append(word)

    return normalized

def color_diff(correct_script, user_transcript):
    correct_words = normalize_text(remove_fillers(correct_script.lower().strip()))
    transcript_words = normalize_text(remove_fillers(user_transcript.lower().strip()))

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
    # Clean up and normalize before diff
    ref_words = normalize_text(remove_fillers(reference.lower().strip()))
    hyp_words = normalize_text(remove_fillers(hypothesis.lower().strip()))

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
