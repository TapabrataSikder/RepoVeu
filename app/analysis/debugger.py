from dataclasses import dataclass, field
from typing import Any, Dict, List

# ==================================================
# DEBUGGING RESULT
# ==================================================

@dataclass
class DebuggingResult:
    """
    Structured result produced by the debugging engine.

    The result intentionally separates diagnosis from
    code modification.
    """
    problem: str
    root_cause: str
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    fix_plan: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    validation_steps: List[str] = field(default_factory=list)
    confidence: str = "unknown"
    additional_information_needed: List[str] = field(default_factory=list)


# ==================================================
# DEBUGGER
# ==================================================

class Debugger:
    """
    Repository-aware debugging engine.

    Responsibilities:
        1. Understand the reported problem.
        2. Examine retrieved repository context.
        3. Identify the likely root cause.
        4. Identify evidence supporting the diagnosis.
        5. Produce a fix plan.
        6. Suggest validation steps.

    This class does NOT:
        - modify repository files
        - automatically apply fixes
        - execute arbitrary code
        - execute tests
        - generate a final patch
    """

    def __init__(self, llm_generator):
        """
        Initialize the debugger.

        Parameters
        ----------
        llm_generator:
            Callable that accepts a prompt and returns
            an LLM-generated response.
        """
        if not callable(llm_generator):
            raise TypeError("llm_generator must be callable.")
        self.llm_generator = llm_generator

    # ==================================================
    # PUBLIC API
    # ==================================================

    def debug(self, question: str, context: Any) -> DebuggingResult:
        """
        Analyze a reported code problem.
        """
        if not isinstance(question, str):
            raise TypeError("question must be a string.")

        question = question.strip()

        if not question:
            return DebuggingResult(
                problem="No debugging question was provided.",
                root_cause="Unknown",
                confidence="low",
                additional_information_needed=[
                    "Provide the error or describe the observed behavior."
                ],
            )

        normalized_context = self._normalize_context(context)

        if not normalized_context:
            return DebuggingResult(
                problem=question,
                root_cause=(
                    "Unable to determine the root cause because no "
                    "relevant repository context was retrieved."
                ),
                confidence="low",
                additional_information_needed=[
                    "Relevant source code",
                    "Error message or stack trace",
                    "Steps to reproduce the issue",
                ],
            )

        prompt = self._build_prompt(
            question=question,
            context=normalized_context,
        )

        try:
            raw_response = self.llm_generator(prompt)
        except Exception as exc:
            return DebuggingResult(
                problem=question,
                root_cause=(
                    "The debugging analysis could not be completed "
                    f"because the language model returned an error: {exc}"
                ),
                confidence="unknown",
                additional_information_needed=[
                    "Retry the debugging request."
                ],
            )

        return self._parse_response(
            question=question,
            response=raw_response,
        )

    # ==================================================
    # CONTEXT NORMALIZATION
    # ==================================================

    def _normalize_context(self, context: Any) -> str:
        """
        Convert retrieved context into a consistent text representation.

        Supports:
            - string
            - list of strings
            - list of dictionaries
            - dictionary
        """
        if context is None:
            return ""

        if isinstance(context, str):
            return context.strip()

        if isinstance(context, list):
            sections = []

            for index, item in enumerate(context, start=1):
                formatted = self._format_context_item(item, index)

                if formatted:
                    sections.append(formatted)

            return "\n\n".join(sections).strip()

        if isinstance(context, dict):
            return self._format_context_item(
                item=context,
                index=1,
            ).strip()

        return str(context).strip()

    # ==================================================
    # CONTEXT ITEM FORMATTER
    # ==================================================

    def _format_context_item(self, item: Any, index: int) -> str:
        """
        Format a single retrieved code chunk.
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

        lines = [f"--- Retrieved Context {index} ---"]

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
            lines.append(f"Lines: {start_line}-{end_line}")
        elif start_line is not None:
            lines.append(f"Start Line: {start_line}")

        lines.append("")

        if document:
            lines.append(str(document).strip())
        else:
            lines.append("[No source code available]")

        return "\n".join(lines).strip()

    # ==================================================
    # PROMPT BUILDER
    # ==================================================

    def _build_prompt(self, question: str, context: str) -> str:
        """
        Build the debugging prompt.

        The prompt forces the LLM to distinguish between
        evidence and assumptions.
        """
        return f"""
DEBUGGER ANALYSIS PROMPT

==================================================
DEVELOPER PROBLEM
==================================================

{question}

==================================================
RETRIEVED REPOSITORY CODE
==================================================

{context}

==================================================
DEBUGGING RULES
==================================================

1. Base the diagnosis primarily on the retrieved repository code.

2. Do not invent files, functions, classes, variables, APIs,
   database tables, endpoints, or execution paths.

3. Do not assume that a piece of code exists unless it appears
   in the provided context.

4. Clearly distinguish:
   - confirmed evidence
   - likely explanation
   - uncertain assumptions

