# To run this file independently:
# python -m app.ingestion.code_chunker

from app.analysis.repository_analyzer import analyze_repository
from app.ingestion.file_reader import read_file
from app.ingestion.code_chunk import CodeChunk
from app.embeddings.embedder import generate_embeddings


def create_symbol_chunks(symbols):
    chunks = []

    for symbol in symbols:
        content = read_file(symbol.file_path)

        if content is None:
            continue

        lines = content.splitlines()

        start_index = symbol.start_line - 1
        end_index = symbol.end_line

        symbol_code = "\n".join(
            lines[start_index:end_index]
        )

        if not symbol_code.strip():
            continue

        chunk = CodeChunk(
            content=symbol_code,
            file_path=symbol.file_path,
            language=symbol.language,
            symbol_name=symbol.name,
            symbol_type=symbol.type,
            class_name=symbol.class_name,
            return_type=symbol.return_type,
            visibility=symbol.visibility,
            annotations=symbol.annotations,
            parameters=symbol.parameters,
            calls=symbol.calls,
            start_line=symbol.start_line,
            end_line=symbol.end_line
        )

        chunks.append(chunk)

    return chunks


if __name__ == "__main__":

    repository_path = (
        "data/repositories/"
        "TapabrataSikder_Spring-Boot"
    )

    symbols = analyze_repository(
        repository_path
    )

    chunks = create_symbol_chunks(
        symbols
    )

    texts = [
        chunk.content
        for chunk in chunks
    ]

    embeddings = generate_embeddings(
        texts
    )

    print("=" * 50)
    print("CODE CHUNKING + EMBEDDING")
    print("=" * 50)

    print(
        f"Total symbols    : {len(symbols)}"
    )

    print(
        f"Total chunks     : {len(chunks)}"
    )

    print(
        f"Total embeddings : {len(embeddings)}"
    )

    for index, chunk in enumerate(
        chunks,
        start=1
    ):

        print()
        print("-" * 50)

        print(
            f"Chunk       : {index}"
        )

        print(
            f"Symbol      : {chunk.symbol_name}"
        )

        print(
            f"Type        : {chunk.symbol_type}"
        )

        print(
            f"Class       : {chunk.class_name}"
        )

        print(
            f"Language    : {chunk.language}"
        )

        print(
            f"File        : {chunk.file_path}"
        )

        print(
            f"Return Type : {chunk.return_type}"
        )

        print(
            f"Visibility  : {chunk.visibility}"
        )

        print(
            f"Annotations : {chunk.annotations}"
        )

        print(
            f"Parameters  : {chunk.parameters}"
        )

        print(
            f"Calls       : {chunk.calls}"
        )

        print(
            f"Lines       : "
            f"{chunk.start_line} - "
            f"{chunk.end_line}"
        )

        print(
            f"Embedding   : "
            f"{len(embeddings[index - 1])} dimensions"
        )

        print()
        print("Code:")
        print(chunk.content)