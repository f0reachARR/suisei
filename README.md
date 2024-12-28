# Suisei: Slack AI-powered chat bot

A Slack chat bot powered by [Google Gemini API](https://ai.google.dev/aistudio?hl=ja).
This is a fork of [Collmbo](https://github.com/iwamot/collmbo) and [ChatGPT-in-Slack](https://github.com/seratch/ChatGPT-in-Slack/).

## Changes from the original

- Messaging queue with `threading` is replaced (Work in progress)
- Support more file types (e.g. PDF document)
- Message splitting for long messages (length based / marker `---` based)

## License

This project is licensed under the MIT License. See the LICENSE file for details.
