# app/analysis/code_explainer.py  

from typing import Any, Dict, List, Optional


# ==================================================
# CODE EXPLAINER
# ==================================================
#
# Purpose:
#   Convert retrieved repository code/context into a
#   structured, developer-friendly explanation.
# ==================================================


class CodeExplainer:
    """
    Repository-aware code explanation engine.

    The class takes retrieved code chunks/context and
    prepares a focused prompt for the LLM.

    The LLM is responsible for explaining the code,
    while this class controls the structure and rules
    of the explanation.
    """

    def __init__(self, llm_generator):
        """
        Initialize the code explainer.

        Parameters
        ----------
        llm_generator:
            A callable that accepts a prompt and returns
            the generated answer.

        Example:
            CodeExplainer(generate_answer)
        """

        if not callable(llm_generator):
            raise TypeError("llm_generator must be callable.")

        self.llm_generator = llm_generator

    # ==================================================
    # PUBLIC API
    # ==================================================

    def explain(
        self,
        question: str,
        context: Any,
    ) -> str:
        """
        Explain repository code using the supplied context.

        Parameters
        ----------
        question:
            The developer's question.

        context:
            Retrieved repository context.

        Returns
        -------
        str
            Developer-friendly explanation.
        """

        # if not isinstance(question, str):
        #     raise TypeError("question must be a string.")

        question = question.strip()

        if not question:
            return "Please provide a question about the codebase."

        normalized_context = self._normalize_context(context)

        if not normalized_context:
            return (
                "I could not find enough relevant code context "
                "to explain this."
            )

        prompt = self._build_prompt(
            question=question,
            context=normalized_context,
        )

        try:
            answer = self.llm_generator(prompt)
        except Exception as exc:
            return (
                "I was unable to generate the code explanation "
                f"because the language model returned an error: {exc}"
            )

        return self._clean_answer(answer)

    # ==================================================
    # CONTEXT NORMALIZATION
    # ==================================================

    def _normalize_context(self, context: Any) -> str:
        """
        Convert different context formats into a single
        readable text representation.

        The retrieval layer may return context as:

            - string
            - list of strings
            - list of dictionaries
            - dictionary
            - objects containing metadata/documents

        This method keeps the explainer independent from
        the exact retrieval implementation.
        """

        if context is None:
            return ""

        if isinstance(context, str):
            return context.strip()

        if isinstance(context, list):
            sections = []

            for index, item in enumerate(context, start=1):
                formatted = self._format_context_item(
                    item,
                    index,
                )

                if formatted:
                    sections.append(formatted)

            return "\n\n".join(sections).strip()

        if isinstance(context, dict):
            formatted = self._format_context_item(
                context,
                1,
            )

            return formatted.strip()

        return str(context).strip()

    def _format_context_item(
        self,
        item: Any,
        index: int,
    ) -> str:
        """
        Format one retrieved context item.

        Supports common Chroma/RAG structures such as:

            {
                "document": "...",
                "metadata": {...}
            }

        or:

            {
                "content": "...",
                "file_path": "...",
                "language": "python"
            }
        """

        if item is None:
            return ""

        if isinstance(item, str):
            return (
                f"--- Retrieved Context {index} ---\n"
                f"{item.strip()}"
            )

        if not isinstance(item, dict):
            return (
                f"--- Retrieved Context {index} ---\n"
                f"{str(item).strip()}"
            )

        document = (
            item.get("document")
            or item.get("content")
            or item.get("text")
            or item.get("code")
            or ""
        )

        metadata = item.get("metadata", {})

        if not isinstance(metadata, dict):
            metadata = {}

        # Some retrieval implementations may place
        # metadata directly inside the item.
        if not metadata:
            metadata = {
                key: value
                for key, value in item.items()
                if key not in {
                    "document",
                    "content",
                    "text",
                    "code",
                    "metadata",
                }
            }

        lines = [
            f"--- Retrieved Context {index} ---"
        ]

        file_path = metadata.get("file_path")

        if file_path:
            lines.append(f"File: {file_path}")

        language = metadata.get("language")

        if language:
            lines.append(f"Language: {language}")

        symbol_name = metadata.get("symbol_name")

        if symbol_name:
            lines.append(f"Symbol: {symbol_name}")

        symbol_type = metadata.get("symbol_type")

        if symbol_type:
            lines.append(f"Symbol Type: {symbol_type}")

        class_name = metadata.get("class_name")

        if class_name:
            lines.append(f"Class: {class_name}")

        start_line = metadata.get("start_line")
        end_line = metadata.get("end_line")

        if start_line is not None and end_line is not None:
            lines.append(
                f"Lines: {start_line}-{end_line}"
            )
        elif start_line is not None:
            lines.append(
                f"Start Line: {start_line}"
            )

        lines.append("")

        if document:
            lines.append(str(document).strip())
        else:
            lines.append(
                "[No source code was available for this context item.]"
            )

        return "\n".join(lines).strip()

    # ==================================================
    # PROMPT BUILDING
    # ==================================================

    def _build_prompt(
        self,
        question: str,
        context: str,
    ) -> str:
        """
        Build the repository-aware explanation prompt.

        The prompt forces the model to stay grounded in
        retrieved repository evidence.
        """

        return f"""
You are an AI Software Engineering Assistant helping a
developer understand an unfamiliar codebase.

Your task is to explain the provided repository code
accurately and clearly.

==================================================
DEVELOPER QUESTION
==================================================

{question}

==================================================
REPOSITORY CONTEXT
==================================================

{context}

==================================================
IMPORTANT RULES
==================================================

1. Base your explanation primarily on the provided
   repository context.

2. Do not invent files, functions, classes, APIs,
   variables, database tables, endpoints, or behavior
   that are not supported by the context.

3. If the provided context is insufficient to answer
   something confidently, explicitly say so.

4. Distinguish clearly between:
   - what the code actually does
   - what can reasonably be inferred
   - what cannot be determined from the retrieved code

5. When mentioning a file, use its actual file path
   from the retrieved context whenever available.

6. When mentioning a function, class, or method, use
   its actual name from the retrieved context.

7. Do not rewrite the entire source code unless the
   developer explicitly asks for it.

8. Keep the explanation useful to a software developer.

==================================================
EXPLANATION STRUCTURE
==================================================

Provide the answer using the following structure
when the information is available:

### Direct Answer
Give a concise answer to the developer's question.

### How It Works
Explain the relevant execution flow step by step.

### Important Code
Identify the most relevant functions, classes,
methods, or files.

### Data / Control Flow
Explain how information moves through the relevant
parts of the code.

### Dependencies
Mention important functions, modules, classes,
services, or components that the code depends on.

### Developer Insight
Explain why this implementation matters and what
a developer working on this codebase should understand.

### Evidence
Reference the relevant file paths and symbols from
the retrieved context.

Do not create sections that have no useful information.
Avoid unnecessary repetition.
""".strip()

    # ==================================================
    # ANSWER CLEANING
    # ==================================================

    def _clean_answer(self, answer: Any) -> str:
        """
        Clean and normalize the LLM response.
        """

        if answer is None:
            return (
                "The language model did not return an explanation."
            )

        if not isinstance(answer, str):
            answer = str(answer)

        answer = answer.strip()

        if not answer:
            return (
                "The language model returned an empty explanation."
            )

        return answer


