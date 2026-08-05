"""indic-reg-bench: an open benchmark for Indian regulatory document understanding."""

from .adapter import System, load_system
from .numerals import parse_amount, words_to_number
from .scoring import (score_abstention, score_extraction, score_labels,
                      score_numeric, normalise_name)

__version__ = "0.1.0"
__all__ = [
    "System", "load_system", "parse_amount", "words_to_number",
    "score_abstention", "score_extraction", "score_labels", "score_numeric",
    "normalise_name",
]
