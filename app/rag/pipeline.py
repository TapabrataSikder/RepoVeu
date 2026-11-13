import re
from pathlib import Path

from app.repository.repository_manager import (
    get_repository_path,
    list_repositories,
)

from app.retrieval.retriever import retrieve_code
from app.retrieval.context_builder import build_context
from app.retrieval.prompt_builder import build_prompt

from app.llm.client import generate_answer
from app.llm.answer_refiner import refine_answer

from app.analysis.intent_classifier import IntentClassifier
from app.analysis.engineering_router import EngineeringRouter
from app.analysis.code_explainer import CodeExplainer
from app.analysis.debugger import Debugger
from app.analysis.impact_analyzer import ImpactAnalyzer
from app.analysis.change_planner import ChangePlanner


# ==================================================
# INTENT / ENGINEERING COMPONENTS
# ==================================================

intent_classifier = IntentClassifier()
engineering_router = EngineeringRouter()


# ==================================================
# FILE EXISTENCE PATTERNS
# ==================================================

FILE_EXISTENCE_PATTERNS = [
    r"\bdoes\b.*\b(repos?itory|project)\b.*\b(have|contain|contains)\b",
    r"\bdoes\b.*\b(file|folder)\b.*\b(exist|exist in)\b",
    r"\bis\b.*\b(file|folder)\b.*\b(present|available)\b",
    r"\bdo\b.*\b(repos?itory|project)\b.*\b(have|contain|contains)\b",
    r"\bcan\b.*\b(find|locate)\b.*\b(file|folder)\b",
    r"\bdoes\b.*\b(repos?itory|project)\b.*\b(include|includes)\b",
    r"\bis\b.*\bthere\b.*\b(file|folder)\b",
]


# ==================================================
# BROAD OVERVIEW PATTERNS
# ==================================================

BROAD_OVERVIEW_PATTERNS = [
    r"\bwhat\s+does\s+(this|the)\s+(project|repo|repository|application|app|system)\s+do\b",
    r"\bwhat\s+is\s+(this|the)\s+(project|repo|repository|application|app|system)\b",
    r"\bwhat\s+is\s+(this|the)\s+(project|repo|repository|application|app|system)\s+about\b",
    r"\bwhat\s+is\s+the\s+(main|primary|overall)\s+(purpose|function)\s+of\s+(this|the)\s+(project|repo|repository|application|app|system)\b",
]


# ==================================================
# FILE CONTENT PATTERNS
# ==================================================

FILE_CONTENT_PATTERNS = [
    r"\bwhat\b.*\b(content|inside)\b.*\b(file|document)\b",
    r"\bwhat\b.*\b(content|inside)\b.*\bof\b",
    r"\bshow\b.*\b(content|contents)\b.*\b(file|document)\b",
    r"\bshow\b.*\b(file|document)\b",
    r"\bdisplay\b.*\b(file|document)\b",
    r"\bread\b.*\b(file|document)\b",
    r"\bwhat\b.*\bin\b.*\b(file|document)\b",
]


# ==================================================
# FILE CANDIDATE EXTRACTION
# ==================================================

def extract_file_candidate(question):
    """
    Extract a likely file or relative file path from a question.

    Supports:

        README.md
        server.py
        package.json

    And nested paths:

        backend/README.md
        src/main.py
    """

    if not question:
        return None

    matches = re.findall(
        r"(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.[A-Za-z0-9_-]+",
        question,
    )

    if matches:
        return matches[0].strip().rstrip(".,;:!?")

    return None


# ==================================================
# IMPACT TARGET EXTRACTION
# ==================================================

def extract_impact_target(question):
    """
    Extract a likely engineering change target from an
    impact-analysis question.

    Examples:

        /auth/login
        /api/orders
        src/auth/service.py
        AuthContext
        login()

    The function is intentionally conservative.

    It does not try to fully understand the repository.
    It only identifies useful target strings that can be
    passed into targeted retrieval.
    """

    if not question:
        return None

    # --------------------------------------------------
    # API / ROUTE TARGET
    # --------------------------------------------------

    route_matches = re.findall(
        r"(?<![\w])/"
        r"[A-Za-z0-9_.~-]+"
        r"(?:/[A-Za-z0-9_.~:{}$-]+)*"
        r"(?![\w])",
        question,
    )

    if route_matches:
        for route in route_matches:
            route = route.rstrip(".,;:!?")

            if route not in {
                "/",
                "/api",
                "/auth",
            }:
                return route

        return route_matches[0].rstrip(".,;:!?")

    # --------------------------------------------------
    # FILE TARGET
    # --------------------------------------------------

    file_candidate = extract_file_candidate(question)

    if file_candidate:
        return file_candidate

    # --------------------------------------------------
    # FUNCTION / METHOD TARGET
    # --------------------------------------------------

    function_matches = re.findall(
        r"\b[A-Za-z_][A-Za-z0-9_]*\s*\(\s*\)",
        question,
    )

    if function_matches:
        return function_matches[0].strip()

    # --------------------------------------------------
    # CLASS / COMPONENT TARGET
    # --------------------------------------------------

    component_matches = re.findall(
        r"\b[A-Z][A-Za-z0-9_]*(?:Context|Controller|Service|"
        r"Component|Router|Handler|Middleware|Manager)\b",
        question,
    )

    if component_matches:
        return component_matches[0]

    return None


