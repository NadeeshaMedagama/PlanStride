LIKE_ESCAPE = "\\"


def contains_pattern(term: str) -> str:
    """An ILIKE pattern matching `term` anywhere, with LIKE wildcards in the
    term escaped so a search for "50%" matches literally. Use with
    `escape=LIKE_ESCAPE`."""
    escaped = (
        term.strip()
        .replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
        .replace("%", f"{LIKE_ESCAPE}%")
        .replace("_", f"{LIKE_ESCAPE}_")
    )
    return f"%{escaped}%"
