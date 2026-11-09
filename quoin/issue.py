from __future__ import annotations

import html

MODES = {"study": "Study", "transit": "Transit", "bedtime": "Bedtime"}
KINDS = ("weekly", "pack", "single")
QUESTIONS_TITLE = "Questions to hold"

CSS = (
    '@charset "UTF-8";'
    "html{-webkit-text-size-adjust:100%}"
    'body{margin:0 4%;font-family:Georgia,"Times New Roman",serif;font-size:1em;'
    "line-height:1.5;color:#000;background:#fff;word-wrap:break-word;"
    "overflow-wrap:break-word}"
    'h1,h2,h3,h4{font-family:"Helvetica Neue",Helvetica,Arial,sans-serif;'
    "line-height:1.2;page-break-after:avoid;break-after:avoid}"
    "h1{font-size:1.6em;margin:.3em 0 .4em}"
    "h2{font-size:1.25em;margin:1.4em 0 .5em}"
    "h3{font-size:1.1em;margin:1.2em 0 .4em}"
    "p{margin:0 0 .85em}"
    "a{color:#000;text-decoration:underline}"
    "ul,ol{padding-left:1.4em}"
    "li{margin:.2em 0}"
    "blockquote{margin:1em 0 1em .8em;padding-left:.8em;border-left:1px solid #000}"
    "img{max-width:100%;height:auto;width:auto;max-height:90vh}"
    "figure{margin:1em 0;page-break-inside:avoid;break-inside:avoid}"
    "figcaption{font-size:.85em;font-style:italic;margin-top:.4em}"
    "pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.85em}"
    "code{font-size:.9em}"
    "table{border-collapse:collapse;max-width:100%}"
    "th,td{border:1px solid #000;padding:.25em .4em;text-align:left}"
    "hr{border:0;border-top:1px solid #000;margin:1.5em 0}"
    ".cover{margin:0;text-align:center}"
    ".cover img{max-width:100%;max-height:100%}"
    '.label{font-family:"Helvetica Neue",Helvetica,Arial,sans-serif;font-size:.8em;'
    "font-weight:bold;letter-spacing:.06em;text-transform:uppercase;margin:0 0 .4em}"
    ".byline{font-size:.95em;font-style:italic;margin:0}"
    ".source-head{margin:0 0 1.4em;padding-bottom:.6em;border-bottom:1px solid #000}"
    ".source-foot{margin-top:2em;padding-top:.6em;border-top:1px solid #000;"
    "font-size:.85em;page-break-inside:avoid;break-inside:avoid}"
    ".source-foot p{margin:0 0 .3em}"
    ".subtitle{font-size:1.1em;font-style:italic}"
    '.total{font-family:"Helvetica Neue",Helvetica,Arial,sans-serif;font-size:.9em;'
    "font-weight:bold}"
    ".contents h2{font-size:1.05em;margin:1.2em 0 .3em}"
    ".contents ol{list-style:none;padding:0;margin:0}"
    ".contents li{margin:.25em 0}"
    ".intro{font-style:italic;font-size:1.05em}"
    ".why{font-size:1.05em;margin:1em 0}"
    ".questions ol,.source-questions ol{padding-left:1.4em}"
    ".questions li{margin:.6em 0}"
    ".source-questions{margin-top:2em;page-break-inside:avoid;break-inside:avoid}"
    "\n"
)


def _e(value) -> str:
    return html.escape(str(value), quote=True)


def _issue(source: dict) -> dict:
    return source.get("issue", {})


def details(manifest: dict) -> dict:
    return manifest.get("issue", {})


def is_single(manifest: dict) -> bool:
    return details(manifest).get("kind") == "single"


def questions(manifest: dict) -> list[str]:
    return list(details(manifest).get("questions", []))