# ==================================================
# IMPACT RETRIEVAL QUERY BUILDER
# ==================================================

def build_impact_retrieval_queries(
    question,
    target=None,
):
    """
    Build targeted retrieval queries for impact analysis.

    The goal is to retrieve different parts of the change
    surface rather than relying only on the original semantic
    question.

    Example target:

        /auth/login

    Produces queries for:

        - implementation
        - callers / usages
        - frontend integration
        - backend handling
        - related tests
    """

    if not question:
        return []

    target_text = target.strip() if target else question.strip()

    queries = [
        f"{target_text} implementation",
        f"{target_text} callers usages references",
        f"{target_text} frontend client integration",
        f"{target_text} backend route handler",
        f"{target_text} tests validation",
    ]

    # --------------------------------------------------
    # Add the original question as a targeted query when
    # a specific target was identified.
    # --------------------------------------------------

    if target:
        queries.insert(
            0,
            question.strip(),
        )

    # --------------------------------------------------
    # Remove duplicates while preserving order.
    # --------------------------------------------------

    unique_queries = []

    for query in queries:
        normalized = query.lower().strip()

        if not normalized:
            continue

        if normalized in {
            existing.lower().strip()
            for existing in unique_queries
        }:
            continue

        unique_queries.append(query)

    return unique_queries


# ==================================================
# IMPACT CONTEXT EXPANSION
# ==================================================

def build_impact_analysis_context(
    question,
    repository_id,
    initial_retrieval_results,
    top_k=5,
):
    """
    Build an expanded repository context specifically for
    impact analysis.

    The existing retrieval result is always preserved.

    Additional targeted retrieval searches for:

        - target implementation
        - callers / usages
        - frontend integration
        - backend handling
        - tests / validation

    This function does not modify ChromaDB or repository files.

    Returns:

        str | None
    """

    print()
    print("=" * 40)
    print("IMPACT ANALYSIS RETRIEVAL EXPANSION")
    print("=" * 40)

    target = extract_impact_target(question)

    print("Impact target :", target)

    queries = build_impact_retrieval_queries(
        question=question,
        target=target,
    )

    if not queries:
        print("No targeted retrieval queries generated.")

        return build_context(
            initial_retrieval_results
        )

    print()
    print("Targeted retrieval queries:")

    for index, query in enumerate(
        queries,
        start=1,
    ):
        print(
            f"{index}. {query}"
        )

    contexts = []

    # --------------------------------------------------
    # ORIGINAL RETRIEVAL CONTEXT
    # --------------------------------------------------

    try:
        initial_context = build_context(
            initial_retrieval_results
        )

        if initial_context:
            contexts.append(
                (
                    "ORIGINAL RETRIEVAL CONTEXT",
                    initial_context,
                )
            )

    except Exception as error:
        print(
            "Initial context construction failed:",
            error,
        )

    # --------------------------------------------------
    # TARGETED RETRIEVAL
    # --------------------------------------------------

    targeted_top_k = max(
        2,
        min(top_k, 5),
    )

    for index, query in enumerate(
        queries,
        start=1,
    ):

        print()
        print(
            f"[Impact Retrieval {index}/{len(queries)}]"
        )

        print(
            "Query:",
            query,
        )

        try:
            retrieval_results = retrieve_code(
                query=query,
                repository_id=repository_id,
                top_k=targeted_top_k,
            )

        except Exception as error:
            print(
                "Targeted retrieval failed:",
                error,
            )

            continue

        if not retrieval_results:
            print(
                "No results returned."
            )

            continue

        # --------------------------------------------------
        # Extract documents only for logging.
        # The complete retrieval result is passed to
        # build_context so existing metadata handling
        # remains unchanged.
        # --------------------------------------------------

        if isinstance(
            retrieval_results,
            dict,
        ):
            documents = retrieval_results.get(
                "documents",
                [[]],
            )

            if documents:
                documents = documents[0]

            else:
                documents = []

        else:
            documents = retrieval_results

        if not documents:
            print(
                "No documents returned."
            )

            continue

        print(
            f"Retrieved {len(documents)} "
            f"targeted chunks."
        )

        try:
            targeted_context = build_context(
                retrieval_results
            )

        except Exception as error:
            print(
                "Targeted context construction failed:",
                error,
            )

            continue

        if not targeted_context:
            print(
                "Targeted context was empty."
            )

            continue

        contexts.append(
            (
                f"TARGETED RETRIEVAL {index}: {query}",
                targeted_context,
            )
        )

    # --------------------------------------------------
    # COMBINE CONTEXTS
    # --------------------------------------------------

    if not contexts:
        print(
            "No expanded context was created."
        )

        return None

    print()
    print(
        f"Collected {len(contexts)} context sections."
    )

    # --------------------------------------------------
    # Deduplicate complete context blocks.
    #
    # We intentionally do not attempt to parse or alter
    # the internal format produced by build_context().
    # --------------------------------------------------

    unique_contexts = []
    seen_contexts = set()

    for label, context in contexts:

        normalized_context = context.strip()

        if not normalized_context:
            continue

        context_key = normalized_context

        if context_key in seen_contexts:
            continue

        seen_contexts.add(
            context_key
        )

        unique_contexts.append(
            (
                label,
                normalized_context,
            )
        )

    if not unique_contexts:
        return None

    # --------------------------------------------------
    # Build the final expanded context.
    # --------------------------------------------------

    context_sections = []

    for label, context in unique_contexts:

        context_sections.append(
            f"## {label}\n\n{context}"
        )

    expanded_context = "\n\n".join(
        context_sections
    )

    print()
    print(
        "Original context + targeted relationship "
        "contexts combined."
    )

    print(
        f"Expanded context length: "
        f"{len(expanded_context)} characters"
    )

    return expanded_context


