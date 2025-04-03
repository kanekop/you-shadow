# 共通のフィルター処理
FILLER_WORDS = {
    "uh", "um", "you know", "like", "i mean", "you see", 
    "well", "so", "basically", "actually", "literally",
    "kind of", "sort of", "you know what i mean"
}

def remove_fillers(text: str) -> str:
    tokens = text.lower().split()
    return ' '.join([t for t in tokens if t not in FILLER_WORDS])
