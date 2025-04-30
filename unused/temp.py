from wer_utils import wer

ref = "I think what you said is totally out of scope."
hyp = "I rather think what you said is TOTally out of speech."

wer_percent, S, D, I, N = wer(ref, hyp)

print(f"WER: {wer_percent:.2f}%")
print(f"S: {S}, D: {D}, I: {I}, N: {N}")
