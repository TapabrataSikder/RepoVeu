import re
from dataclasses import dataclass, field


@dataclass
class ImpactAnalysisResult:
    """
    Structured result produced by the impact analyzer.
    """

    change_target: str = ""
    directly_affected_files: list[str] = field(default_factory=list)
    indirectly_affected_files: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    validation_steps: list[str] = field(default_factory=list)
    change_flow: str = ""
    additional_information_needed: list[str] = field(
        default_factory=list
    )

    def to_markdown(self):
        sections = []

        if self.change_target:
            sections.append(
                f"### Change Target\n\n"
                f"{self.change_target}"
            )

        if self.directly_affected_files:
            files = "\n".join(
                f"- `{file}`"
                for file in self.directly_affected_files
            )

            sections.append(
                "### Directly Affected Files\n\n"
                f"{files}"
            )

        if self.indirectly_affected_files:
            files = "\n".join(
                f"- `{file}`"
                for file in self.indirectly_affected_files
            )

            sections.append(
                "### Indirectly Affected Files\n\n"
                f"{files}"
            )

        if self.change_flow:
            sections.append(
                f"### Change Flow\n\n"
                f"{self.change_flow}"
            )

        if self.risks:
            risks = "\n".join(
                f"- {risk}"
                for risk in self.risks
            )

            sections.append(
                f"### Risks\n\n{risks}"
            )

        if self.validation_steps:
            steps = "\n".join(
                f"- {step}"
                for step in self.validation_steps
            )

            sections.append(
                "### Validation Steps\n\n"
                f"{steps}"
            )

        if self.additional_information_needed:
            information = "\n".join(
                f"- {item}"
                for item in self.additional_information_needed
            )

            sections.append(
                "### Additional Information Needed\n\n"
                f"{information}"
            )

        return "\n\n".join(sections)


class ImpactAnalyzer:
    """
    Analyze which parts of a repository may be affected
    by a proposed code change.

    The analyzer does not modify repository files.
    """

    def __init__(self, llm_generator):
        self.llm_generator = llm_generator

    def analyze(self, question, context):
        """
        Analyze the potential impact of a requested change.

        Parameters
        ----------
        question : str
            The developer's change-impact question.

        context : str | list | dict
            Repository evidence retrieved by the RAG system.

        Returns
        -------
        ImpactAnalysisResult | None
        """

        if not isinstance(question, str):
            raise TypeError(
                "question must be a string."
            )

        if not question.strip():
            raise ValueError(
                "question cannot be empty."
            )

        normalized_context = self._normalize_context(
            context
        )

        if not normalized_context:
            return None

        prompt = self._build_prompt(
            question=question,
            context=normalized_context,
        )

        response = self.llm_generator(prompt)

        if not response:
            return None

        return self._parse_response(response)

    # ==================================================
    # CONTEXT NORMALIZATION
    # ==================================================

    def _normalize_context(self, context):
        if context is None:
            return ""

        if isinstance(context, str):
            return context.strip()

        if isinstance(context, list):
            parts = []

            for item in context:
                if item is None:
                    continue

                if isinstance(item, str):
                    value = item.strip()

                else:
                    value = str(item).strip()

                if value:
                    parts.append(value)

            return "\n\n".join(parts)

        if isinstance(context, dict):
            documents = context.get("documents")

            if isinstance(documents, list):
                flattened = []

                for item in documents:
                    if isinstance(item, list):
                        flattened.extend(item)

                    elif isinstance(item, str):
                        flattened.append(item)

                if flattened:
                    return "\n\n".join(
                        item.strip()
                        for item in flattened
                        if item and item.strip()
                    )

            return str(context).strip()

        return str(context).strip()

    # ==================================================
    # PROMPT
    # ==================================================

    def _build_prompt(self, question, context):
        return f"""
You are an AI software engineering assistant performing
repository impact analysis.

Developer question:

{question}

Repository evidence:

{context}

Your task is to determine which repository files are likely
to be affected by the requested change.

IMPORTANT RULES:

1. Use only the repository evidence provided above.
2. Do not invent files, functions, APIs, dependencies, or
   relationships.
3. Separate directly affected files from indirectly affected
   files.
4. A file should only be listed when the evidence supports
   its relationship to the requested change.
5. If the evidence is insufficient, explicitly say so.
6. Do not propose editing files that are unrelated.
7. Do not modify any repository files.
8. Do not claim certainty when the evidence only supports
   a possibility.

Return the result using exactly these sections:

### Change Target

Describe what part of the system is being changed.

### Directly Affected Files

List files that directly implement or consume the changed
functionality.

Use this format:

- `path/to/file`
  Reason: why this file is directly affected.

### Indirectly Affected Files

List files that may depend on the changed behavior.

Use this format:

- `path/to/file`
  Reason: why this file may be affected.

### Change Flow

Describe the relevant flow from caller to implementation
or from implementation to consumer.

### Risks

List concrete risks supported by the repository evidence.

### Validation Steps

List tests or checks that should be performed after the
change.

### Additional Information Needed

List information that would be required to make the analysis
more certain.

If no additional information is needed, write:

None
"""

    # ==================================================
    # RESPONSE PARSING
    # ==================================================

    def _parse_response(self, response):
        sections = self._extract_sections(
            response
        )

        result = ImpactAnalysisResult()

        result.change_target = sections.get(
            "Change Target",
            "",
        ).strip()

        result.directly_affected_files = (
            self._extract_file_items(
                sections.get(
                    "Directly Affected Files",
                    "",
                )
            )
        )

        result.indirectly_affected_files = (
            self._extract_file_items(
                sections.get(
                    "Indirectly Affected Files",
                    "",
                )
            )
        )

        result.change_flow = sections.get(
            "Change Flow",
            "",
        ).strip()

        result.risks = self._extract_bullets(
            sections.get(
                "Risks",
                "",
            )
        )

        result.validation_steps = (
            self._extract_bullets(
                sections.get(
                    "Validation Steps",
                    "",
                )
            )
        )

        result.additional_information_needed = (
            self._extract_bullets(
                sections.get(
                    "Additional Information Needed",
                    "",
                )
            )
        )

        return result

    # ==================================================
    # SECTION EXTRACTION
    # ==================================================

    def _extract_sections(self, response):
        pattern = re.compile(
            r"###\s+(.+?)\n"
            r"(.*?)(?=\n###\s+|\Z)",
            re.DOTALL,
        )

        sections = {}

        for match in pattern.finditer(response):
            title = match.group(1).strip()
            content = match.group(2).strip()

            sections[title] = content

        return sections

    # ==================================================
    # FILE EXTRACTION
    # ==================================================

    def _extract_file_items(self, text):
        if not text:
            return []

        files = []

        for line in text.splitlines():
            line = line.strip()

            if not line:
                continue

            match = re.search(
                r"`([^`]+)`",
                line,
            )

            if not match:
                continue

            file_path = match.group(1).strip()

            if file_path not in files:
                files.append(file_path)

        return files

    # ==================================================
    # BULLET EXTRACTION
    # ==================================================

    def _extract_bullets(self, text):
        if not text:
            return []

        items = []

        for line in text.splitlines():
            line = line.strip()

            if line.startswith("- "):
                value = line[2:].strip()

                if value and value.lower() != "none":
                    items.append(value)

        return items