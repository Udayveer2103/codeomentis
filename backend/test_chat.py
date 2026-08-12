import asyncio

from app.services.chat import (
    handle_chat_message,
    TokenEvent,
    SourcesEvent,
    ErrorEvent,
    DoneEvent,
)

async def main():
    repo_id = "81d7ec8b-2e3c-43ef-abf2-962473e218db"
    user_id = "9a1d390c-f049-4199-8146-503123f4f1f3"

    async for event in handle_chat_message(
        repo_id,
        user_id,
        "Can you explain that more simply?"
    ):
        if isinstance(event, SourcesEvent):
            print("\n===== SOURCES =====")
            for source in event.sources:
                print(source)

        elif isinstance(event, TokenEvent):
            print(event.text, end="", flush=True)

        elif isinstance(event, ErrorEvent):
            print("\nERROR:")
            print(event.message)

        elif isinstance(event, DoneEvent):
            print("\n\nDONE")

asyncio.run(main())