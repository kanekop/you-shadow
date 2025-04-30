
import numpy as np
from typing import Tuple, List, Union

class WERCalculator:
    def __init__(self):
        self.number_map = {
            'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
            'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9'
        }

    def normalize_text(self, text: Union[str, List[str]]) -> List[str]:
        if isinstance(text, list):
            return text
            
        words = text.lower().split()
        return [self.number_map.get(word, word) for word in words]

    def calculate(self, reference: str, hypothesis: str) -> Tuple[float, int, int, int, int]:
        """
        Calculate Word Error Rate and related metrics
        Returns: (wer_percent, substitutions, deletions, insertions, word_count)
        """
        r = self.normalize_text(reference)
        h = self.normalize_text(hypothesis)

        d = np.zeros((len(r) + 1, len(h) + 1), dtype=np.uint16)
        d[:, 0] = np.arange(len(r) + 1)
        d[0, :] = np.arange(len(h) + 1)

        for i in range(1, len(r) + 1):
            for j in range(1, len(h) + 1):
                cost = 0 if r[i-1] == h[j-1] else 1
                d[i, j] = min(d[i-1, j] + 1,      # deletion
                            d[i, j-1] + 1,      # insertion
                            d[i-1, j-1] + cost) # substitution

        return self._count_operations(d, r, h)

    def _count_operations(self, d: np.ndarray, r: List[str], h: List[str]) -> Tuple[float, int, int, int, int]:
        i, j = len(r), len(h)
        s = d = i = 0
        
        while i > 0 and j > 0:
            if r[i-1] == h[j-1]:
                i -= 1
                j -= 1
            elif d[i][j] == d[i-1][j-1] + 1:
                s += 1  # substitution
                i -= 1
                j -= 1
            elif d[i][j] == d[i-1][j] + 1:
                d += 1  # deletion
                i -= 1
            elif d[i][j] == d[i][j-1] + 1:
                i += 1  # insertion
                j -= 1

        d += i
        i += j
        
        n = len(r)
        wer_percent = ((s + d + i) / n) * 100 if n > 0 else 0
        return wer_percent, s, d, i, n
