import asyncio
from pprint import pprint
from telethon import TelegramClient, events, functions

from api import get_response, summarise_text
from utils import parse_history
from db import (
    get_history,
    add_history,
    clear_history,
    get_history_min_id,
    rewrite_history,
    get_history_length,
    delete_history,
    get_summary,
    set_summary,
    delete_summary,
)

import os
from dotenv import load_dotenv

load_dotenv()

api_id = int(os.environ["TELEGRAM_API_ID"])
api_hash = os.environ["TELEGRAM_API_HASH"]
client = TelegramClient("anon", api_id, api_hash)

# constants
DELAY = 2  # seconds
TYPING_SPEED = 20  # characters per second
HISTORY_LENGTH_THRESHOLD = 40  # when to initiate summary
HISTORY_LENGTH_TO_SUMMARISE = 20  # number of histories to take out and summarise
CONVERSATION_TEMPLATE = [  # template to dictate conversation tone (TODO)
    {"input": "hi", "response": "hey!\nwhats up?"},
    {
        "input": "not much\nhbu?",
        "response": "ic\nim just chilling rn\ndo u wanna get sth to eat?",
    },
    {"input": "nah im good\nmaybe later", "response": "kk np\njust lmk when :)"},
]
USER_NAME = os.environ.get("USER_NAME", "Matt")  # user and bot name
BOT_NAME = os.environ.get("BOT_NAME", "Icarus")  # mostly for summary use

# state
current_message_ids = {}
current_message_parts = {}
wait_tasks = {}
cancel_tasks = {}
client_typing_statuses = {}
summarising_statuses = {}


# helper functions


async def reply(event):
    """
    retrieve and clear message parts
    initiate api call
    send reply on tg
    check if history is too long, if so, initiate summary task
    """
    chat_id = event.chat_id

    global current_message_ids, current_message_parts
    current_message_id = current_message_ids[chat_id]
    current_message = "\n".join(current_message_parts[chat_id])

    del current_message_ids[chat_id]
    current_message_parts[chat_id].clear()

    history = [
        *CONVERSATION_TEMPLATE,
        *get_history(chat_id),
    ]

    async with client.action(event.chat_id, "typing"):  # pyright: ignore
        current_summary = get_summary(chat_id)
        response, load_time = await get_response(
            current_message, history, current_summary
        )  # pyright: ignore

        add_history(current_message_id, event.chat_id, current_message, response)
        print(f"[{chat_id}] Current summary: {current_summary}")
        print(f"[{chat_id}] Current history (without prompts)")
        pprint(get_history(chat_id))

    # check if summarising is necessary, if so initiate it
    if get_history_length(chat_id) > HISTORY_LENGTH_THRESHOLD:
        # only initiate it if its not already running
        if not (chat_id in summarising_statuses and summarising_statuses[chat_id]):
            asyncio.create_task(summarise(chat_id))

    for i, raw_text in enumerate(response.split("\n")):
        if raw_text == "":  # speechless
            continue

        text = raw_text
        wait = len(text) / TYPING_SPEED
        if i != 0:  # dont need to wait before sending first message
            async with client.action(event.chat_id, "typing"):  # pyright: ignore
                await asyncio.sleep(wait)

        await event.respond(text)


async def wait_before_reply(event):
    await asyncio.sleep(DELAY)
    if client_typing_statuses.get(event.chat_id, False):
        await wait_before_reply(event)
    else:
        asyncio.create_task(reply(event))


async def stop_typing(chat_id):
    """
    bg task to set typing status back to false
    """

    await asyncio.sleep(6)  # typing status lasts for 6s, cancel after 6s

    global client_typing_statuses
    client_typing_statuses[chat_id] = False

    print(f"[{chat_id}] typing=False (timeout)")