# ==================================================
# FILE EXISTENCE QUERY
# ==================================================

def is_file_existence_query(question):
    """
    Determine whether the question is asking whether
    a file or folder exists in the repository.
    """

    if not question:
        return False

    normalized_question = question.lower().strip()

    for pattern in FILE_EXISTENCE_PATTERNS:
        if re.search(
            pattern,
            normalized_question,
        ):
            return True

    return False


# ==================================================
# FILE CONTENT QUERY
# ==================================================

def is_file_content_query(question):
    """
    Determine whether the question is asking for the
    content of a specific repository file.
    """

    if not question:
        return False

    normalized_question = question.lower().strip()

    for pattern in FILE_CONTENT_PATTERNS:
        if re.search(
            pattern,
            normalized_question,
        ):
            return True

    return False


# ==================================================
# FIND REPOSITORY FILE
# ==================================================

def find_repository_file(
    repository_id,
    file_candidate,
):
    """
    Search for a file inside the downloaded repository.

    The exact relative path is checked first.

    If it is not found, the repository is searched recursively
    by filename.
    """

    repository_path = get_repository_path(
        repository_id
    )

    if not repository_path:
        return []

    repository_path = Path(
        repository_path
    )

    if not repository_path.exists():
        return []

    file_candidate = (
        file_candidate
        .replace("\\", "/")
        .strip("/")
    )

    candidate_path = Path(
        file_candidate
    )

    exact_path = (
        repository_path /
        candidate_path
    )

    try:
        exact_path = exact_path.resolve()
        repository_root = repository_path.resolve()

        if (
            exact_path.is_file()
            and repository_root in exact_path.parents
        ):
            relative_path = (
                exact_path
                .relative_to(repository_root)
            )

            return [
                relative_path.as_posix()
            ]

    except (
        OSError,
        ValueError,
    ):
        pass

    filename = candidate_path.name
    results = []

    try:
        for path in repository_path.rglob(
            filename
        ):
            try:
                resolved_path = path.resolve()

                if not path.is_file():
                    continue

                if ".git" in resolved_path.parts:
                    continue

                if (
                    repository_path.resolve()
                    not in resolved_path.parents
                ):
                    continue

                relative_path = (
                    resolved_path
                    .relative_to(
                        repository_path.resolve()
                    )
                )

                results.append(
                    relative_path.as_posix()
                )

            except (
                OSError,
                ValueError,
            ):
                continue

    except OSError:
        return []

    return sorted(
        results
    )


# ==================================================
# READ REPOSITORY FILE
# ==================================================

