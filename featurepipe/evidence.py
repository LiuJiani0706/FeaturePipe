"""Deterministic checks that complement, rather than replace, editorial review."""

import re


def quote_audit(article, materials):
    """Check whether each marked direct quotation occurs in one source.

    An exact match establishes textual presence only, not speaker attribution.
    Unmatched quotations may be edited quotes, headings, or unsupported text.
    """
    normalize = lambda text: re.sub(r"\s+", "", text)
    sources = [(source["id"], normalize(source["text"])) for source in materials]
    quotes = []
    for match in re.finditer(r'“([^”\n]+)”|「([^」\n]+)」', article):
        text = match.group(1) or match.group(2)
        found = [source_id for source_id, source in sources if normalize(text) in source]
        # Chinese quotations followed by a speech tag often change the final 。 to ，.
        body = normalize(text).rstrip('，。！？!?；;：:、')
        adjusted = [source_id for source_id, source in sources if body and body in source]
        quotes.append({"quote": text, "offset": match.start(), "exact_source_ids": found, "end_punctuation_adjusted_source_ids": adjusted})
    return {
        "chinese_chars": len(re.findall(r"[\u4e00-\u9fff]", article)),
        "marked_quotes": len(quotes),
        "unmatched_quotes": sum(not quote["exact_source_ids"] for quote in quotes),
        "unmatched_after_end_punctuation_adjustment": sum(not quote["end_punctuation_adjusted_source_ids"] for quote in quotes),
        "quotes": quotes,
        "scope": "literal-text-presence-only; does not verify attribution or unquoted claims",
    }
