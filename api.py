import os
import time
import asyncio
import nlpcloud

import functools
from dotenv import load_dotenv

from db import get_context

load_dotenv()

client = nlpcloud.Client("chatdolphin", os.environ["NLPCLOUD_API_KEY"], gpu=True)

# import datetime
# def get_datetime():
#     tz = datetime.timezone(datetime.timedelta(hours=8))
#     return datetime.datetime.now(tz).strftime("%d %b, %a, %H%Mh").lower()


def run_in_executor(f):
    @functools.wraps(f)
    async def inner(*args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: f(*args, **kwargs))

    return inner


@run_in_executor
def get_response(message, history, current_summary=None):
    start = time.time()
    context = get_context()
    if current_summary:
        context += "\n\n"
        context += current_summary

    resp = client.chatbot(
        message,
        context=context,
        history=history,
    )
    end = time.time()

    return resp["response"], end - start


@run_in_executor
def summarise_text(text: str):
    res = client.summarization(text, size="large")

    return res["summary_text"]
