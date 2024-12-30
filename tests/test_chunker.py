def test_chunker():
    from suisei.slack_markdown.chunker import Chunker

    chunker = Chunker()
    chunker.feed("Hello, world!\n")
    chunker.feed("This is a test.\n")