def read_repository_file(
    repository_id,
    relative_file_path,
):
    """
    Read a repository file locally and safely.

    Returns:

        tuple[str, str] | None

        (relative_path, content)
    """

    repository_path = get_repository_path(
        repository_id
    )

    if not repository_path:
        return None

    repository_path = Path(
        repository_path
    ).resolve()

    relative_file_path = (
        relative_file_path
        .replace("\\", "/")
        .strip("/")
    )

    file_path = (
        repository_path /
        relative_file_path
    )

    try:
        resolved_file_path = (
            file_path.resolve()
        )

        if (
            repository_path
            not in resolved_file_path.parents
        ):
            return None

        if not resolved_file_path.is_file():
            return None

        content = resolved_file_path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        relative_path = (
            resolved_file_path
            .relative_to(repository_path)
            .as_posix()
        )

        return (
            relative_path,
            content,
        )

    except (
        OSError,
        UnicodeError,
        ValueError,
    ):
        return None


# ==================================================
# DIRECT FILE EXISTENCE ANSWER
# ==================================================

def answer_file_existence_query(
    question,
    repository_id,
):
    """
    Answer repository file-existence questions directly
    from the local repository filesystem.

    Returns:

        str | None
    """

    if not is_file_existence_query(
        question
    ):
        return None

    file_candidate = extract_file_candidate(
        question
    )

    if not file_candidate:
        return None

    print()
    print("=" * 40)
    print("DETERMINISTIC FILE QUERY")
    print("=" * 40)

    print(
        "Repository :",
        repository_id,
    )

    print(
        "File       :",
        file_candidate,
    )

    matches = find_repository_file(
        repository_id,
        file_candidate,
    )

    if matches:
        print(
            "File found :",
            len(matches),
        )

        if len(matches) == 1:
            return (
                f"Yes. The repository contains "
                f"`{matches[0]}`."
            )

        formatted_matches = "\n".join(
            f"- `{match}`"
            for match in matches
        )

        return (
            f"Yes. The repository contains "
            f"{len(matches)} matching files:\n\n"
            f"{formatted_matches}"
        )

    print(
        "File found : 0"
    )

    return (
        f"No. I could not find "
        f"`{file_candidate}` "
        f"in the repository."
    )


# ==================================================
# DIRECT FILE CONTENT ANSWER
# ==================================================

def answer_file_content_query(
    question,
    repository_id,
):
    """
    Answer questions asking for the contents of a specific
    repository file directly from the local filesystem.
    """

    if not is_file_content_query(
        question
    ):
        return None

    file_candidate = extract_file_candidate(
        question
    )

    if not file_candidate:
        return None

    print()
    print("=" * 40)
    print("DETERMINISTIC FILE CONTENT QUERY")
    print("=" * 40)

    print(
        "Repository :",
        repository_id,
    )

    print(
        "File       :",
        file_candidate,
    )

    matches = find_repository_file(
        repository_id,
        file_candidate,
    )

    if not matches:
        print(
            "File found : 0"
        )

        return (
            f"I could not find "
            f"`{file_candidate}` "
            f"in the repository."
        )

    print(
        "File found :",
        len(matches),
    )

    if len(matches) > 1:
        formatted_matches = "\n".join(
            f"- `{match}`"
            for match in matches
        )

        return (
            f"I found multiple files named "
            f"`{file_candidate}`:\n\n"
            f"{formatted_matches}\n\n"
            f"Please specify the relative path."
        )

    relative_path = matches[0]

    file_result = read_repository_file(
        repository_id,
        relative_path,
    )

    if not file_result:
        return (
            f"I found `{relative_path}`, "
            f"but I could not read its contents."
        )

    relative_path, content = file_result

    print(
        "File loaded successfully."
    )

    if not content.strip():
        return (
            f"`{relative_path}` exists, "
            f"but the file is empty."
        )

    return (
        f"### `{relative_path}`\n\n"
        f"```text\n"
        f"{content}\n"
        f"```"
    )


# ==================================================
# ENGINEERING WORKFLOW HELPERS
# ==================================================

def classify_engineering_question(
    question,
):
    """
    Classify the question and determine the engineering workflow.
    """

    print()
    print("=" * 40)
    print("ENGINEERING INTENT ANALYSIS")
    print("=" * 40)

    intent = intent_classifier.classify(
        question
    )

    print(
        "Intent      :",
        intent.intent,
    )

    print(
        "Confidence  :",
        intent.confidence,
    )

    print(
        "Repo context:",
        intent.requires_repository_context,
    )

    print(
        "Code gen    :",
        intent.requires_code_generation,
    )

    print(
        "Validation  :",
        intent.requires_validation,
    )

    print(
        "Target      :",
        intent.target,
    )

    print(
        "Reason      :",
        intent.reason,
    )

    route = engineering_router.route(
        question
    )

    print()
    print(
        "Engineering route:",
        route.workflow,
    )

    return intent, route


# ==================================================
# CODE EXPLANATION WORKFLOW
# ==================================================

