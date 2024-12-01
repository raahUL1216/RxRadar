import json

import faiss
from llama_index.core import SimpleDirectoryReader
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.vector_stores.faiss import FaissVectorStore
from llama_index.readers.file import HTMLTagReader

from llama_index.core import StorageContext
from llama_index.vector_stores.faiss import FaissVectorStore
from llama_index.core import (
	load_index_from_storage
)
from dotenv import load_dotenv, find_dotenv
from llama_index.readers.web import SimpleWebPageReader

load_dotenv(find_dotenv())

import re
# from llama_index.readers.web import SimpleWebPageReader
import requests
from llama_index.core import Document

class MedWebPageReader(SimpleWebPageReader):
    def _remove_links(self, string) -> str:
        """Removes all URLs and * (URL)[text] * patterns from a given string."""
        # Pattern to match * (URL)[text] *
        pattern = r"\*\s*\(https?://[^\)]+\)\[.*?\]\s*\*"
        # Remove the matched patterns
        string = re.sub(pattern, "", string)
        
        # Existing URL removal logic
        def replace_match(match):
            text = match.group(1)
            return text if text else ""
        
        url_pattern = r"https?://(?:www\.)?((?!www\.).)+?"
        return re.sub(url_pattern, replace_match, string)

    def load_data(self, urls):
        if not isinstance(urls, list):
            raise ValueError("urls must be a list of strings.")
        documents = []
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
        }
        for url in urls:
            response = requests.get(url, headers=headers).text
            if self.html_to_text:
                import html2text
                response = html2text.html2text(response)
                response = self._remove_links(response)

            metadata = None
            if self._metadata_fn is not None:
                metadata = self._metadata_fn(url)

            documents.append(Document(text=response, id_=url, metadata=metadata or {}))

        return documents

def create_index():
    # dimensions of text-ada-embedding-002
    d = 1536
    faiss_index = faiss.IndexFlatL2(d)

    # load documents
    parser = HTMLTagReader()
    file_extractor = {".html": parser}
    documents = SimpleDirectoryReader(
        "server/data", file_extractor=file_extractor
    ).load_data()

    vector_store = FaissVectorStore(faiss_index=faiss_index)
    storage_context = StorageContext.from_defaults(
        vector_store=vector_store
    )
    index = VectorStoreIndex.from_documents(
        documents, storage_context=storage_context
    )

    # save index to disk
    index.storage_context.persist()
    print('created med index successfully.')

def get_med_index():
    # load index from disk
	vector_store = FaissVectorStore.from_persist_dir("storage")
	storage_context = StorageContext.from_defaults(
		vector_store=vector_store, persist_dir="storage"
	)
	index = load_index_from_storage(storage_context=storage_context)
	return index

def get_answer(query):
    index = get_med_index()

    query_engine = index.as_query_engine()
    response = query_engine.query(query)

    return response.response


def store_documents(documents):
	index = get_med_index()

	for doc in documents:
		index.insert(document=doc)

	# save index to disk
	index.storage_context.persist()
    
def save_chat(memory):
    """Save memory to file."""
    with open('server/memory.json', 'w') as f:
        json.dump(memory.to_dict(), f, indent=4)
