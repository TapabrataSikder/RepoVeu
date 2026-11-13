from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ChangeStep:
    """
    Represents one step in a proposed code change.
    """

    order: int
    file_path: str
    symbol_name: str = ""
    change: str = ""
    reason: str = ""
    dependencies: List[str] = field(default_factory=list)
    risk: str = "medium"


@dataclass
class ChangePlan:
    """
    Structured representation of an engineering change plan.
    """

    change_request: str
    target: str = ""
    summary: str = ""

    steps: List[ChangeStep] = field(default_factory=list)

    affected_files: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    validation_steps: List[str] = field(default_factory=list)

    assumptions: List[str] = field(default_factory=list)
    additional_information_needed: List[str] = field(default_factory=list)

    confidence: str = "medium"

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the change plan into a dictionary.
        """

        return {
            "change_request": self.change_request,
            "target": self.target,
            "summary": self.summary,
            "steps": [
                {
                    "order": step.order,
                    "file_path": step.file_path,
                    "symbol_name": step.symbol_name,
                    "change": step.change,
                    "reason": step.reason,
                    "dependencies": step.dependencies,
                    "risk": step.risk,
                }
                for step in self.steps
            ],
            "affected_files": self.affected_files,
            "dependencies": self.dependencies,
            "risks": self.risks,
            "validation_steps": self.validation_steps,
            "assumptions": self.assumptions,
            "additional_information_needed": (
                self.additional_information_needed
            ),
            "confidence": self.confidence,
        }

    def to_markdown(self) -> str:
        """
        Convert the structured change plan into readable Markdown.
        """

        lines = []

        # lines.append("## Change Plan")
        # lines.append("")

        lines.append("### Change Request")
        lines.append(self.change_request)
        lines.append("")

        if self.target:
            lines.append("### Target")
            lines.append(f"`{self._clean_markdown_value(self.target)}`")
            lines.append("")

        if self.summary:
            lines.append("### Summary")
            lines.append(self.summary)
            lines.append("")

        if self.steps:
            lines.append("### Proposed Changes")
            lines.append("")

            for step in self.steps:
                location = f"`{self._clean_markdown_value(step.file_path)}`"

                if step.symbol_name:
                    location += (
                        f" → `{self._clean_markdown_value(step.symbol_name)}`"
                    )

                lines.append(
                    f"{step.order}. **{location}**"
                )

                if step.change:
                    lines.append(f"   - Change: {step.change}")

                if step.reason:
                    lines.append(f"   - Reason: {step.reason}")

                if step.dependencies:
                    lines.append(
                        "   - Dependencies: "
                        + ", ".join(
                            f"`{dependency}`"
                            for dependency in step.dependencies
                        )
                    )

                if step.risk:
                    lines.append(
                        f"   - Risk: {step.risk}"
                    )

                lines.append("")

        if self.affected_files:
            lines.append("### Affected Files")
            for file_path in self.affected_files:
                lines.append(
                    f"- `{self._clean_markdown_value(file_path)}`"
                )
            lines.append("")

        if self.dependencies:
            lines.append("### Dependencies")
            for dependency in self.dependencies:
                lines.append(f"- {dependency}")
            lines.append("")

        if self.risks:
            lines.append("### Risks")
            for risk in self.risks:
                lines.append(f"- {risk}")
            lines.append("")

        if self.validation_steps:
            lines.append("### Validation Steps")
            for validation in self.validation_steps:
                lines.append(f"- {validation}")
            lines.append("")

        if self.assumptions:
            lines.append("### Assumptions")
            for assumption in self.assumptions:
                lines.append(f"- {assumption}")
            lines.append("")

        if self.additional_information_needed:
            lines.append("### Additional Information Needed")
            for information in self.additional_information_needed:
                lines.append(f"- {information}")
            lines.append("")

        # if self.confidence:
        #     lines.append("### Confidence")
        #     lines.append(self.confidence)

        return "\n".join(lines).strip()

    @staticmethod
    def _clean_markdown_value(value: str) -> str:
        """
        Remove surrounding Markdown backticks before adding formatting.
        """

        if not value:
            return ""

        value = value.strip()

        while (
            len(value) >= 2
            and value.startswith("`")
            and value.endswith("`")
        ):
            value = value[1:-1].strip()

        return value


class ChangePlanner:
    """
    Converts impact-analysis information into an actionable engineering
    change plan.

    The planner does NOT:
    - modify repository files
    - generate patches
    - execute commands
    - run tests
    - automatically apply changes

    It only produces a proposed plan.
    """

    def __init__(
        self,
        llm_generator: Optional[Callable[[str], str]] = None,
    ):
        self.llm_generator = llm_generator

    def plan(
        self,
        question: str,
        impact_analysis: Any,
        context: Any = None,
    ) -> ChangePlan:
        """
        Generate a structured change plan from impact-analysis results.

        Parameters
        ----------
        question:
            Original developer request.

        impact_analysis:
            Result produced by ImpactAnalyzer.

        context:
            Optional repository/code context.

        Returns
        -------
        ChangePlan
        """

        if not question or not str(question).strip():
            raise ValueError("Change request cannot be empty.")

        normalized_question = str(question).strip()

        impact_text = self._normalize_impact_analysis(
            impact_analysis
        )

        context_text = self._normalize_context(context)

        prompt = self._build_prompt(
            question=normalized_question,
            impact_analysis=impact_text,
            context=context_text,
        )

        if self.llm_generator is None:
            return self._build_fallback_plan(
                question=normalized_question,
                impact_analysis=impact_text,
            )

        response = self.llm_generator(prompt)

        if not response or not str(response).strip():
            return self._build_fallback_plan(
                question=normalized_question,
                impact_analysis=impact_text,
            )

        return self._parse_response(
            question=normalized_question,
            response=str(response).strip(),
            impact_analysis=impact_text,
        )

    def _build_prompt(
        self,
        question: str,
        impact_analysis: str,
        context: str,
    ) -> str:
        """
        Build a grounded change-planning prompt.
        """

        context_section = context.strip()

        if not context_section:
            context_section = "No additional repository context provided."

        return f"""
