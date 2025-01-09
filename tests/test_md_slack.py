from marko import Markdown, MarkoExtension
from marko.md_renderer import MarkdownRenderer
from suisei.slack_markdown.extensions import SLACK_EXTENSION
from suisei.slack_markdown.renderer import SlackRenderer


def test_SlackReference():
    test_input = "## Hello World!\n<@U12345678> <#C12345678>"

    parser = Markdown(extensions=[SLACK_EXTENSION], renderer=SlackRenderer)
    result = parser.parse(test_input)

    assert result.children[1].get_type() == "Paragraph"
    assert result.children[1].children[0].get_type() == "SlackReference"
    assert result.children[1].children[0].children == "@U12345678"
    assert result.children[1].children[1].get_type() == "RawText"
    assert result.children[1].children[1].children == " "
    assert result.children[1].children[2].get_type() == "SlackReference"
    assert result.children[1].children[2].children == "#C12345678"

    rendered = parser.render(result)

    assert rendered[1]["elements"][0]["type"] == "user"
    assert rendered[1]["elements"][2]["type"] == "channel"


def test_SlackReference_MarkdownRenderer():
    parser = Markdown(extensions=[SLACK_EXTENSION], renderer=MarkdownRenderer)

    test_input = "## Hello World!\n<@U12345678> <#C12345678>"

    result = parser(test_input)

    assert result == "## Hello World!\n@U12345678 #C12345678\n"
