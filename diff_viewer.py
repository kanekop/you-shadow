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

import difflib

def diff_html(correct: str, transcript: str) -> str:
    correct_words = correct.strip().split()
    transcript_words = transcript.strip().split()

    matcher = difflib.SequenceMatcher(None, correct_words, transcript_words)
    result_html = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            for word in correct_words[i1:i2]:
                result_html.append(f'<span>{word} </span>')
        elif tag == 'replace':
            for word in transcript_words[j1:j2]:
                result_html.append(f'<span style="color: red;">{word} </span>')
        elif tag == 'insert':
            for word in transcript_words[j1:j2]:
                result_html.append(f'<span style="color: green;">{word} </span>')
        elif tag == 'delete':
            for word in correct_words[i1:i2]:
                result_html.append(f'<span style="color: orange; text-decoration: line-through;">{word} </span>')

    return ''.join(result_html)


def get_diff_html(reference: str, hypothesis: str, mode='user') -> str:
    ref_words = remove_fillers(reference).split()
    hyp_words = remove_fillers(hypothesis).split()

    if mode == 'original':
        base_words = ref_words
        compare_words = hyp_words
    else:  # default 'user'
        base_words = hyp_words
        compare_words = ref_words

    sm = SequenceMatcher(None, base_words, compare_words)
    result_html = ""
    for opcode, i1, i2, j1, j2 in sm.get_opcodes():
        if opcode == 'equal':
            result_html += ' ' + ' '.join(base_words[i1:i2])
        elif opcode == 'insert':
            result_html += ' <span class="insert">' + ' '.join(compare_words[j1:j2]) + '</span>'
        elif opcode == 'delete':
            result_html += ' <span class="delete">' + ' '.join(base_words[i1:i2]) + '</span>'
        elif opcode == 'replace':
            result_html += (
                ' <span class="delete">' + ' '.join(base_words[i1:i2]) + '</span>' +
                ' <span class="insert">' + ' '.join(compare_words[j1:j2]) + '</span>'
            )
    return result_html.strip()
