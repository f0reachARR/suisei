from marko import MarkoExtension
from marko.ext.gfm import GFM
from marko import inline
from marko.helpers import render_dispatch
from marko.md_renderer import MarkdownRenderer
import re
from .renderer import SlackRenderer


class SlackReference(inline.InlineElement):
    pattern = re.compile(r"<((@U|#C)[A-Z0-9]+)>")
    priority = 5
    parse_children = False


class RenderMixin:
    @render_dispatch(MarkdownRenderer)
    def render_slack_reference(self, element):
        return f"{element.children}"

    @render_slack_reference.dispatch(SlackRenderer)
    def render_slack_reference(self, element: SlackReference) -> str:
        if element.children.startswith("@"):
            return [
                {
                    "type": "user",
                    "user_id": element.children[1:],
                }
            ]
        elif element.children.startswith("#"):
            return [
                {
                    "type": "channel",
                    "channel_id": element.children[1:],
                }
            ]
        else:
            return [
                {
                    "type": "text",
                    "text": element.children,
                }
            ]


SLACK_EXTENSION = MarkoExtension(
    elements=GFM.elements + [SlackReference], renderer_mixins=[RenderMixin]
)
