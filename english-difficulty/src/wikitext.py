"""Turn MediaWiki source into the lines a player would hear.

Fandom transcript pages are not prose. They are dialogue wrapped in templates,
links, tables and editorial notes, and every wiki writes them slightly
differently. This module handles the markup; `clean.py` handles what is left.
"""
from __future__ import annotations

import re

# Templates that carry dialogue, mapped to the positional parameter holding it.
# Everything else is furniture and gets dropped whole.
DIALOGUE_TEMPLATES = {
    "quote": 1,
    "quotation": 1,
    "cquote": 1,
    "dialogue": 1,
    "line": 1,
    "speech": 1,
    "transcript": 1,
}

# Removed with their contents: these never contain spoken English.
DROP_BLOCKS = [
    re.compile(r"<!--.*?-->", re.S),
    re.compile(r"<ref[^>]*>.*?</ref>", re.S | re.I),
    re.compile(r"<ref[^>]*/>", re.I),
    re.compile(r"<gallery[^>]*>.*?</gallery>", re.S | re.I),
    re.compile(r"<table[^>]*>.*?</table>", re.S | re.I),
    re.compile(r"<score[^>]*>.*?</score>", re.S | re.I),
    re.compile(r"<syntaxhighlight[^>]*>.*?</syntaxhighlight>", re.S | re.I),
]

# Sections that hold spoken lines. Everything else on a cutscene page is prose
# the wiki's editors wrote — a plot summary is encyclopedic register, and
# measuring it would measure the editors rather than the game.
SPOKEN_SECTION = re.compile(r"transcript|dialogue|dialog|script|quotes?|"
                            r"conversation|lines", re.I)
SECTION_HEADING = re.compile(r"^[ \t]*(={2,})[ \t]*(.*?)[ \t]*\1[ \t]*$", re.M)

# A <tabber> holds the same scene more than once: Resident Evil pages carry the
# official localisation beside a literal retranslation of the Japanese script.
# Keeping both would count every line twice, in two different Englishes, only
# one of which was ever in the game.
TABBER = re.compile(r"<tabber>(.*?)</tabber>", re.S | re.I)
TAB_SPLIT = re.compile(r"\|-\|")
TAB_LABEL = re.compile(r"\s*([^=\n]{1,80})=(.*)", re.S)
PREFERRED_TAB = re.compile(r"official|localis|localiz|english", re.I)

FILE_LINK = re.compile(r"\[\[(?:File|Image|Media|Category):[^\]]*\]\]", re.I)
HEADING = re.compile(r"^\s*={2,}.*?={2,}\s*$")
TABLE_MARKUP = re.compile(r"^\s*(?:\{\||\|\}|\||!)")
LIST_PREFIX = re.compile(r"^[:*#;]+\s*")
HTML_TAG = re.compile(r"</?[a-zA-Z][^>]*>")
BOLD_ITALIC = re.compile(r"'{2,5}")
EXTERNAL_LINK = re.compile(r"\[(?:https?:|//)\S+?(?:\s+([^\]]*))?\]")
NOWIKI = re.compile(r"</?nowiki>", re.I)


def _find_templates(text: str) -> list[tuple[int, int, str, list[str]]]:
    """Locate every top-level {{...}}, returning span, name and parameters.

    Done by scanning rather than by regex: transcript templates nest
    ({{Quote|{{Character|Jin}} said it}}) and a regex either stops at the first
    `}}` or swallows the rest of the page.
    """
    found = []
    i, n = 0, len(text)
    while i < n - 1:
        if text[i] == "{" and text[i + 1] == "{":
            depth, j = 0, i
            while j < n - 1:
                if text[j] == "{" and text[j + 1] == "{":
                    depth += 1
                    j += 2
                elif text[j] == "}" and text[j + 1] == "}":
                    depth -= 1
                    j += 2
                    if depth == 0:
                        break
                else:
                    j += 1
            if depth != 0:            # unbalanced: leave the rest alone
                break
            body = text[i + 2:j - 2]
            parts = _split_params(body)
            name = parts[0].strip().lower() if parts else ""
            found.append((i, j, name, parts[1:]))
            i = j
        else:
            i += 1
    return found


