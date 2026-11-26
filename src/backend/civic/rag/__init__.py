"""Civic RAG: retrieval over curated BKK regulation snippets + grounded Thai answers."""

from .retriever import CivicRetriever, Document, Hit, load_documents
from .service import RagAnswer, RagService

__all__ = ["CivicRetriever", "Document", "Hit", "load_documents", "RagAnswer", "RagService"]
