# To run this file indepently
# python -m app.analysis.repository_analyzer

from app.ingestion.file_discover import discover_files
from app.ingestion.file_reader import read_file
from app.analysis.java_analyzer import extract_java_methods

from app.analysis.language_detector import detect_language
from app.analysis.python_analyzer import analyze_python_code
from app.analysis.tree_sitter_analyzer import extract_javascript_functions


def analyze_repository(repository_path):

    files = discover_files(repository_path)

    print(f"\nRepository: {repository_path}")
    print(f"Files discovered: {len(files)}")

    symbols = []

    for file_path in files:

        print(f"\nProcessing: {file_path}")

        content = read_file(file_path)

        if content is None:
            print("  Could not read file")
            continue

        language = detect_language(file_path)

        print(f"  Language: {language}")

        if language is None:
            print("  Skipped: unsupported language")
            continue

        try:

            if language == "python":

                file_symbols = analyze_python_code(
                    content,
                    file_path=str(file_path)
                )

            elif language in {"javascript", "js"}:

                file_symbols = extract_javascript_functions(
                    content,
                    file_path=str(file_path)
                )

            elif language == "java":
                file_symbols = extract_java_methods(
                    content,
                    file_path=str(file_path)
                )
                
            else:
                print("  Skipped: analyzer not available")
                continue

        except Exception as e:
            print(f"  Analysis error: {e}")
            continue

        print(f"  Symbols found: {len(file_symbols)}")
        symbols.extend(file_symbols)

    return symbols


if __name__ == "__main__":

    repository_path = (
        "data/repositories/"
        "TapabrataSikder_Spring-Boot"
    )

    symbols = analyze_repository(
        repository_path
    )

    print()
    print("=" * 50)
    print("REPOSITORY CODE ANALYSIS")
    print("=" * 50)

    print(
        f"\nTotal symbols found: "
        f"{len(symbols)}"
    )

    for symbol in symbols:

        print()
        print("-" * 50)

        print(f"Type       : {symbol.type}")
        print(f"Name       : {symbol.name}")
        print(f"Language   : {symbol.language}")
        print(f"File       : {symbol.file_path}")

        print(
            f"Lines      : "
            f"{symbol.start_line} - "
            f"{symbol.end_line}"
        )

        print(
            f"Parameters : "
            f"{symbol.parameters}"
        )

        print(
            f"Calls      : "
            f"{symbol.calls}"
        )