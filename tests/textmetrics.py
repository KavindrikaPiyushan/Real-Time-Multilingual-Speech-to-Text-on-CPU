"""Text error metrics shared by the test scripts (no model/torch imports)."""
import re

import jiwer


def normalise(s: str) -> str:
    """Lowercase and strip punctuation, so only the words are compared."""
    return re.sub(r"[^\w\s]", "", s.lower()).strip()


def error_rate(ref: str, hyp: str, metric: str) -> float | None:
    """WER for word-based languages, CER (spaces ignored) for Chinese."""
    ref, hyp = normalise(ref), normalise(hyp)
    if not ref:
        return None
    if metric == "CER":
        return jiwer.cer(ref.replace(" ", ""), hyp.replace(" ", ""))
    return jiwer.wer(ref, hyp)