def run_code_explanation_workflow(
    question,
    context,
):
    """
    Run the dedicated code explanation workflow.
    """

    print()
    print("=" * 40)
    print("CODE EXPLANATION WORKFLOW")
    print("=" * 40)

    explainer = CodeExplainer(
        llm_generator=generate_answer
    )

    answer = explainer.explain(
        question=question,
        context=context,
    )

    if not answer:
        return None

    return answer


# ==================================================
# DEBUGGING WORKFLOW
# ==================================================

def run_debugging_workflow(
    question,
    context,
):
    """
    Run the dedicated debugging workflow.
    """

    print()
    print("=" * 40)
    print("DEBUGGING WORKFLOW")
    print("=" * 40)

    debugger = Debugger(
        llm_generator=generate_answer
    )

    result = debugger.debug(
        question=question,
        context=context,
    )

    if not result:
        return None

    if hasattr(
        result,
        "to_markdown",
    ):
        return result.to_markdown()

    if isinstance(
        result,
        str,
    ):
        return result

    if hasattr(
        result,
        "__dict__",
    ):
        data = result.__dict__

        sections = []

        section_order = [
            "problem",
            "root_cause",
            "evidence",
            "fix_plan",
            "risks",
            "validation_steps",
            "confidence",
            "additional_information_needed",
        ]

        titles = {
            "problem": "Problem",
            "root_cause": "Root Cause",
            "evidence": "Evidence",
            "fix_plan": "Fix Plan",
            "risks": "Risks",
            "validation_steps": "Validation Steps",
            "confidence": "Confidence",
            "additional_information_needed": (
                "Additional Information Needed"
            ),
        }

        for field in section_order:
            value = data.get(
                field
            )

            if value is None:
                continue

            if isinstance(
                value,
                list,
            ):
                value = "\n".join(
                    f"- {item}"
                    for item in value
                )

            value = str(
                value
            ).strip()

            if not value:
                continue

            sections.append(
                f"### {titles[field]}\n\n{value}"
            )

        if sections:
            return "\n\n".join(
                sections
            )

    return str(
        result
    )


# ==================================================
# IMPACT ANALYSIS WORKFLOW
# ==================================================

def run_impact_analysis_workflow(
    question,
    context,
):
    """
    Run the dedicated change-impact analysis workflow.

    This workflow determines:

        - change target
        - directly affected files
        - indirectly affected files
        - change flow
        - risks
        - validation steps

    It does not modify repository files.
    """

    print()
    print("=" * 40)
    print("IMPACT ANALYSIS WORKFLOW")
    print("=" * 40)

    analyzer = ImpactAnalyzer(
        llm_generator=generate_answer
    )

    result = analyzer.analyze(
        question=question,
        context=context,
    )

    if not result:
        return None

    # --------------------------------------------------
    # If analyzer already provides markdown
    # --------------------------------------------------

    if hasattr(
        result,
        "to_markdown",
    ):
        return result.to_markdown()

    # --------------------------------------------------
    # If analyzer returns a string
    # --------------------------------------------------

    if isinstance(
        result,
        str,
    ):
        return result

    # --------------------------------------------------
    # Convert structured result to markdown
    # --------------------------------------------------

    if hasattr(
        result,
        "__dict__",
    ):
        data = result.__dict__

        sections = []

        section_order = [
            "change_target",
            "directly_affected_files",
            "indirectly_affected_files",
            "change_flow",
            "risks",
            "validation_steps",
        ]

        titles = {
            "change_target": "Change Target",
            "directly_affected_files": (
                "Directly Affected Files"
            ),
            "indirectly_affected_files": (
                "Indirectly Affected Files"
            ),
            "change_flow": "Change Flow",
            "risks": "Risks",
            "validation_steps": (
                "Validation Steps"
            ),
        }

        for field in section_order:
            value = data.get(
                field
            )

            if value is None:
                continue

            if isinstance(
                value,
                list,
            ):
                value = "\n".join(
                    f"- {item}"
                    for item in value
                )

            value = str(
                value
            ).strip()

            if not value:
                continue

            sections.append(
                f"### {titles[field]}\n\n{value}"
            )

        if sections:
            return "\n\n".join(
                sections
            )

    return str(
        result
    )


# ==================================================
# CHANGE PLANNING WORKFLOW
# ==================================================

