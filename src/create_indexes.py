# create_indexes.py
import os
from langchain_unstructured import UnstructuredLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
import faiss
import uuid
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_openai import AzureOpenAIEmbeddings
from dotenv import load_dotenv
import os

load_dotenv()

AZURE_API_KEY = os.getenv("AZURE_OPENAI_EMBEDDINGS_KEY")
AZURE_DEPLOYMENT_NAME = os.getenv("AZURE_DEPLOYMENT_NAME")
AZURE_OPENAI_EMBEDDINGS_ENDPOINT = os.getenv("AZURE_OPENAI_EMBEDDINGS_ENDPOINT")
AZURE_OPENAI_EMBEDDINGS_API_VERSION = os.getenv("AZURE_OPENAI_EMBEDDINGS_API_VERSION")


# create_indexes.py
import os
import pickle
import time
from langchain_community.document_loaders import PyMuPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores import FAISS
import faiss
import uuid


def load_and_index_pdfs(pdf_directory):
    embedding_model = AzureOpenAIEmbeddings(
        azure_deployment=AZURE_DEPLOYMENT_NAME,
        azure_endpoint=AZURE_OPENAI_EMBEDDINGS_ENDPOINT,
        api_version=AZURE_OPENAI_EMBEDDINGS_API_VERSION,
        api_key=AZURE_API_KEY,
    )
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=200)
    index_map = {}
    book_titles = {
        "mechanics_vol1.pdf": "DC Pandey Mechanics Volume 1",
        "mechanics_vol2.pdf": "DC Pandey Mechanics Volume 2",
        "waves_thermodynamics.pdf": "DC Pandey Waves and Thermodynamics",
        "electricity_magnetism.pdf": "DC Pandey Electricity and Magnetism",
        "optics_modern.pdf": "DC Pandey Optics and Modern Physics",
    }

    os.makedirs("./documents_cache/", exist_ok=True)
    os.makedirs("./indexes/", exist_ok=True)

    for filename in os.listdir(pdf_directory):
        if filename.endswith(".pdf"):
            file_path = os.path.join(pdf_directory, filename)
            print(f"Processing {file_path}...")

            doc_cache_path = f"./documents_cache/{filename.split('.')[0]}_docs.pkl"
            index_name = f"faiss_index_{filename.split('.')[0]}"
            save_path = os.path.join("./indexes/", index_name)
            checkpoint_path = f"./indexes/{filename.split('.')[0]}_checkpoint.pkl"

            if os.path.exists(save_path) and not os.path.exists(checkpoint_path):
                print(f"Index already exists for {filename} at {save_path}. Skipping.")
                index_map[filename] = save_path
                continue

            if os.path.exists(doc_cache_path):
                print(f"Loading cached documents from {doc_cache_path}...")
                with open(doc_cache_path, "rb") as f:
                    documents = pickle.load(f)
            else:
                print(f"Loading PDF {file_path} with PyMuPDFLoader...")
                loader = PyMuPDFLoader(file_path)
                documents = loader.load()
                with open(doc_cache_path, "wb") as f:
                    pickle.dump(documents, f)
                print(f"Saved documents to {doc_cache_path}")

            book_title = book_titles.get(filename, "Unknown DC Pandey Book")
            for doc in documents:
                doc.metadata["book_title"] = book_title
                doc.metadata["source_file"] = filename
                if "page" in doc.metadata:
                    doc.metadata["page"] = doc.metadata["page"] + 1  # 1-based

            chunks = text_splitter.split_documents(documents)
            print(f"Split {filename} into {len(chunks)} chunks.")

            if not chunks:
                print(
                    f"Warning: No chunks extracted from {filename}. Skipping indexing."
                )
                continue

            dimension = 3072  # For text-embedding-3-large
            faiss_index = faiss.IndexFlatL2(dimension)
            vector_store = FAISS(
                embedding_function=embedding_model,
                index=faiss_index,
                docstore=InMemoryDocstore(),
                index_to_docstore_id={},
            )

            chunk_texts = [chunk.page_content for chunk in chunks]
            chunk_ids = [str(uuid.uuid4()) for _ in chunks]
            chunk_metadatas = [chunk.metadata for chunk in chunks]

            batch_size = 50  # Smaller batch size to respect rate limits
            start_idx = 0

            # Load checkpoint if exists
            if os.path.exists(checkpoint_path):
                with open(checkpoint_path, "rb") as f:
                    checkpoint = pickle.load(f)
                start_idx = checkpoint["last_idx"]
                vector_store = FAISS.load_local(
                    save_path, embedding_model, allow_dangerous_deserialization=True
                )
                print(f"Resuming from checkpoint at index {start_idx}...")

            # Process chunks in batches
            for i in range(start_idx, len(chunks), batch_size):
                batch_texts = chunk_texts[i : i + batch_size]
                batch_ids = chunk_ids[i : i + batch_size]
                batch_metadatas = chunk_metadatas[i : i + batch_size]

                print(
                    f"Embedding batch {i // batch_size + 1} of {len(chunks) // batch_size + 1}..."
                )
                try:
                    vector_store.add_texts(
                        texts=batch_texts, ids=batch_ids, metadatas=batch_metadatas
                    )
                except Exception as e:
                    print(
                        f"Error during embedding: {e}. Saving progress and retrying later."
                    )
                    break

                # Save checkpoint
                with open(checkpoint_path, "wb") as f:
                    pickle.dump({"last_idx": i + batch_size}, f)
                vector_store.save_local(save_path)

                # Throttle to avoid rate limits (e.g., 1 request per 2 seconds)
                time.sleep(2)

            # Clean up checkpoint if completed
            if i + batch_size >= len(chunks) and os.path.exists(checkpoint_path):
                os.remove(checkpoint_path)
                print(f"Completed embedding for {filename}. Checkpoint removed.")

            index_map[filename] = save_path
            print(f"Saved index for {filename} at {save_path}")

    return index_map


def main():
    pdf_directory = "/home/aitutor/src/Data_sources/physics/"
    index_map = load_and_index_pdfs(pdf_directory)
    print("\nIndex creation completed. Index map:")
    for pdf, path in index_map.items():
        print(f"{pdf}: {path}")


if __name__ == "__main__":
    main()