5. If the retrieved context is insufficient to identify the
   root cause, say so explicitly.

6. Do not claim that a fix has been tested.

7. Do not claim that code has been modified.

8. Do not generate a complete replacement file.

9. Do not produce a code patch yet.

10. Focus on diagnosis and an actionable fix plan.

==================================================
REQUIRED RESPONSE FORMAT
==================================================

Return the response using exactly these sections:

### Problem

Describe the problem reported by the developer.

### Root Cause

Explain the most likely root cause.

If the root cause cannot be determined confidently,
say that explicitly.

### Evidence

List the repository evidence supporting the diagnosis.

For each important piece of evidence include:

- File
- Symbol if available
- Relevant lines if available
- Explanation

### Fix Plan

Provide a numbered sequence of recommended changes.

Do not write the actual patch yet.

### Risks

Describe possible side effects or risks associated
with the proposed fix.

If there are no obvious risks, say so.

### Validation Steps

Describe how a developer should verify that the fix works.

Include relevant tests, commands, or behaviors to verify
when they can be determined from the repository context.

Do not claim that these validations have already been run.

### Confidence

Use exactly one of:

HIGH
MEDIUM
LOW

### Additional Information Needed

If additional information is required, list it here.

If no additional information is required, write:

None
""".strip()

    # ==================================================
    # RESPONSE PARSER
    # ==================================================

    def _parse_response(
        self,
        question: str,
        response: Any,
    ) -> DebuggingResult:
        """
        Parse the structured LLM response into a DebuggingResult.
        """
        if response is None:
            return DebuggingResult(
                problem=question,
                root_cause=(
                    "The language model returned no debugging analysis."
                ),
                confidence="unknown",
            )

        if not isinstance(response, str):
            response = str(response)

        response = response.strip()

        if not response:
            return DebuggingResult(
                problem=question,
                root_cause=(
                    "The language model returned an empty debugging analysis."
                ),
                confidence="unknown",
            )

        sections = self._extract_sections(response)

        problem = sections.get("Problem", question)

        root_cause = sections.get(
            "Root Cause",
            "The root cause could not be determined from the generated analysis.",
        )

        evidence_text = sections.get("Evidence", "")
        fix_plan_text = sections.get("Fix Plan", "")
        risks_text = sections.get("Risks", "")
        validation_text = sections.get("Validation Steps", "")
        confidence = sections.get("Confidence", "UNKNOWN").strip().upper()

        if confidence not in {"HIGH", "MEDIUM", "LOW"}:
            confidence = "UNKNOWN"

        additional_information_text = sections.get(
            "Additional Information Needed",
            "",
        )

        return DebuggingResult(
            problem=problem.strip(),
            root_cause=root_cause.strip(),
            evidence=self._parse_evidence(evidence_text),
            fix_plan=self._parse_list(fix_plan_text),
            risks=self._parse_list(risks_text),
            validation_steps=self._parse_list(validation_text),
            confidence=confidence.lower(),
            additional_information_needed=self._parse_list(
                additional_information_text
            ),
        )

    # ==================================================
    # SECTION EXTRACTION
    # ==================================================

    def _extract_sections(self, response: str) -> Dict[str, str]:
        """
        Extract markdown sections from the LLM response.

        Handles:
            ### Problem
            **Problem**
            Problem
        """
        section_names = [
            "Problem",
            "Root Cause",
            "Evidence",
            "Fix Plan",
            "Risks",
            "Validation Steps",
            "Confidence",
            "Additional Information Needed",
        ]

        sections = {}
        current_section = None
        current_lines = []

        for line in response.splitlines():
            stripped = line.strip()
            normalized = stripped.strip("*# ").strip().lower()

            matched_section = None

            for section_name in section_names:
                if normalized == section_name.lower():
                    matched_section = section_name
                    break

            if matched_section:
                if current_section is not None:
                    sections[current_section] = "\n".join(
                        current_lines
                    ).strip()

                current_section = matched_section
                current_lines = []
                continue

            if current_section is not None:
                current_lines.append(line)

        if current_section is not None:
            sections[current_section] = "\n".join(
                current_lines
            ).strip()

        return sections

    # ==================================================
    # LIST PARSER
    # ==================================================

    def _parse_list(self, text: str) -> List[str]:
        """
        Convert bullet points or numbered items into a Python list.
        """
        if not text:
            return []

        results = []

        for line in text.splitlines():
            line = line.strip()

            if not line:
                continue

            line = self._clean_markdown_prefix(line)

            if line:
                results.append(line)

        return results

    def _clean_markdown_prefix(self, line: str) -> str:
        """
        Remove common Markdown list formatting.
        """
        line = line.strip()

        if line.startswith("- "):
            return line[2:].strip()

        if line.startswith("* "):
            return line[2:].strip()

        if line.startswith("+ "):
            return line[2:].strip()

        parts = line.split(". ", 1)

        if len(parts) == 2 and parts[0].isdigit():
            return parts[1].strip()

        return line

    # ==================================================
    # EVIDENCE PARSER
    # ==================================================

    def _parse_evidence(
        self,
        text: str,
    ) -> List[Dict[str, Any]]:
        """
        Convert evidence text into structured evidence objects.
        """
        if not text:
            return []

        evidence_items = []
        current_item = []

        for line in text.splitlines():
            stripped = line.strip()

            if not stripped:
                continue

            normalized = stripped.strip("* ").strip().lower()

            is_new_item = (
                normalized.startswith("file:")
                or normalized.startswith("**file:**")
                or (
                    len(stripped) >= 3
                    and stripped[0].isdigit()
                    and ". " in stripped
                )
            )

            if is_new_item:
                if current_item:
                    evidence_items.append(
                        self._format_evidence_item(current_item)
                    )

                current_item = [stripped]
            else:
                current_item.append(stripped)

        if current_item:
            evidence_items.append(
                self._format_evidence_item(current_item)
            )

        if not evidence_items:
            evidence_items.append({
                "description": text.strip()
            })

        return evidence_items

    # ==================================================
    # EVIDENCE FORMATTER
    # ==================================================

    def _format_evidence_item(
        self,
        lines: List[str],
    ) -> Dict[str, Any]:
        """
        Convert one evidence block into a dictionary.
        """
        item = {}
        description_parts = []

        for line in lines:
            clean_line = line.strip()
            clean_line = self._clean_markdown_prefix(clean_line)
            clean_line = clean_line.strip("* ").strip()

            lower_line = clean_line.lower()

            if lower_line.startswith("file:"):
                item["file"] = clean_line[len("file:"):].strip()
                continue

            if lower_line.startswith("symbol:"):
                item["symbol"] = clean_line[len("symbol:"):].strip()
                continue

            if lower_line.startswith("lines:"):
                item["lines"] = clean_line[len("lines:"):].strip()
                continue

            if lower_line.startswith("relevant lines:"):
                item["lines"] = clean_line[len("relevant lines:"):].strip()
                continue

            if clean_line:
                description_parts.append(clean_line)

        if description_parts:
            item["description"] = " ".join(description_parts)

        return item


# ==================================================
# CONVENIENCE FUNCTION
# ==================================================

def debug_code(
    question: str,
    context: Any,
    llm_generator,
) -> DebuggingResult:
    """
    Convenience wrapper around Debugger.
    """
    debugger = Debugger(
        llm_generator=llm_generator
    )

    return debugger.debug(
        question=question,
        context=context,
    )


# ==================================================
# LOCAL TEST
# ==================================================

if __name__ == "__main__":

    def mock_llm(prompt: str) -> str:
        """
        Mock LLM used for local testing.

        No real API call is made.
        """
        print()
        print("=" * 70)
        print("GENERATED DEBUGGING PROMPT")
        print("=" * 70)
        print()
        print(prompt)

        return """