You are an AI software engineering change planner.

Your job is to create a SAFE, EVIDENCE-GROUNDED change plan for an
existing software repository.

You are NOT generating code.
You are NOT modifying files.
You are NOT producing a patch.

You are only determining:

1. What needs to change.
2. Which files/functions/components are involved.
3. In what order the changes should be made.
4. Why each change is required.
5. What dependencies may be affected.
6. What risks exist.
7. How the change should be validated.

IMPORTANT RULES:

- Use only evidence provided in the impact analysis and repository context.
- Do not invent files.
- Do not invent functions.
- Do not claim that a file must change unless repository evidence supports it.
- Distinguish direct changes from indirect or conditional changes.
- If evidence is insufficient, explicitly say so.
- Do not generate source code.
- Do not create patches.
- Do not assume a test exists if it was not found.
- Do not claim that tests pass.
- Do not claim that a change is safe merely because it appears simple.
- Preserve uncertainty when repository evidence is incomplete.

Original change request:

{question}

==================================================
IMPACT ANALYSIS
==================================================

{impact_analysis}

==================================================
REPOSITORY / CODE CONTEXT
==================================================

{context_section}

==================================================
OUTPUT FORMAT
==================================================

Return EXACTLY these sections:

### Target
The primary feature, endpoint, function, component, or module being changed.

### Summary
A short explanation of the requested change.

### Change Steps
Numbered implementation planning steps.

For every step use:

1. File: path/to/file
   Symbol: function_or_component
   Type: Direct / Indirect / Conditional
   Change: what should be changed
   Reason: why it needs to change
   Dependencies: relevant dependencies
   Risk: Low / Medium / High

### Affected Files
List the files that are directly or indirectly affected.

### Dependencies
List important functions, modules, API contracts, components,
data structures, or external dependencies involved.

### Risks
List realistic risks supported by repository evidence.

### Validation Steps
List concrete tests or checks that should be performed after
the change.

### Assumptions
List assumptions made because repository evidence is incomplete.

### Additional Information Needed
List information that would be useful before implementation.
If none is needed, write:

- None

### Confidence
High / Medium / Low

