import asyncio

from app.services.llm import stream_text, LLMServiceError


async def main():
    try:
        print("Streaming: ", end="", flush=True)

        async for token in stream_text(
            prompt="Count from 1 to 10. Output only the numbers separated by spaces.",
            system="You are a terse assistant.",
        ):
            print(token, end="", flush=True)

        print("\nSUCCESS")

    except LLMServiceError as e:
        print(f"\nLLM SERVICE ERROR: {e}")


asyncio.run(main())