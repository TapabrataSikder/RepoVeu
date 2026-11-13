def build_context(results):
    """
    Convert retrieved ChromaDB results into
    readable repository context for the LLM.
    """

    documents = results.get(
        "documents",
        [[]]
    )[0]

    metadatas = results.get(
        "metadatas",
        [[]]
    )[0]

    if not documents:
        return ""

    context_parts = []

    for index, document in enumerate(documents):
        metadata = (
            metadatas[index]
            if index < len(metadatas)
            else {}
        )

        context = (
            f"File: "
            f"{metadata.get('file_path', '')}\n"
            f"Class: "
            f"{metadata.get('class_name', '')}\n"
            f"Symbol: "
            f"{metadata.get('symbol_name', '')}\n"
            f"Type: "
            f"{metadata.get('symbol_type', '')}\n"
            f"Language: "
            f"{metadata.get('language', '')}\n"
            f"Lines: "
            f"{metadata.get('start_line', '')} - "
            f"{metadata.get('end_line', '')}\n\n"
            f"Code:\n"
            f"{document}"
        )

        context_parts.append(context)

    return "\n\n".join(context_parts)

if __name__ == "__main__":
    from app.retrieval.retriever import retrieve_code

    query = (
        "Where is the Spring Boot "
        "application started?"
    )

    results = retrieve_code(
        query,
        top_k=3
    )

    context = build_context(
        results
    )

    print()
    print("=" * 50)
    print("RAG CONTEXT")
    print("=" * 50)
    print()
    print(context)