async def summarise(chat_id: int):
    """
    grab first X pieces of history
    summarise using model A
    get previous summary if available
    combine summaries if available with model B
    update summary
    delete initially grabbed history (only at this stage in case convo continues during summarisation)

    note: there is possibility of generating 2 summaries simultaneously if
    threshold is low but shouldnt happen reasonably
    """
    print(f"[{chat_id}] Summary initiated")
    summarising_statuses[chat_id] = True

    try:
        to_summarise = get_history(chat_id, HISTORY_LENGTH_TO_SUMMARISE)
        ids = []
        temp = []
        for item in to_summarise:
            ids.append(item["id"])
            for msg in item["input"].split("\n"):
                temp.append(f"{USER_NAME}: {msg}")
            for msg in item["response"].split("\n"):
                temp.append(f"{BOT_NAME}: {msg}")

        to_summarise_text = "\n".join(temp)
        new_summary = await summarise_text(to_summarise_text)

        current_summary = get_summary(chat_id)
        if current_summary != None:
            new_summary = await summarise_text(f"{current_summary}\n{new_summary}")

        set_summary(chat_id, new_summary)
        delete_history(chat_id, ids)

        print(f"[{chat_id}] new summary generated: {new_summary}")

    except Exception as e:
        raise e
    finally:
        summarising_statuses[chat_id] = False


# event handlers


@client.on(events.UserUpdate())
async def user_update(event):
    """
    set typing to true when tg says so
    """
    if not event.typing:
        return

    global client_typing_statuses
    client_typing_statuses[event.chat_id] = True

    print(f"[{event.chat_id}] typing=True (event handler)")

    # restart 6s countdown before setting typing to false
    global cancel_tasks
    if event.chat_id in cancel_tasks and cancel_tasks[event.chat_id]:
        cancel_tasks[event.chat_id].cancel()
    cancel_tasks[event.chat_id] = asyncio.create_task(stop_typing(event.chat_id))


@client.on(events.NewMessage(pattern="\\/clear_history"))
async def on_clear_history(event):  # TODO
    global wait_tasks  # cancel any pending messages
    if event.chat_id in wait_tasks and wait_tasks[event.chat_id]:
        wait_tasks[event.chat_id].cancel()

    await client(
        functions.messages.DeleteHistoryRequest(
            peer=event.chat_id, max_id=-1, revoke=True
        )
    )

    clear_history(event.chat_id)
    delete_summary(event.chat_id)

    global current_message_ids, current_message_parts
    if event.chat_id in current_message_ids:
        del current_message_ids[event.chat_id]
    if event.chat_id in current_message_parts:
        del current_message_parts[event.chat_id]

    raise events.StopPropagation


@client.on(events.NewMessage(pattern="\\/update_history"))
async def on_update_history(event):
    # TODO: consider context of this function call:
    # are there pending messages from user?
    # is bot currently replying?

    # --
    my_id = (await client.get_me(input_peer=True)).user_id
    chat_id = event.chat_id
    min_id = get_history_min_id(chat_id)

    chat_log = []
    async for message in client.iter_messages(
        chat_id, min_id=min_id - 1, max_id=event.message.id
    ):  # ignore command message
        if message.from_id == None or message.from_id.user_id != my_id:
            chat_log.insert(0, ("user", message.text, message.id))
        else:
            chat_log.insert(0, ("bot", message.text, message.id))

    parsed_history = parse_history(chat_log)
    print(f"{my_id=}")
    print(f"{min_id=}")
    pprint(chat_log)
    pprint(parsed_history)
    rewrite_history(chat_id, parsed_history)
    # --

    # delete command message
    await client.delete_messages(chat_id, [event.message.id])

    raise events.StopPropagation


@client.on(events.NewMessage(incoming=True))
async def new_message(event):
    """
    handle new tg message
    set client_typing status
    cancel current reply if have
    """
    chat_id = event.chat_id

    # message received, cancel task and immediately set stop typing
    global cancel_tasks
    if chat_id in cancel_tasks and cancel_tasks[chat_id]:
        cancel_tasks[chat_id].cancel()

    global client_typing_statuses
    client_typing_statuses[chat_id] = False
    print(f"[{chat_id}] typing=False (message received)")

    await event.mark_read()  # mark as read!

    # parse message received
    global current_message_ids, current_message_parts
    if not chat_id in current_message_ids:
        # id of the entire message is that of the first message
        # (not updated on subsequent messages)
        current_message_ids[chat_id] = event.message.id

    if not chat_id in current_message_parts:
        current_message_parts[chat_id] = []
    current_message_parts[chat_id].append(event.raw_text)

    # start wait task before sending a reply (in case subsequent messages come in)
    global wait_tasks
    if chat_id in wait_tasks and wait_tasks[chat_id]:
        wait_tasks[chat_id].cancel()
    wait_tasks[chat_id] = asyncio.create_task(wait_before_reply(event))
