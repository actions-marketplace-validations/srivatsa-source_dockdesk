try:
    from langchain_community.vectorstores import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain.text_splitter import RecursiveCharacterTextSplitter, Language
    from langchain.schema import Document
    HAS_RAG_DEPS = True
except ImportError:
    HAS_RAG_DEPS = False

import os
from typing import List, Optional
from rich.console import Console

console = Console()

# Map file extensions to LangChain Language enum — built lazily to avoid
# NameError when RAG deps are not installed.
_EXT_LANGUAGE_MAP = None


def _get_ext_language_map():
    """Lazily build and cache the extension→Language mapping."""
    global _EXT_LANGUAGE_MAP
    if _EXT_LANGUAGE_MAP is not None:
        return _EXT_LANGUAGE_MAP
    if not HAS_RAG_DEPS:
        _EXT_LANGUAGE_MAP = {}
        return _EXT_LANGUAGE_MAP
    _EXT_LANGUAGE_MAP = {
        ".py": Language.PYTHON,
        ".js": Language.JS,
        ".jsx": Language.JS,
        ".ts": Language.TS,
        ".tsx": Language.TS,
        ".java": Language.JAVA,
        ".go": Language.GO,
        ".rb": Language.RUBY,
        ".rs": Language.RUST,
        ".cpp": Language.CPP,
        ".c": Language.CPP,
        ".h": Language.CPP,
        ".cs": Language.CSHARP,
        ".scala": Language.SCALA,
        ".swift": Language.SWIFT,
        ".md": Language.MARKDOWN,
        ".markdown": Language.MARKDOWN,
        ".rst": Language.RST,
        ".html": Language.HTML,
        ".php": Language.PHP,
        ".sol": Language.SOL,
        ".kt": Language.KOTLIN,
        ".lua": Language.LUA,
        ".hs": Language.HASKELL,
        ".pl": Language.PERL,
    }
    return _EXT_LANGUAGE_MAP


def _get_splitter_for_file(source: str) -> "RecursiveCharacterTextSplitter":
    """Return an AST-aware text splitter tuned for the file's language.
    
    Uses language-specific separators (function/class boundaries) so that
    chunks align with logical code units instead of cutting mid-function.
    Requires RAG deps to be installed; returns None otherwise.
    """
    if not HAS_RAG_DEPS:
        return None
    
    ext = os.path.splitext(source)[1].lower()
    lang_map = _get_ext_language_map()
    lang = lang_map.get(ext)
    
    if lang:
        try:
            return RecursiveCharacterTextSplitter.from_language(
                language=lang,
                chunk_size=2000,
                chunk_overlap=200,
            )
        except Exception:
            pass  # Fall through to generic splitter
    
    # Generic fallback for unknown languages — larger chunks to avoid splitting functions
    return RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=200,
    )

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

        docs = []
        for text, meta in zip(documents, metadatas):
            source = meta.get("source", "")
            splitter = _get_splitter_for_file(source)
            chunks = splitter.create_documents([text], metadatas=[meta])
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