def run_change_planning_workflow(question, impact_analysis, context, ):
    """
    Run the dedicated change-planning workflow.

    ChangePlanner receives:

        - original change request
        - ImpactAnalyzer result
        - grounded repository context

    The planner does not modify repository files.

    Returns:

        str | None
    """

    print()
    print("=" * 40)
    print("CHANGE PLANNING WORKFLOW")
    print("=" * 40)

    planner = ChangePlanner(llm_generator=generate_answer)

    result = planner.plan(
        question=question,
        impact_analysis=impact_analysis,
        context=context,
    )

    if not result:
        return None

    # --------------------------------------------------
    # If planner already provides markdown
    # --------------------------------------------------

    if hasattr(result, "to_markdown", ):
        return result.to_markdown()

    # --------------------------------------------------
    # If planner returns a string
    # --------------------------------------------------

    if isinstance(result, str, ):
        return result

    # --------------------------------------------------
    # Convert structured result to readable text
    # --------------------------------------------------

    if hasattr(result, "__dict__", ):
        data = result.__dict__

        sections = []

        section_order = [
            "change_request",
            "target",
            "summary",
            "proposed_changes",
            "affected_files",
            "dependencies",
            "risks",
            "validation_steps",
            "assumptions",
            "confidence",
        ]

        titles = {
            "change_request": "Change Request",
            "target": "Target",
            "summary": "Summary",
            "proposed_changes": "Proposed Changes",
            "affected_files": "Affected Files",
            "dependencies": "Dependencies",
            "risks": "Risks",
            "validation_steps": "Validation Steps",
            "assumptions": "Assumptions",
            "confidence": "Confidence",
        }

        for field in section_order:
            value = data.get(field)

            if value is None:
                continue

            if isinstance(value, list, ):
                value = "\n".join(
                    f"- {item}"
                    for item in value
                )

            value = str(value).strip()

            if not value:
                continue

            sections.append(f"### {titles[field]}\n\n{value}")

        if sections:
            return "\n\n".join(sections)

    return str(result)


# ==================================================
# NORMAL EXISTING RAG WORKFLOW
# ==================================================

def run_existing_rag_workflow(
    question,
    retrieval_results,
):
    """
    Run the original RAG answer-generation workflow.

    This function intentionally preserves:

        context builder
        ↓
        prompt builder
        ↓
        Gemini / Hugging Face
        ↓
        OpenAI final refinement
    """

    if not retrieval_results:
        return (
            "I could not find relevant information "
            "in the repository."
        )

    if isinstance(
        retrieval_results,
        dict,
    ):
        documents = retrieval_results.get(
            "documents",
            [[]],
        )[0]

    else:
        documents = retrieval_results

    if not documents:
        print()
        print("=" * 40)
        print("NO RELEVANT REPOSITORY CONTEXT")
        print("=" * 40)

        return (
            "I could not find relevant information "
            "in the repository to answer this question."
        )

    print()
    print(
        f"Retrieved {len(documents)} relevant chunks."
    )

    print()
    print(
        "[2] Building repository context..."
    )

    context = build_context(
        retrieval_results
    )

    if not context:
        return (
            "The available repository context "
            "is insufficient to answer this question."
        )

    print(
        "Repository context created."
    )

    print()
    print(
        "[3] Building RAG prompt..."
    )

    prompt = build_prompt(
        question=question,
        context=context,
    )

    print(
        "RAG prompt created."
    )

    print()
    print(
        "[4] Generating draft answer "
        "with configured LLM..."
    )

    draft_answer = generate_answer(
        prompt
    )

    if not draft_answer:
        return (
            "I was unable to generate an answer "
            "from the repository context."
        )

    print()
    print("=" * 30)
    print("DRAFT ANSWER")
    print("=" * 30)

    print()
    print(
        "[5] Refining final answer..."
    )

    final_answer = refine_answer(
        question=question,
        draft_answer=draft_answer,
    )

    if not final_answer:
        print(
            "Final refinement returned no answer. "
            "Using the original draft."
        )

        final_answer = draft_answer

    print()
    print("=" * 40)
    print("FINAL ANSWER READY")
    print("=" * 40)

    print(
        f"Answer length: "
        f"{len(final_answer)} characters"
    )

    return final_answer


# ==================================================
# MAIN REPOSITORY QUESTION PIPELINE
# ==================================================

