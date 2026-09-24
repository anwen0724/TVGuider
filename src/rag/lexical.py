"""Persistent BM25 terms with shared query/document lexical conventions."""

import re

from rank_bm25 import BM25Okapi


def tokenize(text):
    """Preserve English identifiers and numbers, without stemming or stopwords."""
    return re.findall(r"[a-z0-9_]+", text.lower())


def rank_bm25(index, query):
    """Return only actual term matches, including zero/negative BM25 scores."""
    terms = tokenize(query)
    corpus = index["corpus"]
    if not any(corpus) or not terms:
        return []
    scores = BM25Okapi(corpus, **index["parameters"]).get_scores(terms)
    matched = set(terms)
    return sorted(
        [
            (cid, float(score))
            for cid, words, score in zip(index["ids"], corpus, scores)
            if matched.intersection(words)
        ],
        key=lambda item: (-item[1], item[0]),
    )