# ==================================================
# CONVENIENCE FUNCTION
# ==================================================

def explain_code(
    question: str,
    context: Any,
    llm_generator,
) -> str:
    """
    Convenience wrapper around CodeExplainer.

    Example:

        answer = explain_code(
            question,
            retrieved_context,
            generate_answer,
        )
    """

    explainer = CodeExplainer(
        llm_generator=llm_generator
    )

    return explainer.explain(
        question=question,
        context=context,
    )


# ==================================================
# LOCAL TEST
# ==================================================

if __name__ == "__main__":

    def mock_llm(prompt: str) -> str:
        """
        Simple local mock used only for testing the
        CodeExplainer without calling an actual API.
        """

        print("\n========== GENERATED PROMPT ==========\n")
        print(prompt)

        return (
            "### Direct Answer\n"
            "The retrieved code shows how the requested "
            "functionality is implemented.\n\n"
            "### How It Works\n"
            "The function receives the input, processes it, "
            "and returns the resulting value.\n\n"
            "### Evidence\n"
            "The explanation is based on the retrieved "
            "repository context."
        )

    sample_context = [
        {
            "document": """
def validate_github_url(url):
    if not url:
        return False

    if not url.startswith("https://github.com/"):
        return False

    return True
""",
            "metadata": {
                "file_path": "app/ingestion/url_validator.py",
                "language": "python",
                "symbol_name": "validate_github_url",
                "symbol_type": "function",
                "start_line": 1,
                "end_line": 8,
            },
        },
        {
            "document": """
def analyze_repository(repository_path):
    files = discover_files(repository_path)
    return scan_repository(files)
""",
            "metadata": {
                "file_path": "app/main.py",
                "language": "python",
                "symbol_name": "analyze_repository",
                "symbol_type": "function",
                "start_line": 10,
                "end_line": 13,
            },
        },
    ]

    explainer = CodeExplainer(
        llm_generator=mock_llm
    )

    result = explainer.explain(
        question="How is the GitHub repository validated?",
        context=sample_context,
    )

    print("\n========== FINAL ANSWER ==========\n")
    print(result)