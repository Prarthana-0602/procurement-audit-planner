"""Markdown to HTML for the one-page app. Raw HTML in the source is neutralised."""
import re

import markdown

_COMMENT = re.compile(r"<!--.*?-->", re.S)


def md_to_html(text: str) -> str:
    text = _COMMENT.sub("", text).replace("<", "&lt;")
    return markdown.markdown(text, extensions=["tables", "fenced_code"])