def ask_repository(
    question,
    repository_id,
    top_k=5,
):
    """
    Ask a question about a repository.

    Dedicated engineering workflows:

        EXPLAIN
            → CodeExplainer

        DEBUG
            → Debugger

        IMPACT_ANALYSIS
            → ImpactAnalyzer
            → ChangePlanner

    Other intents continue to use the original
    RAG pipeline.

    No workflow automatically modifies repository
    files.
    """

    print()
    print("=" * 40)
    print("REPOSITORY RAG PIPELINE")
    print("=" * 40)

    print(
        "Repository :",
        repository_id,
    )

    print(
        "Question   :",
        question,
    )

    print(
        "Top K      :",
        top_k,
    )

    # ==================================================
    # 1. DIRECT FILE EXISTENCE CHECK
    # ==================================================

    direct_answer = answer_file_existence_query(
        question,
        repository_id,
    )

    if direct_answer is not None:
        print()
        print("=" * 40)
        print("DIRECT LOCAL ANSWER")
        print("=" * 40)

        print(
            direct_answer
        )

        return direct_answer

    # ==================================================
    # 2. DIRECT FILE CONTENT CHECK
    # ==================================================

    direct_content_answer = answer_file_content_query(
        question,
        repository_id,
    )

    if direct_content_answer is not None:
        print()
        print("=" * 40)
        print("DIRECT LOCAL FILE CONTENT ANSWER")
        print("=" * 40)

        print(
            f"Answer length: "
            f"{len(direct_content_answer)} characters"
        )

        return direct_content_answer

    # ==================================================
    # 3. CLASSIFY ENGINEERING INTENT
    # ==================================================

    try:
        intent, route = classify_engineering_question(
            question
        )

    except Exception as error:
        print()
        print(
            "Intent classification failed:",
            error,
        )

        print(
            "Falling back to the original RAG pipeline."
        )

        intent = None
        route = None

    # ==================================================
    # 4. LOCAL RETRIEVAL
    # ==================================================

    print()
    print(
        "[1] Retrieving repository context locally..."
    )

    retrieval_results = retrieve_code(
        query=question,
        repository_id=repository_id,
        top_k=top_k,
    )

    if not retrieval_results:
        return (
            "I could not find relevant information "
            "in the repository."
        )

    if isinstance(
        retrieval_results,
        dict,
    ):
        documents = retrieval_results.get(
            "documents",
            [[]],
        )[0]

    else:
        documents = retrieval_results

    if not documents:
        print()
        print("=" * 40)
        print("NO RELEVANT REPOSITORY CONTEXT")
        print("=" * 40)

        return (
            "I could not find relevant information "
            "in the repository to answer this question."
        )

    print()
    print(
        f"Retrieved {len(documents)} relevant chunks."
    )

    # ==================================================
    # 5. BUILD SHARED CONTEXT
    # ==================================================

    print()
    print(
        "[2] Building repository context..."
    )

    context = build_context(
        retrieval_results
    )

    if not context:
        return (
            "The available repository context "
            "is insufficient to answer this question."
        )

    print(
        "Repository context created."
    )

    # ==================================================
    # 6. ENGINEERING WORKFLOW ROUTING
    # ==================================================

    if route is not None:

        workflow = getattr(
            route,
            "workflow",
            None,
        )

        print()
        print("=" * 40)
        print("ENGINEERING WORKFLOW ROUTING")
        print("=" * 40)

        print(
            "Intent   :",
            intent.intent,
        )

        print(
            "Workflow :",
            workflow,
        )

        # --------------------------------------------------
        # CODE EXPLANATION
        # --------------------------------------------------

        if workflow == "code_explanation":

            try:
                answer = run_code_explanation_workflow(
                    question=question,
                    context=context,
                )

                if answer:
                    return answer

                print(
                    "Code explanation returned no answer."
                )

            except Exception as error:
                print(
                    "Code explanation failed:",
                    error,
                )

                print(
                    "Falling back to original RAG."
                )

        # --------------------------------------------------
        # DEBUGGING
        # --------------------------------------------------

        elif workflow == "debugging":

            try:
                answer = run_debugging_workflow(
                    question=question,
                    context=context,
                )

                if answer:
                    return answer

                print(
                    "Debugger returned no answer."
                )

            except Exception as error:
                print(
                    "Debugging workflow failed:",
                    error,
                )

                print(
                    "Falling back to original RAG."
                )

        # --------------------------------------------------
        # IMPACT ANALYSIS + CHANGE PLANNING
        # --------------------------------------------------

        elif workflow == "impact_analysis":

            try:
                # --------------------------------------------------
                # Expand retrieval specifically for impact analysis.
                #
                # Normal RAG remains untouched.
                # --------------------------------------------------

                impact_context = (
                    build_impact_analysis_context(
                        question=question,
                        repository_id=repository_id,
                        initial_retrieval_results=(
                            retrieval_results
                        ),
                        top_k=top_k,
                    )
                )

                if not impact_context:
                    print(
                        "Impact retrieval expansion returned "
                        "no additional context."
                    )

                    impact_context = context

                print()
                print(
                    "Running ImpactAnalyzer with "
                    "expanded repository context..."
                )

                impact_answer = (
                    run_impact_analysis_workflow(
                        question=question,
                        context=impact_context,
                    )
                )

                if impact_answer:

                    print()
                    print(
                        "Impact analysis completed."
                    )

                    # --------------------------------------------------
                    # Run ChangePlanner using the ImpactAnalyzer
                    # result as its engineering input.
                    # --------------------------------------------------

                    print()
                    print(
                        "Running ChangePlanner using "
                        "impact analysis..."
                    )

                    change_plan = (
                        run_change_planning_workflow(
                            question=question,
                            impact_analysis=impact_answer,
                            context=impact_context,
                        )
                    )

                    if change_plan:

                        print()
                        print(
                            "Change planning completed."
                        )

                        return (
                            "## Impact Analysis\n\n"
                            f"{impact_answer}\n\n"
                            "---\n\n"
                            "## Change Plan\n\n"
                            f"{change_plan}"
                        )

                    print(
                        "ChangePlanner returned no plan."
                    )

                    # --------------------------------------------------
                    # Preserve ImpactAnalyzer result if planning
                    # fails.
                    # --------------------------------------------------

                    return impact_answer

                print(
                    "Impact analyzer returned no answer."
                )

            except Exception as error:
                print(
                    "Impact analysis failed:",
                    error,
                )

                print(
                    "Falling back to original RAG."
                )

        # --------------------------------------------------
        # OTHER WORKFLOWS
        # --------------------------------------------------

        else:
            print(
                "Dedicated workflow not implemented yet:"
            )

            print(
                workflow
            )

            print(
                "Using existing RAG pipeline."
            )

    # ==================================================
    # 7. ORIGINAL RAG WORKFLOW
    # ==================================================

    print()
    print(
        "Using original RAG answer-generation pipeline..."
    )

    print()
    print(
        "[3] Building RAG prompt..."
    )

    prompt = build_prompt(
        question=question,
        context=context,
    )

    print(
        "RAG prompt created."
    )

    # ==================================================
    # 8. GEMINI → HUGGING FACE FALLBACK
    # ==================================================

    print()
    print(
        "[4] Generating draft answer "
        "with configured LLM..."
    )

    draft_answer = generate_answer(
        prompt
    )

    if not draft_answer:
        return (
            "I was unable to generate an answer "
            "from the repository context."
        )

    print()
    print("=" * 30)
    print("DRAFT ANSWER")
    print("=" * 30)

    print()
    print(
        "[5] Refining final answer..."
    )

    final_answer = refine_answer(
        question=question,
        draft_answer=draft_answer,
    )

    if not final_answer:
        print(
            "Final refinement returned no answer. "
            "Using the original draft."
        )

        final_answer = draft_answer

    print()
    print("=" * 40)
    print("FINAL ANSWER READY")
    print("=" * 40)

    print(
        f"Answer length: "
        f"{len(final_answer)} characters"
    )

    return final_answer


