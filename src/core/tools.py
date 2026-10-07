"""The Qloo operations, described so a model can decide when to call them.

Each entry pairs a declaration Gemini sees with the python that runs it. The
descriptions are doing real work here: everything we learned the hard way about
how Qloo behaves is written into them, because the model only knows what these
say. Vague descriptions give you a model that calls search on a cuisine, or asks
for places without a category and gets shopping malls back.
"""
from __future__ import annotations

from . import qloo

CATEGORIES = {
    "restaurant": qloo.CAT_RESTAURANT,
    "bar": qloo.CAT_BAR,
    "cafe": qloo.CAT_CAFE,
    "live_music": qloo.CAT_LIVE_MUSIC,
}

ENTITY_TYPES = {
    "artist": qloo.ARTIST,
    "movie": qloo.MOVIE,
    "book": qloo.BOOK,
    "place": qloo.PLACE,
}


def resolve_taste(name: str, kind: str = "artist", city: str | None = None) -> dict:
    """Look up a named thing and hand back its Qloo id."""
    hit = qloo.search_entity(name, ENTITY_TYPES.get(kind, qloo.ARTIST), city)
    if not hit:
        return {"found": False, "name": name}
    return {"found": True, **qloo.summarize(hit)}


def find_tag(text: str) -> dict:
    """Turn a cuisine or genre word into a Qloo tag id."""
    tag = qloo.find_tag(text)
    if not tag or not tag.get("id"):
        return {"found": False, "query": text}
    return {"found": True, "name": tag.get("name") or text, "tag_id": tag["id"]}


def places(city: str, category: str, entity_ids: list[str] | None = None,
           signal_tags: list[str] | None = None, cuisine_tag: str | None = None,
           take: int = 8) -> dict:
    """Places in a city that suit a taste."""
    rows = qloo.insights(
        filter_type=qloo.PLACE, city=city,
        entity_ids=entity_ids, signal_tags=signal_tags,
        # A cuisine tag replaces the category rather than joining it. Qloo returns
        # junk if you stack tags from different families.
        filter_tag=cuisine_tag or CATEGORIES.get(category, qloo.CAT_RESTAURANT),
        take=take)
    return {"count": len(rows), "results": [qloo.summarize(r) for r in rows]}


def culture(kind: str, entity_ids: list[str] | None = None,
            signal_tags: list[str] | None = None, genre_tag: str | None = None,
            take: int = 6) -> dict:
    """Artists, films or books connected to a taste."""
    rows = qloo.insights(
        filter_type=ENTITY_TYPES.get(kind, qloo.ARTIST),
        entity_ids=entity_ids, signal_tags=signal_tags,
        filter_tag=genre_tag, take=take)
    return {"count": len(rows), "results": [qloo.summarize(r) for r in rows]}


HANDLERS = {
    "resolve_taste": resolve_taste,
    "find_tag": find_tag,
    "places": places,
    "culture": culture,
}

DECLARATIONS = [{"functionDeclarations": [
    {
        "name": "resolve_taste",
        "description": (
            "Look up something the person named - a musician, a film, a book, a venue - "
            "and get its Qloo id. Call this before asking for recommendations, because "
            "the other tools want ids, not names. Only use it for proper names. For a "
            "cuisine or a genre like 'qawwali' or 'Kashmiri', use find_tag instead."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "name": {"type": "STRING", "description": "the name as the person wrote it"},
                "kind": {"type": "STRING", "enum": ["artist", "movie", "book", "place"]},
                "city": {"type": "STRING",
                         "description": "only for kind=place, to avoid matching a "
                                        "same-named venue on another continent"},
            },
            "required": ["name", "kind"],
        },
    },
    {
        "name": "find_tag",
        "description": (
            "Turn a cuisine or a music genre into a Qloo tag id. Use it for words like "
            "'Kashmiri', 'street food', 'qawwali', 'ghazal'. These are categories rather "
            "than named things, so resolve_taste will not find them."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {"text": {"type": "STRING"}},
            "required": ["text"],
        },
    },
    {
        "name": "places",
        "description": (
            "Places in a city that suit a taste. Pass entity ids from resolve_taste, or "
            "tag ids from find_tag, or both. Always pick a category: 'restaurant' and "
            "'bar' and 'cafe' and 'live_music'. Without one Qloo returns shopping malls "
            "and monuments. For a specific cuisine pass cuisine_tag instead of relying on "
            "the category, and do not pass both. Call it once per category you want."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "city": {"type": "STRING"},
                "category": {"type": "STRING",
                             "enum": ["restaurant", "bar", "cafe", "live_music"]},
                "entity_ids": {"type": "ARRAY", "items": {"type": "STRING"}},
                "signal_tags": {"type": "ARRAY", "items": {"type": "STRING"},
                                "description": "tag ids to shape the results, e.g. a genre"},
                "cuisine_tag": {"type": "STRING",
                                "description": "a cuisine tag id, used instead of category"},
            },
            "required": ["city", "category"],
        },
    },
    {
        "name": "culture",
        "description": (
            "Artists, films or books connected to a taste. Two different questions "
            "depending on what you pass. genre_tag gives you things that ARE that genre: "
            "the qawwali tag returns Nusrat Fateh Ali Khan and the Sabri Brothers. "
            "signal_tags or entity_ids give you what people with that taste also like, "
            "which is a different and usually more surprising list. Use whichever the "
            "person is actually asking for, or call it twice."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "kind": {"type": "STRING", "enum": ["artist", "movie", "book"]},
                "entity_ids": {"type": "ARRAY", "items": {"type": "STRING"}},
                "signal_tags": {"type": "ARRAY", "items": {"type": "STRING"}},
                "genre_tag": {"type": "STRING"},
            },
            "required": ["kind"],
        },
    },
]}]


def run(name: str, args: dict) -> dict:
    """Execute one call the model asked for. Errors come back as data, not exceptions,
    so the model can read what went wrong and try something else."""
    handler = HANDLERS.get(name)
    if not handler:
        return {"error": f"no tool called {name}"}
    try:
        return handler(**args)
    except qloo.QlooError as exc:
        return {"error": str(exc)}
    except TypeError as exc:
        return {"error": f"wrong arguments for {name}: {exc}"}
