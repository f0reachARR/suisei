from __future__ import annotations

import html
from typing import Any, Literal, Union, cast
from urllib.parse import quote

from marko.renderer import Renderer
from marko.md_renderer import MarkdownRenderer
from marko import block, inline
from marko.ext.gfm.elements import Table


class SlackRenderer(Renderer):
    def __init__(self) -> None:
        super().__init__()
        self.md = MarkdownRenderer()
        self.list_type = "bullet"
        self.list_indent = 0

    @staticmethod
    def postprocess(children: list) -> Any:
        rendered = []
        rich_text_children = []

        for child in children:
            if isinstance(child, dict) and child["type"] == "rich_text":
                if len(rich_text_children) > 0:
                    rendered.append(
                        {
                            "type": "rich_text",
                            "elements": rich_text_children,
                        }
                    )
                rendered.append(child)
                rich_text_children = []
            else:
                rich_text_children.append(child)

        if len(rich_text_children) > 0:
            rendered.append(
                {
                    "type": "rich_text",
                    "elements": rich_text_children,
                }
            )

        return rendered

    @staticmethod
    def validate(element: dict) -> bool:
        if isinstance(element, list):
            return all(SlackRenderer.validate(child) for child in element)
        if not isinstance(element, dict):
            return False
        if "type" not in element:
            return False
        if element["type"].startswith("_"):
            return False
        if "elements" in element and element["type"].startswith("rich_text"):
            return all(SlackRenderer.validate(child) for child in element["elements"])
        return True

    def render_children(self, element: Any) -> Any:
        rendered = [self.render(child) for child in element.children]  # type: ignore
        rendered = list(filter(None, rendered))
        rendered = map(lambda x: x if isinstance(x, list) else [x], rendered)
        rendered = sum(rendered, [])

        return rendered

    def render_paragraph(self, element: block.Paragraph) -> str:
        children = self.render_children(element)
        assert len(children) > 0
        return [{"type": "rich_text_section", "elements": children}]

    def render_list(self, element: block.List) -> str:
        if element.ordered:
            self.list_type = "ordered"
        else:
            self.list_type = "bullet"
        self.list_indent += 1
        children = self.render_children(element)
        self.list_indent -= 1

        # Shrink same indent into one list
        shrunk = []
        indent = -1
        for child in children:
            if child["indent"] == indent and len(shrunk) > 0:
                shrunk[-1]["elements"].extend(child["elements"])
            else:
                shrunk.append(child)
                indent = child["indent"]
        return shrunk

    def render_list_item(self, element: block.ListItem) -> str:
        children = self.render_children(element)
        rendered = [
            {
                "type": "rich_text_list",
                "style": self.list_type,
                "elements": [],
                "indent": self.list_indent - 1,
            }
        ]

        all_section = all(child["type"] == "rich_text_section" for child in children)
        if all_section:
            rendered[0]["elements"] = [
                {
                    "type": "rich_text_section",
                    "elements": sum(list(map(lambda x: x["elements"], children)), []),
                }
            ]
        else:
            for child in children:
                if isinstance(child, dict) and child["type"] == "rich_text_list":
                    rendered.append(child)
                elif (
                    isinstance(child, dict)
                    and child["type"] == "rich_text_preformatted"
                ):
                    rendered.append(child)
                else:
                    rendered[0]["elements"].append(child)
        return rendered

    def render_quote(self, element: block.Quote) -> str:
        children = self.render_children(element)
        rendered = []

        # list or paragraph is allowed in quote
        for child in children:
            assert isinstance(child, dict)
            if child["type"] == "rich_text_list":
                child["border"] = 1
                if len(rendered) > 0 and rendered[-1]["type"] == "rich_text":
                    rendered[-1]["elements"].append(child)
                else:
                    rendered.append(
                        {
                            "type": "rich_text",
                            "elements": [child],
                        }
                    )
            elif child["type"] == "rich_text_section":
                if len(rendered) > 0 and rendered[-1]["type"] != "rich_text":
                    rendered[-1]["elements"].extend(child["elements"])
                else:
                    rendered.append(
                        {
                            "type": "rich_text_quote",
                            "elements": child["elements"],
                        }
                    )
            else:
                raise ValueError(f"Unexpected element in quote: {child}")

        return rendered

    def render_fenced_code(self, element: block.FencedCode) -> str:
        return {
            "type": "rich_text_preformatted",
            "elements": [
                {
                    "type": "text",
                    "text": element.children[0].children.strip(),  # type: ignore
                }
            ],
        }

    def render_code_block(self, element: block.CodeBlock) -> str:
        return self.render_fenced_code(cast("block.FencedCode", element))

    def render_html_block(self, element: block.HTMLBlock) -> str:
        return {
            "type": "rich_text_preformatted",
            "elements": [
                {
                    "type": "text",
                    "text": html.escape(element.body).strip(),  # type: ignore
                }
            ],
        }

    def render_thematic_break(self, element: block.ThematicBreak) -> str:
        return []

    def render_heading(self, element: block.Heading) -> str:
        return self.render_children(element)

    def render_setext_heading(self, element: block.SetextHeading) -> str:
        return self.render_heading(cast("block.Heading", element))

    def render_blank_line(self, element: block.BlankLine) -> str:
        return [
            {"type": "rich_text_section", "elements": [{"type": "text", "text": "\n"}]}
        ]

    def render_link_ref_def(self, element: block.LinkRefDef) -> str:
        return []

    def _render_text_style(
        self,
        element: Any,
        style: Union[
            Literal["italic"], Literal["bold"], Literal["strike"], Literal["code"]
        ],
    ) -> str:
        children = (
            self.render_children(element)
            if isinstance(element.children, list)
            else element.children
        )
        if all(isinstance(child, str) for child in children):
            return [
                {
                    "type": "text",
                    "text": "".join(children),
                    "style": {style: True},
                }
            ]
        else:
            modified = []
            for child in children:
                if isinstance(child, dict):
                    assert child["type"] in ["text", "emoji", "link"]
                    child["style"] = child.get("style", {})
                    child["style"][style] = True
                else:
                    child = {"type": "text", "text": child, "style": {style: True}}
                modified.append(child)
            return modified

    def render_emphasis(self, element: inline.Emphasis) -> str:
        return self._render_text_style(element, "italic")

    def render_strong_emphasis(self, element: inline.StrongEmphasis) -> str:
        return self._render_text_style(element, "bold")

    def render_strikethrough(self, element):
        return self._render_text_style(element, "strike")

    def render_inline_html(self, element: inline.InlineHTML) -> str:
        return cast(str, element.children)

    def render_code_span(self, element: inline.CodeSpan) -> str:
        return self._render_text_style(element, "code")

    def render_plain_text(self, element: Any) -> str:
        if isinstance(element.children, str):
            return self.render_raw_text(cast("inline.RawText", element))
        return self.render_children(element)

    def render_link(self, element: inline.Link) -> dict:
        url = self.escape_url(element.dest)
        body = self.md.render_children(element)
        return [
            {
                "type": "link",
                "url": url,
                "text": body,
            }
        ]

    def render_url(self, element: inline.AutoLink) -> dict:
        return self.render_link(cast("inline.Link", element))

    def render_auto_link(self, element: inline.AutoLink) -> str:
        return self.render_link(cast("inline.Link", element))

    def render_image(self, element: inline.Image) -> str:
        url = self.escape_url(element.dest)
        body = self.md.render_children(element)
        return [
            {
                "type": "link",
                "url": url,
                "text": url if body == "" else body,
            }
        ]

    def render_literal(self, element: inline.Literal) -> str:
        return self.render_raw_text(cast("inline.RawText", element))

    def render_raw_text(self, element: inline.RawText) -> str:
        return [{"type": "text", "text": element.children}]

    def render_line_break(self, element: inline.LineBreak) -> str:
        return [{"type": "text", "text": "\n"}]

    def render_table(self, element: Table) -> str:
        from io import StringIO
        from csv import writer

        with StringIO() as f:
            w = writer(f, lineterminator="\n")
            for row in element.children:
                w.writerow([self.md.render(cell) for cell in row.children])

            return [
                {"type": "_embed_file", "content": f.getvalue(), "name": "table.csv"}
            ]

    @staticmethod
    def escape_html(raw: str) -> str:
        return html.escape(html.unescape(raw)).replace("&#x27;", "'")

    @staticmethod
    def escape_url(raw: str) -> str:
        """
        Escape urls to prevent code injection craziness. (Hopefully.)
        """
        return html.escape(quote(html.unescape(raw), safe="/#:()*?=%@+,&"))