Do not generate code.
Do not generate a diff.
Do not modify the repository.
""".strip()

    def _parse_response(
        self,
        question: str,
        response: str,
        impact_analysis: str,
    ) -> ChangePlan:
        """
        Parse the LLM response into a ChangePlan.

        The parser is intentionally tolerant because different LLMs
        may format individual sections slightly differently.
        """

        sections = self._extract_sections(response)

        target = self._clean_section(
            sections.get("target", "")
        )

        summary = self._clean_section(
            sections.get("summary", "")
        )

        affected_files = self._parse_bullets(
            sections.get("affected files", "")
        )

        dependencies = self._parse_bullets(
            sections.get("dependencies", "")
        )

        risks = self._parse_bullets(
            sections.get("risks", "")
        )

        validation_steps = self._parse_bullets(
            sections.get("validation steps", "")
        )

        assumptions = self._parse_bullets(
            sections.get("assumptions", "")
        )

        additional_information = self._parse_bullets(
            sections.get("additional information needed", "")
        )

        confidence = self._clean_section(
            sections.get("confidence", "medium")
        )

        steps = self._parse_change_steps(
            sections.get("change steps", "")
        )

        if not steps:
            steps = self._build_steps_from_files(
                affected_files=affected_files,
                impact_analysis=impact_analysis,
            )

        return ChangePlan(
            change_request=question,
            target=target,
            summary=summary,
            steps=steps,
            affected_files=affected_files,
            dependencies=dependencies,
            risks=risks,
            validation_steps=validation_steps,
            assumptions=assumptions,
            additional_information_needed=additional_information,
            confidence=confidence or "medium",
        )

    def _extract_sections(
        self,
        text: str,
    ) -> Dict[str, str]:
        """
        Extract Markdown '### Section' blocks.
        """

        sections: Dict[str, str] = {}

        current_section: Optional[str] = None
        current_lines: List[str] = []

        for raw_line in text.splitlines():
            line = raw_line.strip()

            if line.startswith("### "):
                if current_section is not None:
                    sections[current_section] = "\n".join(
                        current_lines
                    ).strip()

                current_section = line[4:].strip().lower()
                current_lines = []
                continue

            if current_section is not None:
                current_lines.append(raw_line)

        if current_section is not None:
            sections[current_section] = "\n".join(
                current_lines
            ).strip()

        return sections

    def _parse_change_steps(
        self,
        text: str,
    ) -> List[ChangeStep]:
        """
        Parse numbered change steps.

        Expected form:

        1. File: backend/server.py
           Symbol: login
           Type: Direct
           Change: ...
           Reason: ...
           Dependencies: ...
           Risk: High
        """

        if not text.strip():
            return []

        steps: List[ChangeStep] = []

        blocks = self._split_numbered_blocks(text)

        for index, block in enumerate(blocks, start=1):
            file_path = self._extract_field(
                block,
                "File",
            )

            symbol_name = self._extract_field(
                block,
                "Symbol",
            )

            change_type = self._extract_field(
                block,
                "Type",
            )

            change = self._extract_field(
                block,
                "Change",
            )

            reason = self._extract_field(
                block,
                "Reason",
            )

            dependency_text = self._extract_field(
                block,
                "Dependencies",
            )

            risk = self._extract_field(
                block,
                "Risk",
            )

            dependencies = self._split_values(
                dependency_text
            )

            if not file_path:
                continue

            if change_type:
                change = (
                    f"[{change_type}] {change}"
                    if change
                    else f"[{change_type}]"
                )

            steps.append(
                ChangeStep(
                    order=index,
                    file_path=self._clean_value(file_path),
                    symbol_name=self._clean_value(
                        symbol_name
                    ),
                    change=self._clean_value(change),
                    reason=self._clean_value(reason),
                    dependencies=dependencies,
                    risk=self._normalize_risk(risk),
                )
            )

        return steps

    def _split_numbered_blocks(
        self,
        text: str,
    ) -> List[str]:
        """
        Split a section into numbered blocks.
        """

        blocks: List[str] = []
        current: List[str] = []

        for line in text.splitlines():
            stripped = line.strip()

            is_new_step = (
                len(stripped) > 2
                and stripped[0].isdigit()
                and ". " in stripped[:5]
            )

            if is_new_step:
                if current:
                    blocks.append("\n".join(current))

                current = [line]
            else:
                if current:
                    current.append(line)

        if current:
            blocks.append("\n".join(current))

        return blocks

    def _extract_field(
        self,
        block: str,
        field_name: str,
    ) -> str:
        """
        Extract a field such as:

        File: backend/server.py

        Also supports:

        1. File: backend/server.py
        """

        prefix = f"{field_name.lower()}:"

        for line in block.splitlines():
            stripped = line.strip()

            if stripped.lower().startswith(prefix):
                value = stripped[
                    len(prefix):
                ].strip()

                return self._clean_value(value)

            numbered_prefix = stripped

            if (
                numbered_prefix
                and numbered_prefix[0].isdigit()
                and ". " in numbered_prefix[:5]
            ):
                dot_index = numbered_prefix.find(". ")

                remainder = numbered_prefix[
                    dot_index + 2:
                ].strip()

                if remainder.lower().startswith(prefix):
                    value = remainder[
                        len(prefix):
                    ].strip()

                    return self._clean_value(value)

        return ""

    def _parse_bullets(
        self,
        text: str,
    ) -> List[str]:
        """
        Parse Markdown bullet lists.
        """

        if not text.strip():
            return []

        values: List[str] = []

        for line in text.splitlines():
            value = line.strip()

            if value.startswith("- "):
                value = value[2:].strip()

            elif value.startswith("* "):
                value = value[2:].strip()

            elif value.startswith("• "):
                value = value[2:].strip()

            else:
                continue

            value = self._clean_value(value)

            if value and value.lower() != "none":
                values.append(value)

        return self._unique(values)

    def _build_steps_from_files(
        self,
        affected_files: List[str],
        impact_analysis: str,
    ) -> List[ChangeStep]:
        """
        Conservative fallback when the LLM did not return structured
        change steps.
        """

        steps: List[ChangeStep] = []

        for index, file_path in enumerate(
            affected_files,
            start=1,
        ):
            steps.append(
                ChangeStep(
                    order=index,
                    file_path=file_path,
                    change=(
                        "Review the affected implementation and "
                        "update only the portions required by the "
                        "requested change."
                    ),
                    reason=(
                        "The file was identified as affected by "
                        "the impact analysis."
                    ),
                    risk="medium",
                )
            )

        return steps

    def _build_fallback_plan(
        self,
        question: str,
        impact_analysis: str,
    ) -> ChangePlan:
        """
        Produce a safe fallback when no LLM is configured.
        """

        affected_files = self._extract_file_paths(
            impact_analysis
        )

        steps = self._build_steps_from_files(
            affected_files=affected_files,
            impact_analysis=impact_analysis,
        )

        return ChangePlan(
            change_request=question,
            target=self._extract_target_from_impact(
                impact_analysis
            ),
            summary=(
                "A change plan could not be fully generated because "
                "no LLM generator was configured. The affected files "
                "identified by the impact analysis are preserved."
            ),
            steps=steps,
            affected_files=affected_files,
            assumptions=[
                "The impact analysis is the source of truth for "
                "affected files."
            ],
            additional_information_needed=[
                "A configured LLM generator is required for a detailed "
                "change plan."
            ],
            confidence="low",
        )

    def _extract_file_paths(
        self,
        text: str,
    ) -> List[str]:
        """
        Extract likely file paths from impact-analysis text.

        This is deliberately conservative.
        """

        files: List[str] = []

        for line in text.splitlines():
            stripped = line.strip()

            if not stripped:
                continue

            if stripped.startswith("-"):
                stripped = stripped[1:].strip()

            if "`" in stripped:
                parts = stripped.split("`")

                for index in range(
                    1,
                    len(parts),
                    2,
                ):
                    candidate = parts[index].strip()

                    if self._looks_like_file_path(
                        candidate
                    ):
                        files.append(candidate)

        return self._unique(files)

    def _extract_target_from_impact(
        self,
        text: str,
    ) -> str:
        """
        Try to extract a target from an impact-analysis result.
        """

        sections = self._extract_sections(text)

        target = sections.get("change target", "")

        if not target:
            target = sections.get("target", "")

        target = self._clean_section(target)

        if target.startswith("`") and target.endswith("`"):
            target = target[1:-1].strip()

        return target

    def _normalize_impact_analysis(
        self,
        impact_analysis: Any,
    ) -> str:
        """
        Normalize ImpactAnalyzer output.

        Supports:
        - strings
        - dictionaries
        - objects with to_markdown()
        - objects with to_dict()
        """

        if impact_analysis is None:
            return ""

        if isinstance(impact_analysis, str):
            return impact_analysis.strip()

        to_markdown = getattr(
            impact_analysis,
            "to_markdown",
            None,
        )

        if callable(to_markdown):
            try:
                result = to_markdown()

                if result:
                    return str(result).strip()
            except Exception:
                pass

        to_dict = getattr(
            impact_analysis,
            "to_dict",
            None,
        )

        if callable(to_dict):
            try:
                result = to_dict()

                if result:
                    return self._dict_to_text(result)
            except Exception:
                pass

        if isinstance(impact_analysis, dict):
            return self._dict_to_text(
                impact_analysis
            )

        return str(impact_analysis).strip()

    def _normalize_context(
        self,
        context: Any,
    ) -> str:
        """
        Normalize repository context.
        """

        if context is None:
            return ""

        if isinstance(context, str):
            return context.strip()

        if isinstance(context, list):
            parts = []

            for item in context:
                if isinstance(item, str):
                    parts.append(item)

                elif isinstance(item, dict):
                    parts.append(
                        self._dict_to_text(item)
                    )

                else:
                    parts.append(str(item))

            return "\n\n".join(
                part for part in parts if part
            ).strip()

        if isinstance(context, dict):
            return self._dict_to_text(context)

        return str(context).strip()

    def _dict_to_text(
        self,
        value: Dict[str, Any],
    ) -> str:
        """
        Convert nested dictionaries/lists into readable text.
        """

        lines: List[str] = []

        def walk(
            current: Any,
            prefix: str = "",
        ) -> None:
            if isinstance(current, dict):
                for key, item in current.items():
                    key_text = str(key)

                    if isinstance(
                        item,
                        (dict, list),
                    ):
                        lines.append(
                            f"{prefix}{key_text}:"
                        )
                        walk(
                            item,
                            prefix="  ",
                        )
                    else:
                        lines.append(
                            f"{prefix}{key_text}: "
                            f"{item}"
                        )

            elif isinstance(current, list):
                for item in current:
                    if isinstance(
                        item,
                        (dict, list),
                    ):
                        walk(
                            item,
                            prefix=prefix,
                        )
                    else:
                        lines.append(
                            f"{prefix}- {item}"
                        )

            else:
                lines.append(
                    f"{prefix}{current}"
                )

        walk(value)

        return "\n".join(lines).strip()

    def _clean_section(
        self,
        value: str,
    ) -> str:
        """
        Clean a section without destroying useful content.
        """

        if not value:
            return ""

        lines = [
            line.strip()
            for line in value.splitlines()
            if line.strip()
        ]

        return " ".join(lines).strip()

    def _clean_value(
        self,
        value: str,
    ) -> str:
        """
        Clean inline Markdown formatting.
        """

        if not value:
            return ""

        value = value.strip()

        while (
            len(value) >= 2
            and (
                (
                    value[0] == "`"
                    and value[-1] == "`"
                )
                or (
                    value[0] == "*"
                    and value[-1] == "*"
                )
            )
        ):
            value = value[1:-1].strip()

        return value

    def _split_values(
        self,
        value: str,
    ) -> List[str]:
        """
        Convert a comma/semicolon separated value into a list.
        """

        if not value:
            return []

        separators = [
            ",",
            ";",
        ]

        result = [value]

        for separator in separators:
            new_result: List[str] = []

            for item in result:
                new_result.extend(
                    item.split(separator)
                )

            result = new_result

        return self._unique(
            [
                self._clean_value(item)
                for item in result
                if self._clean_value(item)
            ]
        )

    def _normalize_risk(
        self,
        risk: str,
    ) -> str:
        """
        Normalize risk labels.
        """

        if not risk:
            return "medium"

        normalized = risk.lower().strip()

        if "high" in normalized:
            return "high"

        if "low" in normalized:
            return "low"

        return "medium"

    def _looks_like_file_path(self, value: str,) -> bool:
        """
        Determine whether a value resembles a repository file path.
        """

        if not value:
            return False

        value = value.strip()

        if value.startswith("http://"):
            return False

        if value.startswith("https://"):
            return False

        if value.startswith("__"):
            return False

        common_extensions = (
            ".py",
            ".js",
            ".jsx",
            ".ts",
            ".tsx",
            ".java",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".go",
            ".rs",
            ".rb",
            ".php",
            ".json",
            ".yaml",
            ".yml",
            ".md",
            ".css",
            ".html",
            ".env",
            ".toml",
        )

        if value.lower().endswith(common_extensions):
            return True

        return "/" in value or "\\" in value

    def _unique(self, values: List[str],) -> List[str]:
        """
        Preserve order while removing duplicates.
        """

        seen = set()
        result = []

        for value in values:
            normalized = value.strip()

            if not normalized:
                continue

            key = normalized.lower()

            if key in seen:
                continue

            seen.add(key)
            result.append(normalized)

        return result