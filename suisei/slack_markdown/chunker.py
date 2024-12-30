from typing import List, Tuple
from marko import Markdown
from marko.element import Element
from marko.block import Document
from marko.md_renderer import MarkdownRenderer
from .extensions import SLACK_EXTENSION
from suisei.slack_markdown.renderer import SlackRenderer


class Chunker:
    def __init__(self, max_chunk_size: int = 1024):
        # Markdownになるかもしれないリスト
        self.lines = []
        # 未だ続く可能性のあるMarkdownの断片
        self.buffer = ""
        # Markdown中のindex
        self.index = 0

        self.max_chunk_size = max_chunk_size

        self.md = Markdown(renderer=SlackRenderer)
        self.md.use(SLACK_EXTENSION)

        self.md_ref = Markdown(renderer=MarkdownRenderer)
        self.md_ref.use(SLACK_EXTENSION)

        self.finished = False

    def _strip_line(line: str) -> str:
        return line.rstrip("\n ")

    def feed(self, chunk: str):
        self.buffer += chunk
        last_line = self.buffer.rfind("\n")

        if last_line >= 0:
            lines = self.buffer[:last_line].split("\n")
            self.lines.extend([Chunker._strip_line(line) for line in lines])
            self.buffer = self.buffer[last_line + 1 :]

    def finish(self):
        self.finished = True

    def _is_markdown_end(self, elements: List[Element]) -> bool:
        if self.finished:
            return True

        if len(elements) == 0:
            return False

        last_element = elements[-1]

        # 未だ続く可能性のあるtypeを列挙
        blacklist = ["list", "table", "fenced_code"]

        return last_element.get_type(snake_case=True) not in blacklist

    def _split_markdown(self, elements: List[Element]) -> List[List[Element]]:
        result: List[List[Element]] = []
        chunk: List[Element] = []
        for element in elements:
            type = element.get_type(snake_case=True)
            if type == "table":
                # tableは必ず1つ
                result.append(chunk)
                result.append([element])
                chunk = []
            elif type == "thematic_break":
                # --- が来たら区切る
                result.append(chunk)
                chunk = [element]
            else:
                chunk.append(element)

        if len(chunk) > 0:
            result.append(chunk)

        return list(filter(lambda x: len(x) > 0, result))

    def _is_empty(self, elements: List[Element]) -> bool:
        if len(elements) == 0:
            return True

        meaningless = ["thematic_break", "blank_line"]
        for element in elements:
            if element.get_type(snake_case=True) not in meaningless:
                return False

        return True

    def _fix_rendered(self, elements: List[dict]) -> List[dict]:
        return elements

    def consume(self) -> Tuple[dict, str] | None:
        markdown = "\n".join(self.lines)
        parsed = self.md.parse(markdown).children
        chunks = self._split_markdown(parsed[self.index :])

        if len(chunks) == 0:
            return None

        consumable = chunks if self._is_markdown_end(chunks[-1]) else chunks[:-1]

        if len(consumable) == 0:
            return None

        first = consumable[0]

        # 空の場合は無視
        print(first)
        if self._is_empty(first):
            self.index += len(first)
            return None

        doc = Document()
        doc.children = first

        reference_md = self.md_ref.render(doc)

        if len(consumable) == 1 and not self.finished:
            # これが途中のchunkの最後の場合、短すぎると分かれすぎるため待つ
            if len(markdown) < self.max_chunk_size:
                return None

        self.index += len(first)

        raw_rendered = self.md.render(doc)
        if not SlackRenderer.validate(raw_rendered):
            raw_rendered = self._fix_rendered(raw_rendered)
            if not SlackRenderer.validate(raw_rendered):
                raise ValueError(f"Invalid rendered markdown {raw_rendered} {first}")

        rendered = SlackRenderer.postprocess(raw_rendered)

        return (rendered, reference_md)


from slack_sdk.web import WebClient


class SlackChunker(Chunker):
    def __init__(
        self,
        client: WebClient,
        channel: str,
        thread_ts: str,
        max_chunk_size: int = 1024,
    ):
        super().__init__(max_chunk_size)
        self.client = client
        self.channel = channel
        self.thread_ts = thread_ts

    def _fix_rendered(self, elements):
        if len(elements) == 1 and elements[0]["type"] == "_embed_file":
            # ファイルを埋め込む場合、Slack APIで投稿して、URLを返す
            file = elements[0]["content"]
            name = elements[0]["name"]
            self.client.files_upload_v2(
                channels=self.channel,
                thread_ts=self.thread_ts,
                filename=name,
                file=file,
            )
            return [
                {
                    "type": "rich_text_section",
                    "elements": [
                        {
                            "type": "text",
                            "text": f"[表を埋め込みました]",
                        }
                    ],
                }
            ]
        return super()._fix_rendered(elements)

    def consume(self):
        result = super().consume()
        if result is None:
            return None

        blocks, reference_md = result
        try:
            self.client.chat_postMessage(
                channel=self.channel,
                thread_ts=self.thread_ts,
                text=reference_md,
                blocks=blocks,
            )
        except Exception as e:
            from json import dumps

            raise Exception(f"Failed to post message: {e} {dumps(blocks)}")