# ==================================================
# REPOSITORY SELECTION
# ==================================================

def select_repository():
    """
    Display available repositories and allow the user
    to select one.
    """

    repositories = list_repositories()

    if not repositories:
        print()
        print(
            "No repositories are available."
        )

        return None

    print(
        "=" * 50
    )

    print(
        "AVAILABLE REPOSITORIES"
    )

    print(
        "=" * 50
    )

    for index, repository in enumerate(
        repositories,
        start=1,
    ):
        if isinstance(
            repository,
            dict,
        ):
            repository_id = repository.get(
                "repository_id"
            )

        else:
            repository_id = repository

        print(
            f"{index}. {repository_id}"
        )

    print()

    while True:
        try:
            choice = int(
                input(
                    "Select repository number: "
                )
            )

            if (
                1 <= choice <= len(repositories)
            ):

                selected = repositories[
                    choice - 1
                ]

                if isinstance(
                    selected,
                    dict,
                ):
                    return selected.get(
                        "repository_id"
                    )

                return selected

            print(
                f"Please enter a number between "
                f"1 and {len(repositories)}."
            )

        except ValueError:
            print(
                "Please enter a valid repository number."
            )


# ==================================================
# COMMAND-LINE TEST
# ==================================================

def main():

    repository_id = select_repository()

    if not repository_id:
        return

    print()
    print(
        "=" * 50
    )

    print(
        "GITHUB REPOSITORY RAG"
    )

    print(
        "=" * 50
    )

    print(
        f"Repository: {repository_id}"
    )

    question = input(
        "\nAsk a question about the repository: "
    ).strip()

    if not question:
        print(
            "Question cannot be empty."
        )

        return

    print()
    print(
        "Searching repository locally..."
    )

    answer = ask_repository(
        question=question,
        repository_id=repository_id,
    )

    print()
    print(
        "=" * 50
    )

    print(
        "ANSWER"
    )

    print(
        "=" * 50
    )

    print()
    print(
        answer
    )


# ==================================================
# ENTRY POINT
# ==================================================

if __name__ == "__main__":
    main()