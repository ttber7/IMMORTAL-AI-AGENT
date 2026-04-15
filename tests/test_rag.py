import os
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import logging

from duckduckgo_search import DDGS
from core.local_rag import LocalRAG

print("Initialization LocalRAG...")
embedder = LocalRAG.initialize_embedder()
store, chunks = LocalRAG.initialize_vector_store(embedder)
rag = LocalRAG(embedder=embedder, vector_store=store, chunks=chunks)

print(rag.search("Lịch sử phát triển của AI?"))

print("Web search testing...")
results = DDGS().text("Thời tiết hôm nay", max_results=2)
print([r.get("title") for r in results])