def spine_items(manifest: dict, ordered: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    if is_single(manifest):
        return [item for item in ordered if item[2] != "movement"]
    return ordered


def minutes(source: dict) -> int:
    return int(_issue(source).get("minutes", 0))


def mode_label(source: dict) -> str:
    return MODES.get(_issue(source).get("mode", ""), "")


def _sources_in(movement: dict, sources: dict[str, dict]) -> list[dict]:
    return [
        sources[item["ref"].split(":", 1)[1]]
        for item in movement["items"]
        if item["ref"].startswith("source:")
    ]


def _minutes_text(value: int) -> str:
    return f"{value} min"


def total_line(manifest: dict) -> str:
    sources = manifest["sources"]
    total = sum(minutes(source) for source in sources)
    pieces = f"{len(sources)} piece" + ("" if len(sources) == 1 else "s")
    if is_single(manifest):
        return f"{pieces} · {total} minutes"
    sections = len(manifest["movements"])
    section_text = f"{sections} section" + ("" if sections == 1 else "s")
    return f"{pieces} · {section_text} · {total} minutes"


def title_body(manifest: dict) -> str:
    sources = {source["id"]: source for source in manifest["sources"]}
    parts = [f'<section class="issue-title"><h1>{_e(manifest["title"])}</h1>']
    if manifest.get("subtitle"):
        parts.append(f'<p class="subtitle">{_e(manifest["subtitle"])}</p>')
    if details(manifest).get("why"):
        parts.append(f'<p class="why">{_e(details(manifest)["why"])}</p>')
    parts.append(f'<p class="total">{_e(total_line(manifest))}</p>')
    parts.append('<div class="contents">')
    for movement in manifest["movements"]:
        if is_single(manifest):
            parts.append("<ol>")
        else:
            parts.append(
                f'<h2><a href="movement-{_e(movement["id"])}.xhtml">'
                f"{_e(movement['title'])}</a></h2><ol>"
            )
        for source in _sources_in(movement, sources):
            label = mode_label(source)
            suffix = " · ".join(part for part in (_minutes_text(minutes(source)), label) if part)
            parts.append(
                f'<li><a href="source-{_e(source["id"])}.xhtml">'
                f"{_e(source.get('title', source['id']))}</a> · {_e(suffix)}</li>"
            )
        parts.append("</ol>")
    if questions(manifest):
        parts.append(f'<p><a href="questions.xhtml">{_e(QUESTIONS_TITLE)}</a></p>')
    parts.append("</div></section>")
    return "".join(parts)


def questions_body(manifest: dict) -> str:
    items = "".join(f"<li>{_e(question)}</li>" for question in questions(manifest))
    return f'<section class="questions"><h1>{_e(QUESTIONS_TITLE)}</h1><ol>{items}</ol></section>'


def source_questions(source: dict) -> str:
    issue = _issue(source)
    if issue.get("mode") != "study" or not issue.get("questions"):
        return ""
    items = "".join(f"<li>{_e(question)}</li>" for question in issue["questions"])
    return (
        f'<section class="source-questions"><p class="label">{_e(QUESTIONS_TITLE)}</p>'
        f"<ol>{items}</ol></section>"
    )


def movement_body(manifest: dict, movement: dict) -> str:
    sources = {source["id"]: source for source in manifest["sources"]}
    members = _sources_in(movement, sources)
    total = sum(minutes(source) for source in members)
    pieces = f"{len(members)} piece" + ("" if len(members) == 1 else "s")
    intro = f'<p class="intro">{_e(movement["intro"])}</p>' if movement.get("intro") else ""
    return (
        f'<section class="issue-section"><h1>{_e(movement["title"])}</h1>{intro}'
        f'<p class="label">{_e(pieces)} · {_e(total)} minutes</p></section>'
    )


def source_header(source: dict) -> str:
    attribution = source.get("attribution", {})
    label = " · ".join(
        part for part in (mode_label(source), _minutes_text(minutes(source))) if part
    )
    parts = ['<header class="source-head">']
    parts.append(f'<p class="label">{_e(label)}</p>')
    parts.append(f"<h1>{_e(source.get('title', source['id']))}</h1>")
    if attribution.get("author"):
        parts.append(f'<p class="byline">{_e(attribution["author"])}</p>')
    parts.append("</header>")
    return "".join(parts)


def source_footer(source: dict) -> str:
    attribution = source.get("attribution", {})
    issue = _issue(source)
    url = issue.get("url") or source.get("locator", "")
    lines = []
    byline = " · ".join(
        part
        for part in (attribution.get("author"), attribution.get("publisher"), issue.get("date"))
        if part
    )
    if byline:
        lines.append(f"<p>{_e(byline)}</p>")
    if url.startswith(("http://", "https://")):
        lines.append(f'<p><a href="{_e(url)}">{_e(url)}</a></p>')
    if issue.get("asked_by"):
        lines.append(f"<p>Queued by {_e(issue['asked_by'])}</p>")
    if issue.get("why"):
        lines.append(f"<p>Why: {_e(issue['why'])}</p>")
    if mode_label(source):
        lines.append(
            f"<p>Mode: {_e(mode_label(source))} · {_e(_minutes_text(minutes(source)))}</p>"
        )
    return f'<footer class="source-foot">{"".join(lines)}</footer>'


def nav_items(manifest: dict) -> str:
    sources = {source["id"]: source for source in manifest["sources"]}
    parts = ['<li><a href="text/title.xhtml">Contents</a></li>']
    for movement in manifest["movements"]:
        if is_single(manifest):
            parts.extend(
                f'<li><a href="text/source-{_e(source["id"])}.xhtml">'
                f"{_e(source.get('title', source['id']))} "
                f"({_e(_minutes_text(minutes(source)))})</a></li>"
                for source in _sources_in(movement, sources)
            )
            continue
        parts.append(
            f'<li><a href="text/movement-{_e(movement["id"])}.xhtml">'
            f"{_e(movement['title'])}</a><ol>"
        )
        for source in _sources_in(movement, sources):
            parts.append(
                f'<li><a href="text/source-{_e(source["id"])}.xhtml">'
                f"{_e(source.get('title', source['id']))} "
                f"({_e(_minutes_text(minutes(source)))})</a></li>"
            )
        parts.append("</ol></li>")
    if questions(manifest):
        parts.append(f'<li><a href="text/questions.xhtml">{_e(QUESTIONS_TITLE)}</a></li>')
    parts.append('<li><a href="text/attribution.xhtml">Attribution</a></li>')
    return "".join(parts)


def validate(manifest: dict) -> list[str]:
    errors: list[str] = []
    if manifest.get("template") is None:
        return errors
    if manifest["template"] != "issue":
        return ["manifest.json: template must be issue"]
    if "subtitle" in manifest and not isinstance(manifest["subtitle"], str):
        errors.append("manifest.json: subtitle must be a string")
    meta = manifest.get("issue", {})
    if not isinstance(meta, dict):
        return [*errors, "manifest.json: issue must be an object"]
    if "kind" in meta and meta["kind"] not in KINDS:
        errors.append("manifest.json: issue.kind must be one of weekly, pack, single")
    if "why" in meta and not isinstance(meta["why"], str):
        errors.append("manifest.json: issue.why must be a string")
    errors.extend(_string_list_errors(meta, "questions", "manifest.json: issue.questions"))
    if meta.get("kind") == "single" and len(manifest.get("sources", [])) != 1:
        errors.append("manifest.json: a single issue holds exactly one source")
    for index, movement in enumerate(manifest.get("movements", [])):
        if "intro" in movement and not isinstance(movement["intro"], str):
            errors.append(f"manifest.json: movements[{index}].intro must be a string")
    for index, source in enumerate(manifest.get("sources", [])):
        issue = source.get("issue")
        path = f"manifest.json: sources[{index}].issue"
        if not isinstance(issue, dict):
            errors.append(f"{path} is required for the issue template")
            continue
        if issue.get("mode") not in MODES:
            errors.append(f"{path}.mode must be one of study, transit, bedtime")
        value = issue.get("minutes")
        if type(value) is not int or value < 0:
            errors.append(f"{path}.minutes must be a non-negative integer")
        for key in ("url", "date", "asked_by", "why"):
            if key in issue and not isinstance(issue[key], str):
                errors.append(f"{path}.{key} must be a string")
        errors.extend(_string_list_errors(issue, "questions", f"{path}.questions"))
    return errors


def _string_list_errors(container: dict, key: str, path: str) -> list[str]:
    if key not in container:
        return []
    value = container[key]
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        return [f"{path} must be a list of non-empty strings"]
    return []
