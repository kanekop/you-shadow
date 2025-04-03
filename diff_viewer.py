from difflib import SequenceMatcher
import difflib
from utils import remove_fillers

# ANSIカラー定義（赤 = 削除, 緑 = 追加, リセット）
RED = "\033[91m"
GREEN = "\033[92m"
RESET = "\033[0m"

def color_diff(correct_script, user_transcript):
    correct_words = correct_script.strip().split()
    transcript_words = user_transcript.strip().split()

    diff = list(difflib.ndiff(correct_words, transcript_words))

    print("=== Meld-style Diff ===")
    for token in diff:
        if token.startswith("- "):
            print(f"{RED}{token[2:]}{RESET}", end=" ")
        elif token.startswith("+ "):
            print(f"{GREEN}{token[2:]}{RESET}", end=" ")
        elif token.startswith("  "):
            print(token[2:], end=" ")
        # '? '（違いの位置）は表示しない
    print("\n")

def normalize_for_diff(text: str) -> list:
    """Normalize text for diff display by handling case and punctuation"""
    # Convert to lowercase first
    text = text.lower()
    # Standardize contractions
    text = text.replace("i'm", "im")
    # Handle punctuation after commas and periods
    text = text.replace(", ", " ")
    text = text.replace(". ", " ")
    # Split and strip remaining punctuation
    words = text.strip().split()
    # Normalize each word
    normalized = []
    for word in words:
        word = word.strip('.,;:!?')
        # Re-add standard contractions
        if word == "im":
            word = "i'm"
        normalized.append(word)
    return normalized

def diff_html(correct: str, transcript: str) -> str:
    """Creates HTML diff with insert/delete spans for evaluation results"""
    correct_words = normalize_for_diff(correct)
    transcript_words = normalize_for_diff(transcript)

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
    ref_words = remove_fillers(reference).split()
    hyp_words = remove_fillers(hypothesis).split()

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