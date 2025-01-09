from marko import Markdown, MarkoExtension
from suisei.slack_markdown.extensions import SlackReference


def test_SlackReference():
    test_input = "## Hello World!\n<@U12345678> <#C12345678>"

    parser = Markdown(extensions=[MarkoExtension(elements=[SlackReference])])
    result = parser.parse(test_input)

    assert result.children[1].get_type() == "Paragraph"
    assert result.children[1].children[0].get_type() == "SlackReference"
    assert result.children[1].children[0].children == "@U12345678"
    assert result.children[1].children[1].get_type() == "RawText"
    assert result.children[1].children[1].children == " "
    assert result.children[1].children[2].get_type() == "SlackReference"
    assert result.children[1].children[2].children == "#C12345678"
