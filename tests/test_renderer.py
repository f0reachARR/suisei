from deepdiff import DeepDiff


def test_slack_renderer_1():
    from marko import Markdown
    from suisei.slack_markdown.renderer import SlackRenderer
    from suisei.slack_markdown.extensions import SLACK_EXTENSION

    MARKDOWN_TEXT = """
**Hello *world***
~~strike~~

```cpp
#include <iostream>

int main() {
    std::cout << "Hello, world!" << std::endl;
    return 0;
}
```

[Hello, world!](https://example.com)

https://example.com

![Hello, world!](https://example.com/hello.png)

- List item 1
    - List item 1.1
    - List item 1.2
        - List item 1.2

1. List item 1
2. List item 2
    1. List item 2.1
    1. List item 2.1

> Hello, world!
> - Scramble Egg
> - Bacon
> - Ham
>    - ???

"""

    markdown = Markdown(renderer=SlackRenderer)
    markdown.use(SLACK_EXTENSION)
    parsed = markdown.parse(MARKDOWN_TEXT)
    rendered = markdown.render(parsed)
    rendered = SlackRenderer.postprocess(rendered)
    expected = [
        {
            "type": "rich_text",
            "elements": [
                {
                    "type": "rich_text_section",
                    "elements": [
                        {"type": "text", "text": "Hello ", "style": {"bold": True}},
                        {
                            "type": "text",
                            "text": "world",
                            "style": {"italic": True, "bold": True},
                        },
                        {"type": "text", "text": "\n"},
                        {"type": "text", "text": "strike", "style": {"strike": True}},
                    ],
                },
                {
                    "type": "rich_text_preformatted",
                    "elements": [
                        {
                            "type": "text",
                            "text": '#include <iostream>\n\nint main() {\n    std::cout << "Hello, world!" << std::endl;\n    return 0;\n}',
                        }
                    ],
                },
                {
                    "type": "rich_text_section",
                    "elements": [
                        {
                            "type": "link",
                            "url": "https://example.com",
                            "text": "Hello, world!",
                        }
                    ],
                },
                {
                    "type": "rich_text_section",
                    "elements": [
                        {
                            "type": "link",
                            "url": "https://example.com",
                            "text": "https://example.com",
                        }
                    ],
                },
                {
                    "type": "rich_text_section",
                    "elements": [
                        {
                            "type": "link",
                            "url": "https://example.com/hello.png",
                            "text": "Hello, world!",
                        }
                    ],
                },
                {
                    "type": "rich_text_list",
                    "style": "bullet",
                    "elements": [
                        {
                            "type": "rich_text_section",
                            "elements": [{"type": "text", "text": "List item 1"}],
                        }
                    ],
                    "indent": 0,
                },
                {
                    "type": "rich_text_list",
                    "style": "bullet",
                    "elements": [
                        {
                            "type": "rich_text_section",
                            "elements": [{"type": "text", "text": "List item 1.1"}],
                        },
                        {
                            "type": "rich_text_section",
                            "elements": [{"type": "text", "text": "List item 1.2"}],
                        },
                    ],
                    "indent": 1,
                },
                {
                    "type": "rich_text_list",
                    "style": "bullet",
                    "elements": [
                        {
                            "type": "rich_text_section",
                            "elements": [{"type": "text", "text": "List item 1.2"}],
                        }
                    ],
                    "indent": 2,
                },
                {
                    "type": "rich_text_list",
                    "style": "ordered",
                    "elements": [
                        {
                            "type": "rich_text_section",
                            "elements": [{"type": "text", "text": "List item 1"}],
                        },
                        {
                            "type": "rich_text_section",
                            "elements": [{"type": "text", "text": "List item 2"}],
                        },
                    ],
                    "indent": 0,
                },
                {
                    "type": "rich_text_list",
                    "style": "ordered",
                    "elements": [
                        {
                            "type": "rich_text_section",
                            "elements": [{"type": "text", "text": "List item 2.1"}],
                        },
                        {
                            "type": "rich_text_section",
                            "elements": [{"type": "text", "text": "List item 2.1"}],
                        },
                    ],
                    "indent": 1,
                },
                {
                    "type": "rich_text_quote",
                    "elements": [{"type": "text", "text": "Hello, world!"}],
                },
            ],
        },
        {
            "type": "rich_text",
            "elements": [
                {
                    "type": "rich_text_list",
                    "style": "bullet",
                    "elements": [
                        {
                            "type": "rich_text_section",
                            "elements": [{"type": "text", "text": "Scramble Egg"}],
                        },
                        {
                            "type": "rich_text_section",
                            "elements": [{"type": "text", "text": "Bacon"}],
                        },
                        {
                            "type": "rich_text_section",
                            "elements": [{"type": "text", "text": "Ham"}],
                        },
                    ],
                    "indent": 0,
                    "border": 1,
                },
                {
                    "type": "rich_text_list",
                    "style": "bullet",
                    "elements": [
                        {
                            "type": "rich_text_section",
                            "elements": [{"type": "text", "text": "???"}],
                        }
                    ],
                    "indent": 1,
                    "border": 1,
                },
            ],
        },
    ]

    assert not DeepDiff(rendered, expected)
