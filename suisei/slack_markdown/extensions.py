from marko import MarkoExtension
from marko.ext.gfm import GFM
from marko import inline
import re


class SlackReference(inline.InlineElement):
    pattern = re.compile(r"<((@U|#C)[A-Z0-9]+)>")
    priority = 5
    parse_children = False


SLACK_EXTENSION = MarkoExtension(elements=GFM.elements + [SlackReference])
