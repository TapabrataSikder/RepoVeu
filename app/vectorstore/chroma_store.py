import chromadb
# --------------------------------------------------
# ChromaDB Client
# --------------------------------------------------
client = chromadb.PersistentClient(
    path="data/chroma"
)
# --------------------------------------------------
# Collection
# --------------------------------------------------
collection = client.get_or_create_collection(
    name="code_chunks"
)
# --------------------------------------------------
# Add Chunks
# --------------------------------------------------
def add_chunks(chunks, embeddings, repository_id):
    """
    Store code chunks and embeddings in ChromaDB.
    Each chunk is associated with a repository_id.
    """
    if not chunks:
        print("No chunks to add.")
        return
    if embeddings is None or len(embeddings) == 0:
        print("No embeddings to add.")
        return
    if len(chunks) != len(embeddings):
        raise ValueError(
            "Number of chunks and embeddings must match."
        )
    if not repository_id:
        raise ValueError(
            "repository_id is required."
        )
    ids = []
    documents = []
    metadatas = []
    for index, chunk in enumerate(chunks):
        ids.append(
            f"{repository_id}:"
            f"{chunk.file_path}:"
            f"{chunk.symbol_name}:"
            f"{chunk.start_line}:"
            f"{index}"
        )
        documents.append(
            chunk.content
        )
        metadatas.append({
            "repository_id": repository_id,
            "file_path": chunk.file_path,
            "language": chunk.language,
            "symbol_name": chunk.symbol_name,
            "symbol_type": chunk.symbol_type,
            "class_name": chunk.class_name,
            "return_type": chunk.return_type,
            "visibility": chunk.visibility,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line
        })
    collection.add(
        ids=ids,
        documents=documents,
        embeddings=[
            embedding.tolist()
            if hasattr(embedding, "tolist")
            else embedding
            for embedding in embeddings
        ],
        metadatas=metadatas
    )
# --------------------------------------------------
# Search Chunks
# --------------------------------------------------
def search_chunks(
    query_embedding,
    repository_id,
    top_k=5
):
    """
    Search only inside the selected repository.
    """
    if query_embedding is None:
        return {
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]]
        }
    if not repository_id:
        raise ValueError(
            "repository_id is required for repository-isolated retrieval."
        )
    if collection.count() == 0:
        return {
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]]
        }
    query_embedding = (
        query_embedding.tolist()
        if hasattr(query_embedding, "tolist")
        else query_embedding
    )
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(
            top_k,
            collection.count()
        ),
        where={
            "repository_id": repository_id
        }
    )
    return results
# --------------------------------------------------
# Count Repository Chunks
# --------------------------------------------------
def count_repository_chunks(repository_id):
    """
    Return the number of chunks belonging
    to a specific repository.
    """
    if not repository_id:
        return 0
    results = collection.get(
        where={
            "repository_id": repository_id
        },
        include=[]
    )
    return len(results.get("ids", []))
# --------------------------------------------------
# Collection Information
# --------------------------------------------------
def get_collection_count():
    """
    Return total number of indexed chunks
    across all repositories.
    """
    return collection.count()
# --------------------------------------------------
# Test
# --------------------------------------------------
if __name__ == "__main__":
    print("=" * 50)
    print("CHROMADB")
    print("=" * 50)
    print(
        f"Collection : {collection.name}"
    )
    print(
        f"Documents  : {collection.count()}"
    )