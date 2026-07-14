import asyncio
from app.services.embeddings import embed_query

async def main():
    vector = await embed_query("How does the ingestion pipeline work?")
    print(len(vector))
    print(vector[:5])

asyncio.run(main())