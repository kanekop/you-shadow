
from difflib import SequenceMatcher
import difflib
from utils import remove_fillers, normalize_text



def color_diff(correct_script, user_transcript):
    # First normalize, then remove fillers
    correct_words = normalize_text(correct_script.lower().strip())
    transcript_words = normalize_text(user_transcript.lower().strip())
    
    # Remove fillers after normalization
    correct_words = normalize_text(remove_fillers(' '.join(correct_words)))
    transcript_words = normalize_text(remove_fillers(' '.join(transcript_words)))

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
    correct_words = normalize_text(correct.lower().strip())
    transcript_words = normalize_text(transcript.lower().strip())
    
    # Remove fillers after normalization
    correct_words = normalize_text(remove_fillers(' '.join(correct_words)))
    transcript_words = normalize_text(remove_fillers(' '.join(transcript_words)))

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