def _split_params(body: str) -> list[str]:
    """Split a template body on top-level pipes only."""
    parts, buf, depth_c, depth_b = [], [], 0, 0
    i, n = 0, len(body)
    while i < n:
        two = body[i:i + 2]
        if two == "{{":
            depth_c += 1
            buf.append(two)
            i += 2
            continue
        if two == "}}":
            depth_c -= 1
            buf.append(two)
            i += 2
            continue
        if two == "[[":
            depth_b += 1
            buf.append(two)
            i += 2
            continue
        if two == "]]":
            depth_b -= 1
            buf.append(two)
            i += 2
            continue
        if body[i] == "|" and depth_c == 0 and depth_b == 0:
            parts.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(body[i])
        i += 1
    parts.append("".join(buf))
    return parts


def _param_value(params: list[str], index: int) -> str | None:
    """The nth positional parameter, skipping named ones (`author=...`)."""
    positional = [p for p in params if not re.match(r"^\s*[A-Za-z_][\w\s-]*=", p)]
    if len(positional) >= index:
        return positional[index - 1]
    return None


def resolve_templates(text: str) -> str:
    """Replace dialogue templates with their line; drop every other template."""
    for start, end, name, params in reversed(_find_templates(text)):
        index = DIALOGUE_TEMPLATES.get(name)
        replacement = ""
        if index is not None:
            value = _param_value(params, index)
            if value:
                replacement = resolve_templates(value)
        text = text[:start] + replacement + text[end:]
    return text


def resolve_links(text: str) -> str:
    """`[[Page|shown]]` and `[[Page]]` both become what a reader sees."""
    text = FILE_LINK.sub(" ", text)

    def internal(match: re.Match) -> str:
        body = match.group(1)
        return body.split("|")[-1] if "|" in body else body

    for _ in range(3):  # links occasionally nest inside link labels
        new = re.sub(r"\[\[([^\[\]]+)\]\]", internal, text)
        if new == text:
            break
        text = new
    return EXTERNAL_LINK.sub(lambda m: m.group(1) or " ", text)


# A line of dialogue on these pages is either labelled with its speaker or set
# in quotation marks. A bare narrative sentence between them is the editor
# describing the scene.
SPEAKER_LABEL = re.compile(r"^[^\"\u201c\n]{1,40}:\s*\S")
QUOTED = re.compile(r"[\"\u201c\u201d]")


def speech_only(lines: list[str]) -> list[str]:
    """Drop the narration a wiki editor wrote around the dialogue.

    "Trelawny fakes a seizure in front of the two bounty hunters" is prose
    about the game, not English the game delivers, and it reads at a very
    different register from the speech it sits between.

    Only applied to pages that actually mark their speech: where few lines are
    labelled or quoted, the page is a plain transcript with no marking at all
    and everything is kept, because the alternative is discarding the page.
    """
    marked = [x for x in lines if SPEAKER_LABEL.match(x) or QUOTED.search(x)]
    if len(marked) < max(5, 0.25 * len(lines)):
        return lines
    return marked


def pick_tab(source: str) -> str:
    """Collapse every <tabber> to the one tab that was in the game."""
    def choose(match: re.Match) -> str:
        parsed = []
        for chunk in TAB_SPLIT.split(match.group(1)):
            label = TAB_LABEL.match(chunk)
            parsed.append((label.group(1).strip(), label.group(2))
                          if label else ("", chunk))
        for label, body in parsed:
            if PREFERRED_TAB.search(label):
                return body
        return parsed[0][1] if parsed else ""
    return TABBER.sub(choose, source)


def spoken_sections(source: str) -> str:
    """Keep only the sections that hold spoken lines.

    A page with no headings at all is returned whole: plenty of wikis write a
    transcript with no section structure, and dropping those would be worse
    than letting a little prose through.
    """
    heads = list(SECTION_HEADING.finditer(source))
    if not heads:
        return source
    kept = []
    for i, head in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(source)
        if SPOKEN_SECTION.search(head.group(2)):
            kept.append(source[head.end():end])
    return "\n".join(kept) if kept else source


def to_lines(source: str) -> list[str]:
    """Wikitext in, candidate dialogue lines out.

    Speaker labels and stage directions survive this step on purpose —
    `clean.py` removes them, and it has to do the same job on transcripts that
    never went through a wiki.
    """
    for pattern in DROP_BLOCKS:
        source = pattern.sub(" ", source)
    source = pick_tab(source)
    source = spoken_sections(source)
    source = NOWIKI.sub("", source)
    source = resolve_templates(source)
    source = resolve_links(source)
    source = HTML_TAG.sub(" ", source)
    source = BOLD_ITALIC.sub("", source)

    out = []
    for raw in source.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if HEADING.match(line) or TABLE_MARKUP.match(line):
            continue
        line = LIST_PREFIX.sub("", line)
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            out.append(line)
    return out