### Problem

The repository URL validation is rejecting some
valid GitHub repository URLs.

### Root Cause

The validation logic only checks whether the URL
starts with the expected GitHub prefix. It does not
validate the repository owner and repository name
structure.

### Evidence

- File: app/ingestion/url_validator.py
- Symbol: validate_github_url
- Lines: 1-8
- The function only checks whether the URL is empty
  and whether it starts with the GitHub HTTPS prefix.

### Fix Plan

1. Parse the GitHub URL into its owner and repository components.
2. Validate that both components are present.
3. Handle optional .git suffixes consistently.
4. Add tests for valid and invalid GitHub URLs.

### Risks

Changing URL validation could reject URLs that were
previously accepted by the application.

### Validation Steps

1. Test a valid GitHub repository URL.
2. Test an invalid GitHub URL.
3. Test an empty URL.
4. Test a URL with a .git suffix.

### Confidence

HIGH

### Additional Information Needed

None
""".strip()

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
        }
    ]

    debugger = Debugger(
        llm_generator=mock_llm
    )

    result = debugger.debug(
        question=(
            "Why is the GitHub URL validator "
            "accepting invalid repository URLs?"
        ),
        context=sample_context,
    )

    print()
    print("=" * 70)
    print("STRUCTURED DEBUGGING RESULT")
    print("=" * 70)
    print()

    print(f"Problem: {result.problem}")
    print()
    print(f"Root Cause: {result.root_cause}")
    print()
    print(f"Confidence: {result.confidence}")
    print()
    print("Evidence:")

    for evidence in result.evidence:
        print(f"  {evidence}")

    print()
    print("Fix Plan:")

    for step in result.fix_plan:
        print(f"  - {step}")

    print()
    print("Risks:")

    for risk in result.risks:
        print(f"  - {risk}")

    print()
    print("Validation Steps:")

    for step in result.validation_steps:
        print(f"  - {step}")

    print()
    print("Additional Information Needed:")

    for item in result.additional_information_needed:
        print(f"  - {item}")