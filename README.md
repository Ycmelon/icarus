# icarus

LLM-based conversational Telegram bot aiming to mimic human texting behaviour

https://github.com/Ycmelon/icarus/assets/16069727/9886ceca-6a7a-4203-bfcc-54d4fdd9f26f

## Cool things

- Faux typing indicator and delays between messages
- Conversational memory using summarisation models (using a technique similar to [this](https://www.pinecone.io/learn/series/langchain/langchain-conversational-memory/))
- A separate bot to manage the bot's "context" (instructions on writing responses) from within Telegram (`/set_context`, `/get_context`)
- Manage conversation history using commands from within Telegram (`/update_history`, `/clear_history`)

## Requirements

- Python 3 (tested on 3.9)
- A separate Telegram user account from your own, i.e. a second phone number to register for one (or use a service like [Textverified](https://www.textverified.com/))
- A [NLP Cloud](https://nlpcloud.com/) account (they provide free initial credits)

## Usage

1. Clone repo, install dependencies in `requirements.txt`
2. Rename `template.env` to `.env`
3. Create a Telegram user account and [obtain its API ID and hash](https://docs.telethon.dev/en/stable/basic/signing-in.html)
4. Create a Telegram bot ([message @BotFather](https://t.me/botfather)) and obtain its bot token
5. Create a [NLP Cloud](https://nlpcloud.com/) account and get your API key
6. Get your personal Telegram account's user ID (not that of the bot you created earlier) ([message @userinfobot](https://t.me/userinfobot))
7. Update `.env` with all above information
8. Run `main.py`
