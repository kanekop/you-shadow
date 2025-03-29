import difflib

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

