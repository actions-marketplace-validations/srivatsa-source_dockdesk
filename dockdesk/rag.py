try:
    from langchain_community.vectorstores import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain.schema import Document
    HAS_RAG_DEPS = True
except ImportError:
    HAS_RAG_DEPS = False

import os
from typing import List
from rich.console import Console

console = Console()

class CodeRetriever:
    def __init__(self, persist_directory=".chroma_db"):
        self.persist_directory = persist_directory
        self.vector_store = None
        self.retriever = None

        if HAS_RAG_DEPS:
            # Use a small, fast model
            try:
                self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not load embeddings: {e}. RAG disabled.[/yellow]")
                self.embeddings = None
        else:
            self.embeddings = None

    def _load_existing(self) -> bool:
        """Load existing Chroma index if present."""
        if not HAS_RAG_DEPS or not self.embeddings:
            return False
        if self.vector_store:
            return True

        if os.path.exists(self.persist_directory):
            try:
                self.vector_store = Chroma(
                    embedding=self.embeddings,
                    persist_directory=self.persist_directory
                )
                self.retriever = self.vector_store.as_retriever(search_kwargs={"k": 5})
                console.print("[dim]Reusing cached RAG index[/dim]")
                return True
            except Exception as e:
                console.print(f"[yellow]RAG cache load failed, rebuilding: {e}[/yellow]")
        return False

    def index_documents(self, documents: List[str], metadatas: List[dict]):
        if not HAS_RAG_DEPS or not self.embeddings:
            return

        # Reuse existing index when possible
        reused = self._load_existing()

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            language="python"
        )
        
        docs = []
        for text, meta in zip(documents, metadatas):
            chunks = text_splitter.create_documents([text], metadatas=[meta])
            docs.extend(chunks)

        if not docs:
            return

        if reused and self.vector_store:
            console.print(f"[cyan]Adding {len(docs)} new chunks to cached RAG index...[/cyan]")
            self.vector_store.add_documents(docs)
        else:
            console.print(f"[cyan]Indexing {len(docs)} code chunks...[/cyan]")
            self.vector_store = Chroma.from_documents(
                documents=docs,
                embedding=self.embeddings,
                persist_directory=self.persist_directory
            )
        self.retriever = self.vector_store.as_retriever(search_kwargs={"k": 5})

    def query(self, question: str) -> str:
        if not self.retriever:
            return ""
        
        results = self.retriever.invoke(question)
        return "\n\n".join([f"--- Context from {d.metadata.get('source', 'unknown')} ---\n{d.page_content}" for d in results])
