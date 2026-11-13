import json
import re
from pathlib import Path

from app.embeddings.embedder import generate_embedding
from app.vectorstore.chroma_store import search_chunks
from app.repository.repository_manager import (
    list_repositories,
    get_repository_path,
)


DEFAULT_TOP_K = 5
CANDIDATE_TOP_K = 25
OVERVIEW_TOP_K = 5
MAX_OVERVIEW_FILE_SIZE = 200000


# ==================================================
# QUERY TYPE DETECTION
# ==================================================

DOCUMENTATION_TERMS = {
    "readme",
    "documentation",
    "document",
    "docs",
    "description",
    "purpose",
    "repo",
    "repository",
    "overview",
    "installation",
    "setup",
    "usage",
    "contribution",
    "contributing",
    "license",
    "dependencies",
    "requirements",
    "about",
}


CODE_TERMS = {
    "code",
    "function",
    "method",
    "class",
    "variable",
    "implementation",
    "logic",
    "algorithm",
    "module",
    "import",
    "return",
    "parameter",
    "argument",
    "api",
    "endpoint",
    "route",
    "handler",
    "main",
}


MAIN_TERMS = {
    "main",
    "entry",
    "entrypoint",
    "startup",
    "application",
    "run",
}


OVERVIEW_TERMS = {
    "purpose",
    "purposeful",
    "about",
    "overview",
    "describe",
    "description",
    "what",
    "does",
    "project",
    "repository",
    "repo",
    "application",
    "app",
    "system",
    "built",
    "build",
    "developed",
    "develop",
}


# ==================================================
# RELATIONSHIP / ENGINEERING QUERY TERMS
# ==================================================

IMPLEMENTATION_TERMS = {
    "implementation",
    "implement",
    "handler",
    "route",
    "controller",
    "service",
    "logic",
    "defined",
    "definition",
}


CALLER_TERMS = {
    "caller",
    "callers",
    "caller",
    "calls",
    "calling",
    "usage",
    "usages",
    "used",
    "uses",
    "references",
    "reference",
    "dependent",
    "dependents",
}


FRONTEND_TERMS = {
    "frontend",
    "front",
    "client",
    "ui",
    "component",
    "components",
    "browser",
    "axios",
    "fetch",
    "request",
}


BACKEND_TERMS = {
    "backend",
    "server",
    "route",
    "endpoint",
    "handler",
    "controller",
    "api",
}


TEST_TERMS = {
    "test",
    "tests",
    "testing",
    "validation",
    "validate",
    "unit",
    "integration",
    "spec",
    "specs",
}


# ==================================================
# FILE TYPE PRIORITIES
# ==================================================

DOCUMENTATION_EXTENSIONS = {
    ".md",
    ".markdown",
    ".rst",
    ".txt",
}


CODE_EXTENSIONS = {
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
    ".cs",
    ".go",
    ".rs",
    ".php",
    ".rb",
    ".swift",
    ".kt",
    ".kts",
    ".scala",
}


TEST_FILE_TERMS = {
    "test",
    "tests",
    "spec",
    "__tests__",
}


FRONTEND_PATH_TERMS = {
    "frontend",
    "client",
    "web",
    "ui",
    "components",
    "pages",
    "views",
    "src",
}


BACKEND_PATH_TERMS = {
    "backend",
    "server",
    "api",
    "routes",
    "controllers",
    "services",
}


OVERVIEW_FILES = {
    "readme.md",
    "readme.markdown",
    "readme.rst",
    "readme.txt",
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "cargo.toml",
    "pom.xml",
    "build.gradle",
    "composer.json",
    "go.mod",
    "gemfile",
    "design_guidelines.json",
}


# ==================================================
# GENERATED / VENDOR FILES
# ==================================================

GENERATED_PATH_TERMS = {
    "node_modules",
    "vendor",
    "dist",
    "build",
    "coverage",
    "generated",
    "generated_files",
    "test-output",
    "test_output",
    "minified",
    "bundle",
}


MINIFIED_FILE_NAMES = {
    ".min.js",
    ".min.css",
}


# ==================================================
# TEXT NORMALIZATION
# ==================================================

def normalize_text(value):
    if not value:
        return ""

    value = str(value).lower()
    value = value.replace("\\", "/")
    value = re.sub(r"[^a-z0-9_./:-]+", " ", value,)
    value = re.sub(r"\s+", " ", value,)

    return value.strip()


def tokenize(value):
    normalized = normalize_text(value)

    if not normalized:
        return []

    tokens = re.findall(r"[a-zA-Z0-9_]+", normalized,)

    return [
        token.lower()
        for token in tokens
        if len(token) > 1
    ]


# ==================================================
# TARGET EXTRACTION
# ==================================================

def extract_route_targets(query):
    """
    Extract API-style route targets from a query.

    Examples:

        /auth/login
        /api/orders
        /users/:id
        /products/{id}

    Returns:
        list[str]
    """

    if not query:
        return []

    matches = re.findall(
        r"(?<![\w])/"
        r"[A-Za-z0-9_.~-]+"
        r"(?:/[A-Za-z0-9_.~:{}$-]+)*"
        r"(?![\w])",
        str(query),
    )

    routes = []

    for route in matches:
        route = route.rstrip(".,;:!?)]}")

        if route in {
            "/",
            "/api",
            "/auth",
        }:
            continue

        normalized_route = route.lower()

        if normalized_route not in routes:
            routes.append(normalized_route)

    return routes


def extract_function_targets(query):
    """
    Extract explicit function/method targets.

    Examples:

        login()
        validate_github_url()
        authenticate()

    Returns:
        list[str]
    """

    if not query:
        return []

    matches = re.findall(
        r"\b([A-Za-z_][A-Za-z0-9_]*)"
        r"\s*\(\s*\)",
        str(query),
    )

    targets = []

    for match in matches:
        normalized = match.lower()

        if normalized not in targets:
            targets.append(normalized)

    return targets


def extract_filename_targets(query):
    """
    Extract explicit filenames or relative paths.

    Examples:

        server.py
        frontend/src/App.js
        package.json

    Returns:
        list[str]
    """

    if not query:
        return []

    matches = re.findall(
        r"(?:[A-Za-z0-9_.-]+/)*"
        r"[A-Za-z0-9_.-]+\."
        r"[A-Za-z0-9_-]+",
        str(query),
    )

    targets = []

    for match in matches:
        normalized = (
            match
            .replace("\\", "/")
            .strip("/")
            .lower()
        )

        if normalized not in targets:
            targets.append(normalized)

    return targets


def extract_component_targets(query):
    """
    Extract likely class/component/context targets.

    Examples:

        AuthContext
        AuthProvider
        OrderController
        UserService

    Returns:
        list[str]
    """

    if not query:
        return []

    matches = re.findall(
        r"\b[A-Z][A-Za-z0-9_]*"
        r"(?:Context|Controller|Service|"
        r"Component|Router|Handler|Middleware|Manager)\b",
        str(query),
    )

    targets = []

    for match in matches:
        normalized = match.lower()

        if normalized not in targets:
            targets.append(normalized)

    return targets


# ==================================================
# QUERY ANALYSIS
# ==================================================

def analyze_query(query):
    normalized_query = normalize_text(query)

    tokens = set(tokenize(normalized_query))

    documentation_query = bool(tokens.intersection(DOCUMENTATION_TERMS))

    code_query = bool(tokens.intersection(CODE_TERMS))

    main_query = bool(tokens.intersection(MAIN_TERMS))

    overview_query = bool(tokens.intersection(OVERVIEW_TERMS))

    implementation_query = bool(tokens.intersection(IMPLEMENTATION_TERMS))

    caller_query = bool(tokens.intersection(CALLER_TERMS))

    frontend_query = bool(tokens.intersection(FRONTEND_TERMS))

    backend_query = bool(tokens.intersection(BACKEND_TERMS))

    test_query = bool(tokens.intersection(TEST_TERMS))

    filename_candidates = extract_filename_targets(query)

    route_targets = extract_route_targets(query)

    function_targets = extract_function_targets(query)

    component_targets = extract_component_targets(query)

    return {
        "normalized": normalized_query,
        "tokens": tokens,
        "documentation_query": documentation_query,
        "code_query": code_query,
        "main_query": main_query,
        "overview_query": overview_query,
        "implementation_query": implementation_query,
        "caller_query": caller_query,
        "frontend_query": frontend_query,
        "backend_query": backend_query,
        "test_query": test_query,
        "filename_candidates": filename_candidates,
        "route_targets": route_targets,
        "function_targets": function_targets,
        "component_targets": component_targets,
    }


# ==================================================
# METADATA HELPERS
# ==================================================

def get_metadata_value(metadata, *keys,):
    if not metadata:
        return ""

    for key in keys:
        value = metadata.get(key)

        if value is not None:
            value = str(value).strip()

            if value:
                return value

    return ""


def get_file_path(metadata):
    return get_metadata_value(
        metadata,
        "file_path",
        "relative_path",
        "path",
        "file",
    )


def get_symbol_name(metadata):
    return get_metadata_value(
        metadata,
        "symbol_name",
        "symbol",
        "name",
    )


def get_symbol_type(metadata):
    return get_metadata_value(
        metadata,
        "symbol_type",
        "type",
    )


def get_class_name(metadata):
    return get_metadata_value(
        metadata,
        "class_name",
        "class",
    )


def get_language(metadata):
    return get_metadata_value(
        metadata,
        "language",
    )


# ==================================================
# PATH HELPERS
# ==================================================

def normalize_path_for_matching(
    path,
):
    if not path:
        return ""

    path = str(path)
    path = path.replace("\\", "/",)
    path = path.lower()

    return path


def get_extension(file_path):
    if not file_path:
        return ""

    return Path(file_path).suffix.lower()


def is_documentation_file(file_path,):
    return (
        get_extension(file_path)
        in DOCUMENTATION_EXTENSIONS
    )


def is_code_file(
    file_path,
):
    return (
        get_extension(file_path)
        in CODE_EXTENSIONS
    )


# ==================================================
# GENERATED / VENDOR DETECTION
# ==================================================

def is_generated_or_vendor_file(file_path, ):
    normalized_path = (normalize_path_for_matching(file_path))

    path_parts = set(normalized_path.split("/"))

    for term in GENERATED_PATH_TERMS:
        if term in path_parts:
            return True

    file_name = (normalized_path.split("/")[-1])

    for suffix in MINIFIED_FILE_NAMES:
        if file_name.endswith(suffix):
            return True

    return False


# ==================================================
# TOKEN OVERLAP
# ==================================================

def calculate_token_overlap(
    query_tokens,
    text,
):
    if not query_tokens or not text:
        return 0.0

    text_tokens = set(
        tokenize(text)
    )

    if not text_tokens:
        return 0.0

    matched = (
        query_tokens.intersection(
            text_tokens
        )
    )

    return len(matched) / max(
        len(query_tokens),
        1,
    )


# ==================================================
# EXACT TARGET MATCHING
# ==================================================

def extract_routes_from_text(text):
    """
    Extract API-style routes from a document or metadata string.
    """

    if not text:
        return []

    matches = re.findall(
        r"(?<![\w])/"
        r"[a-z0-9_.~-]+"
        r"(?:/[a-z0-9_.~:{}$-]+)*",
        normalize_text(text),
    )

    routes = []

    for route in matches:
        route = route.rstrip(".,;:!?)]}")

        if route in {"/", "/api", "/auth"}:
            continue

        if route not in routes:
            routes.append(route)

    return routes


def calculate_route_match_score(
    query_info,
    file_path,
    symbol_name,
    class_name,
    document,
):
    """
    Strongly reward exact API route matches.

    Exact route matches are intentionally much stronger than
    individual route-segment matches. This prevents a query such as
    "/auth/login" from incorrectly ranking "/auth/logout" above the
    actual login handler.
    """

    routes = query_info.get(
        "route_targets",
        [],
    )

    if not routes:
        return 0.0

    file_text = normalize_path_for_matching(
        file_path
    )

    symbol_text = normalize_text(
        symbol_name
    )

    class_text = normalize_text(
        class_name
    )

    document_text = normalize_text(
        document
    )

    combined_text = " ".join(
        [
            file_text,
            symbol_text,
            class_text,
            document_text,
        ]
    )

    score = 0.0

    document_routes = extract_routes_from_text(
        document_text
    )

    for route in routes:
        normalized_route = normalize_path_for_matching(
            route
        )

        route_without_leading_slash = (
            normalized_route.lstrip("/")
        )

        exact_document_match = (
            normalized_route in document_text
        )

        exact_file_match = (
            normalized_route in file_text
        )

        exact_symbol_match = (
            normalized_route in symbol_text
        )

        exact_class_match = (
            normalized_route in class_text
        )

        # --------------------------------------------------
        # Exact route matches
        # --------------------------------------------------

        if exact_document_match:
            score += 70.0

        if exact_file_match:
            score += 35.0

        if exact_symbol_match:
            score += 25.0

        if exact_class_match:
            score += 20.0

        # --------------------------------------------------
        # Contiguous route without leading slash
        # --------------------------------------------------

        if (
            route_without_leading_slash
            and route_without_leading_slash in combined_text
        ):
            score += 20.0

        # --------------------------------------------------
        # Route segment matching
        #
        # Keep this deliberately weak. A document containing
        # "auth" and "login" somewhere is not equivalent to
        # actually implementing /auth/login.
        # --------------------------------------------------

        route_segments = [
            segment
            for segment in route_without_leading_slash.split("/")
            if segment
        ]

        if route_segments:
            matched_segments = 0

            for segment in route_segments:
                if segment in combined_text:
                    matched_segments += 1

            if not (
                exact_document_match
                or exact_file_match
                or exact_symbol_match
                or exact_class_match
            ):
                if matched_segments == len(route_segments):
                    score += 5.0
                elif matched_segments:
                    score += matched_segments * 1.5

        # --------------------------------------------------
        # Sibling-route penalty
        #
        # Example:
        # query      -> /auth/login
        # document   -> /auth/logout
        #
        # Shared "auth" should not make logout look like login.
        # --------------------------------------------------

        if not exact_document_match and document_routes:
            route_segments = set(
                segment
                for segment in route_without_leading_slash.split("/")
                if segment
            )

            for document_route in document_routes:
                if document_route == normalized_route:
                    continue

                document_segments = set(
                    segment
                    for segment in document_route.lstrip("/").split("/")
                    if segment
                )

                if (
                    route_segments
                    and document_segments
                    and route_segments.intersection(document_segments)
                ):
                    score -= 12.0

    return score


def calculate_function_target_score(
    query_info,
    file_path,
    symbol_name,
    class_name,
    document,
):
    """
    Strongly reward explicit function/method targets.
    """

    targets = query_info.get(
        "function_targets",
        [],
    )

    if not targets:
        return 0.0

    normalized_file = normalize_path_for_matching(
        file_path
    )

    normalized_symbol = normalize_text(
        symbol_name
    )

    normalized_class = normalize_text(
        class_name
    )

    normalized_document = normalize_text(
        document
    )

    score = 0.0

    for target in targets:

        if target == normalized_symbol:
            score += 45.0

        elif target in normalized_symbol:
            score += 25.0

        if target in normalized_class:
            score += 15.0

        if target in normalized_file:
            score += 12.0

        if target in normalized_document:
            score += 12.0

    return score


def calculate_component_target_score(
    query_info,
    file_path,
    symbol_name,
    class_name,
    document,
):
    """
    Strongly reward explicit component/class/context targets.
    """

    targets = query_info.get(
        "component_targets",
        [],
    )

    if not targets:
        return 0.0

    normalized_file = normalize_path_for_matching(
        file_path
    )

    normalized_symbol = normalize_text(
        symbol_name
    )

    normalized_class = normalize_text(
        class_name
    )

    normalized_document = normalize_text(
        document
    )

    score = 0.0

    for target in targets:

        if target == normalized_symbol:
            score += 40.0

        if target == normalized_class:
            score += 40.0

        if target in normalized_symbol:
            score += 20.0

        if target in normalized_class:
            score += 20.0

        if target in normalized_file:
            score += 15.0

        if target in normalized_document:
            score += 10.0

    return score


# ==================================================
# HYBRID MATCHING HELPERS
# ==================================================

def calculate_exact_filename_score(
    query_info,
    file_path,
):
    if not file_path:
        return 0.0

    normalized_path = (
        normalize_path_for_matching(
            file_path
        )
    )

    file_name = (
        normalized_path.split("/")[-1]
    )

    score = 0.0

    for candidate in query_info[
        "filename_candidates"
    ]:

        candidate = (
            normalize_path_for_matching(
                candidate
            )
        )

        if candidate == file_name:
            score += 50.0

        elif candidate in file_name:
            score += 30.0

        elif candidate in normalized_path:
            score += 20.0

    return score


def calculate_path_keyword_score(
    query_tokens,
    file_path,
):
    if not query_tokens or not file_path:
        return 0.0

    normalized_path = (
        normalize_path_for_matching(
            file_path
        )
    )

    path_parts = [
        part
        for part in re.split(
            r"[/_.\-]+",
            normalized_path,
        )
        if part
    ]

    path_tokens = set()

    for part in path_parts:
        path_tokens.update(
            tokenize(part)
        )

    matched_tokens = (
        query_tokens.intersection(
            path_tokens
        )
    )

    if not matched_tokens:
        return 0.0

    return (
        len(matched_tokens)
        * 4.0
    )


def calculate_symbol_match_score(
    query_tokens,
    symbol_name,
):
    if not query_tokens or not symbol_name:
        return 0.0

    normalized_symbol = normalize_text(
        symbol_name
    )

    symbol_tokens = set(
        tokenize(
            normalized_symbol
        )
    )

    matched_tokens = (
        query_tokens.intersection(
            symbol_tokens
        )
    )

    if not matched_tokens:
        return 0.0

    score = (
        len(matched_tokens)
        * 8.0
    )

    normalized_query = " ".join(
        sorted(query_tokens)
    )

    if (
        normalized_query
        and normalized_query
        in normalized_symbol
    ):
        score += 12.0

    return score


def calculate_class_match_score(
    query_tokens,
    class_name,
):
    if not query_tokens or not class_name:
        return 0.0

    normalized_class = normalize_text(
        class_name
    )

    class_tokens = set(
        tokenize(
            normalized_class
        )
    )

    matched_tokens = (
        query_tokens.intersection(
            class_tokens
        )
    )

    if not matched_tokens:
        return 0.0

    return (
        len(matched_tokens)
        * 7.0
    )


def calculate_query_keyword_score(
    query_info,
    document,
    metadata,
):
    query_tokens = query_info[
        "tokens"
    ]

    if not query_tokens:
        return 0.0

    file_path = get_file_path(
        metadata
    )

    symbol_name = get_symbol_name(
        metadata
    )

    class_name = get_class_name(
        metadata
    )

    combined_text = " ".join(
        [
            file_path,
            symbol_name,
            class_name,
            document or "",
        ]
    )

    overlap = calculate_token_overlap(
        query_tokens,
        combined_text,
    )

    return overlap * 6.0


# ==================================================
# QUERY PURPOSE SCORING
# ==================================================

def calculate_test_file_score(
    file_path,
):
    if not file_path:
        return 0.0

    normalized_path = (
        normalize_path_for_matching(
            file_path
        )
    )

    parts = set(
        normalized_path.split("/")
    )

    file_name = (
        normalized_path.split("/")[-1]
    )

    score = 0.0

    if any(
        term in parts
        for term in TEST_FILE_TERMS
    ):
        score += 25.0

    if (
        "test" in file_name
        or "spec" in file_name
    ):
        score += 20.0

    return score


def calculate_frontend_file_score(
    file_path,
):
    if not file_path:
        return 0.0

    normalized_path = (
        normalize_path_for_matching(
            file_path
        )
    )

    parts = set(
        normalized_path.split("/")
    )

    score = 0.0

    for term in FRONTEND_PATH_TERMS:
        if term in parts:
            score += 5.0

    return score


def calculate_backend_file_score(
    file_path,
):
    if not file_path:
        return 0.0

    normalized_path = (
        normalize_path_for_matching(
            file_path
        )
    )

    parts = set(
        normalized_path.split("/")
    )

    score = 0.0

    for term in BACKEND_PATH_TERMS:
        if term in parts:
            score += 5.0

    return score


def calculate_purpose_score(
    query_info,
    file_path,
    symbol_name,
    symbol_type,
    class_name,
    document,
):
    """
    Add query-purpose-aware ranking.

    This prevents queries such as:

        /auth/login tests validation

    from treating every file containing "login"
    as equally useful.
    """

    score = 0.0

    normalized_file = normalize_path_for_matching(
        file_path
    )

    normalized_symbol = normalize_text(
        symbol_name
    )

    normalized_symbol_type = normalize_text(
        symbol_type
    )

    normalized_class = normalize_text(
        class_name
    )

    normalized_document = normalize_text(
        document
    )

    combined = " ".join(
        [
            normalized_file,
            normalized_symbol,
            normalized_symbol_type,
            normalized_class,
            normalized_document,
        ]
    )

    # --------------------------------------------------
    # IMPLEMENTATION QUERY
    # --------------------------------------------------

    if query_info[
        "implementation_query"
    ]:

        if symbol_name:
            score += 5.0

        if symbol_type in {
            "function",
            "method",
            "class",
            "route",
            "handler",
            "controller",
        }:
            score += 8.0

        if any(
            term in normalized_file
            for term in {
                "route",
                "routes",
                "controller",
                "service",
                "handler",
                "api",
                "server",
            }
        ):
            score += 6.0

    # --------------------------------------------------
    # CALLER / USAGE QUERY
    # --------------------------------------------------

    if query_info[
        "caller_query"
    ]:

        if (
            "call"
            in normalized_document
        ):
            score += 3.0

        if (
            "import"
            in normalized_document
        ):
            score += 3.0

        if (
            "fetch"
            in normalized_document
            or "axios"
            in normalized_document
            or ".post("
            in normalized_document
            or ".get("
            in normalized_document
        ):
            score += 6.0

    # --------------------------------------------------
    # FRONTEND QUERY
    # --------------------------------------------------

    if query_info[
        "frontend_query"
    ]:

        score += calculate_frontend_file_score(
            file_path
        )

        if any(
            term in combined
            for term in {
                "axios",
                "fetch",
                "api",
                "component",
                "context",
            }
        ):
            score += 8.0

        if (
            get_extension(file_path)
            in {
                ".js",
                ".jsx",
                ".ts",
                ".tsx",
            }
        ):
            score += 4.0

    # --------------------------------------------------
    # BACKEND QUERY
    # --------------------------------------------------

    if query_info[
        "backend_query"
    ]:

        score += calculate_backend_file_score(
            file_path
        )

        if any(
            term in normalized_file
            for term in {
                "server",
                "route",
                "routes",
                "controller",
                "service",
                "api",
            }
        ):
            score += 10.0

        if any(
            term in normalized_symbol_type
            for term in {
                "route",
                "handler",
                "controller",
                "endpoint",
            }
        ):
            score += 10.0

    # --------------------------------------------------
    # TEST QUERY
    # --------------------------------------------------

    if query_info[
        "test_query"
    ]:

        score += calculate_test_file_score(
            file_path
        )

        if any(
            term in normalized_file
            for term in {
                "test",
                "tests",
                "spec",
                "__tests__",
            }
        ):
            score += 20.0

        if any(
            term in normalized_document
            for term in {
                "assert",
                "pytest",
                "unittest",
                "describe(",
                "it(",
                "test(",
            }
        ):
            score += 10.0

    return score


# ==================================================
# RERANKING
# ==================================================

def calculate_rerank_score(
    query_info,
    document,
    metadata,
    vector_distance,
):
    query_tokens = query_info[
        "tokens"
    ]

    file_path = get_file_path(
        metadata
    )

    symbol_name = get_symbol_name(
        metadata
    )

    symbol_type = get_symbol_type(
        metadata
    )

    class_name = get_class_name(
        metadata
    )

    language = get_language(
        metadata
    )

    normalized_file_path = (
        normalize_path_for_matching(
            file_path
        )
    )

    normalized_file_name = (
        normalized_file_path.split("/")[-1]
        if normalized_file_path
        else ""
    )

    normalized_symbol = normalize_text(
        symbol_name
    )

    normalized_class = normalize_text(
        class_name
    )

    normalized_document = normalize_text(
        document
    )

    try:
        distance = float(
            vector_distance
        )

    except (
        TypeError,
        ValueError,
    ):
        distance = 1.0

    vector_score = 1.0 / (
        1.0
        + max(
            distance,
            0.0,
        )
    )

    score = (
        vector_score
        * 5.0
    )

    # ==================================================
    # SEMANTIC + LEXICAL HYBRID SCORE
    # ==================================================

    file_overlap = calculate_token_overlap(
        query_tokens,
        normalized_file_path,
    )

    symbol_overlap = calculate_token_overlap(
        query_tokens,
        normalized_symbol,
    )

    class_overlap = calculate_token_overlap(
        query_tokens,
        normalized_class,
    )

    document_overlap = calculate_token_overlap(
        query_tokens,
        normalized_document,
    )

    score += (
        file_overlap
        * 8.0
    )

    score += (
        symbol_overlap
        * 12.0
    )

    score += (
        class_overlap
        * 10.0
    )

    score += (
        document_overlap
        * 2.0
    )

    score += calculate_exact_filename_score(
        query_info,
        file_path,
    )

    score += calculate_path_keyword_score(
        query_tokens,
        file_path,
    )

    score += calculate_symbol_match_score(
        query_tokens,
        symbol_name,
    )

    score += calculate_class_match_score(
        query_tokens,
        class_name,
    )

    score += calculate_query_keyword_score(
        query_info,
        document,
        metadata,
    )

    # ==================================================
    # EXACT ENGINEERING TARGET MATCHES
    # ==================================================

    score += calculate_route_match_score(
        query_info=query_info,
        file_path=file_path,
        symbol_name=symbol_name,
        class_name=class_name,
        document=document,
    )

    score += calculate_function_target_score(
        query_info=query_info,
        file_path=file_path,
        symbol_name=symbol_name,
        class_name=class_name,
        document=document,
    )

    score += calculate_component_target_score(
        query_info=query_info,
        file_path=file_path,
        symbol_name=symbol_name,
        class_name=class_name,
        document=document,
    )

    # ==================================================
    # QUERY PURPOSE
    # ==================================================

    score += calculate_purpose_score(
        query_info=query_info,
        file_path=file_path,
        symbol_name=symbol_name,
        symbol_type=symbol_type,
        class_name=class_name,
        document=document,
    )

    # ==================================================
    # EXACT QUERY MATCH
    # ==================================================

    normalized_query = query_info[
        "normalized"
    ]

    if (
        normalized_query
        and normalized_query
        in normalized_file_path
    ):
        score += 8.0

    if (
        normalized_query
        and normalized_query
        in normalized_symbol
    ):
        score += 12.0

    if (
        normalized_query
        and normalized_query
        in normalized_class
    ):
        score += 10.0

    # ==================================================
    # DOCUMENTATION QUERY
    # ==================================================

    if query_info[
        "documentation_query"
    ]:

        if is_documentation_file(
            file_path
        ):
            score += 15.0

        if normalized_file_name in {
            "readme.md",
            "readme.markdown",
            "readme.rst",
            "readme.txt",
        }:
            score += 30.0

        if (
            "/docs/" in normalized_file_path
            or normalized_file_path.startswith(
                "docs/"
            )
        ):
            score += 12.0

    # ==================================================
    # OVERVIEW QUERY
    # ==================================================

    if query_info[
        "overview_query"
    ]:

        if (
            normalized_file_name
            in OVERVIEW_FILES
        ):
            score += 35.0

        if normalized_file_name.startswith(
            "readme"
        ):
            score += 40.0

        if normalized_file_name in {
            "package.json",
            "requirements.txt",
            "pyproject.toml",
            "setup.py",
            "cargo.toml",
            "pom.xml",
            "go.mod",
            "design_guidelines.json",
        }:
            score += 20.0

        if (
            normalized_file_path.startswith(
                "docs/"
            )
            or "/docs/" in normalized_file_path
        ):
            score += 25.0

    # ==================================================
    # CODE QUERY
    # ==================================================

    if query_info[
        "code_query"
    ]:

        if is_code_file(
            file_path
        ):
            score += 4.0

        if symbol_name:
            score += 2.0

        if class_name:
            score += 1.0

    # ==================================================
    # MAIN QUERY
    # ==================================================

    if query_info[
        "main_query"
    ]:

        main_file_names = {
            "main.py",
            "main.js",
            "main.ts",
            "main.java",
            "app.py",
            "application.py",
            "index.js",
            "index.ts",
            "server.py",
            "server.js",
        }

        if normalized_file_name in main_file_names:
            score += 20.0

        if normalized_symbol in {
            "main",
            "__main__",
            "run",
            "start",
            "startup",
        }:
            score += 25.0

        if (
            "main"
            in normalized_symbol
            or "main"
            in normalized_file_name
        ):
            score += 12.0

    # ==================================================
    # EXPLICIT FILE NAME
    # ==================================================

    for filename in query_info[
        "filename_candidates"
    ]:

        if filename in normalized_file_name:
            score += 30.0

        if filename in normalized_file_path:
            score += 20.0

    # ==================================================
    # LANGUAGE
    # ==================================================

    if language:

        normalized_language = normalize_text(
            language
        )

        if normalized_language in query_tokens:
            score += 8.0

    # ==================================================
    # SYMBOL TYPE
    # ==================================================

    if symbol_type:

        normalized_symbol_type = normalize_text(
            symbol_type
        )

        if normalized_symbol_type in query_tokens:
            score += 6.0

    # ==================================================
    # PENALTIES
    # ==================================================

    if is_generated_or_vendor_file(
        file_path
    ):
        score -= 20.0

    if (
        ".min.js" in normalized_file_path
        or ".min.css" in normalized_file_path
    ):
        score -= 30.0

    document_length = len(
        document or ""
    )

    if document_length > 20000:
        score -= 5.0

    if document_length > 50000:
        score -= 10.0

    return score


# ==================================================
# DEDUPLICATION
# ==================================================

def deduplicate_results(
    documents,
    metadatas,
    distances,
):
    """
    Remove exact duplicate chunks while preserving multiple chunks
    from the same file.

    Keeping multiple chunks from one file is important for code-aware
    retrieval. A file can contain several relevant symbols, and the
    first Chroma result for that file is not necessarily the best chunk
    for the current engineering target.

    File-level diversity is applied later, after reranking, when the
    actual relevance score is known.
    """

    unique_results = []
    seen_documents = set()

    for index, document in enumerate(
        documents
    ):
        metadata = (
            metadatas[index]
            if index < len(metadatas)
            else {}
        )

        distance = (
            distances[index]
            if index < len(distances)
            else None
        )

        document_key = normalize_text(
            document
        )

        if (
            document_key
            and document_key in seen_documents
        ):
            continue

        if document_key:
            seen_documents.add(
                document_key
            )

        unique_results.append(
            {
                "document": document,
                "metadata": metadata,
                "distance": distance,
            }
        )

    return unique_results


def select_diverse_results(
    ranked_results,
    top_k,
):
    """
    Select the highest-scoring results while keeping one result per
    file path whenever possible.

    This is intentionally performed after reranking so that, when a
    file contains several chunks, the most relevant chunk for the
    current question wins rather than whichever chunk Chroma returned
    first.
    """

    selected = []
    selected_paths = set()

    for result in ranked_results:
        metadata = result.get(
            "metadata",
            {},
        )

        file_path = normalize_path_for_matching(
            get_file_path(metadata)
        )

        if file_path:
            if file_path in selected_paths:
                continue

            selected_paths.add(
                file_path
            )

        selected.append(
            result
        )

        if len(selected) >= max(
            int(top_k),
            1,
        ):
            break

    return selected


# ==================================================
# REPOSITORY OVERVIEW FILE DISCOVERY
# ==================================================

def discover_overview_files(
    repository_path,
):
    repository_path = Path(
        repository_path
    )

    if not repository_path.exists():
        return []

    found_files = []

    for path in repository_path.rglob("*"):

        if not path.is_file():
            continue

        relative_path = path.relative_to(
            repository_path
        )

        normalized_relative_path = (
            str(relative_path)
            .replace("\\", "/")
            .lower()
        )

        if any(
            part in GENERATED_PATH_TERMS
            for part in Path(
                normalized_relative_path
            ).parts
        ):
            continue

        file_name = path.name.lower()

        if file_name in OVERVIEW_FILES:
            found_files.append(
                path
            )

    found_files.sort(
        key=lambda path: (
            0
            if path.name.lower().startswith(
                "readme"
            )
            else 1,
            len(path.parts),
            str(path).lower(),
        )
    )

    return found_files[
        :OVERVIEW_TOP_K
    ]


# ==================================================
# READ OVERVIEW FILE
# ==================================================

def read_overview_file(
    repository_path,
    file_path,
):
    try:

        file_path = Path(
            file_path
        )

        repository_path = Path(
            repository_path
        ).resolve()

        resolved_path = file_path.resolve()

        if (
            repository_path != resolved_path
            and repository_path
            not in resolved_path.parents
        ):
            return ""

        if not resolved_path.is_file():
            return ""

        if (
            resolved_path.stat().st_size
            > MAX_OVERVIEW_FILE_SIZE
        ):
            return ""

        return resolved_path.read_text(
            encoding="utf-8",
            errors="replace",
        )

    except Exception:
        return ""


# ==================================================
# REPOSITORY STRUCTURE
# ==================================================

def build_repository_structure(
    repository_path,
    max_files=100,
):
    repository_path = Path(
        repository_path
    )

    if not repository_path.exists():
        return ""

    files = []

    ignored_directories = {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        "dist",
        "build",
        "coverage",
    }

    try:

        for path in repository_path.rglob("*"):

            if not path.is_file():
                continue

            relative_path = path.relative_to(
                repository_path
            )

            if any(
                part in ignored_directories
                for part in relative_path.parts
            ):
                continue

            files.append(
                str(relative_path)
                .replace(
                    "\\",
                    "/",
                )
            )

            if len(files) >= max_files:
                break

    except Exception:
        return ""

    files.sort()

    if not files:
        return ""

    return "\n".join(
        f"- {file_path}"
        for file_path in files
    )


# ==================================================
# SYNTHETIC REPOSITORY OVERVIEW
# ==================================================

def build_repository_overview(
    repository_id,
    repository_path,
):
    repository_path = Path(
        repository_path
    )

    overview_parts = [
        f"Repository: {repository_id}",
        "Repository overview and project purpose context.",
    ]

    overview_files = discover_overview_files(
        repository_path
    )

    if overview_files:

        for file_path in overview_files:

            relative_path = file_path.relative_to(
                repository_path
            )

            relative_path = str(
                relative_path
            ).replace(
                "\\",
                "/",
            )

            content = read_overview_file(
                repository_path,
                file_path,
            )

            if not content:
                continue

            if (
                file_path.name.lower()
                == "package.json"
            ):

                try:

                    package_data = json.loads(
                        content
                    )

                    name = package_data.get(
                        "name"
                    )

                    description = package_data.get(
                        "description"
                    )

                    scripts = package_data.get(
                        "scripts",
                        {},
                    )

                    overview_parts.append(
                        f"File: {relative_path}"
                    )

                    if name:
                        overview_parts.append(
                            f"Package name: {name}"
                        )

                    if description:
                        overview_parts.append(
                            f"Description: {description}"
                        )

                    if scripts:
                        overview_parts.append(
                            "Available scripts: "
                            + ", ".join(
                                scripts.keys()
                            )
                        )

                    continue

                except Exception:
                    pass

            overview_parts.append(
                f"File: {relative_path}"
            )

            overview_parts.append(
                content[:30000]
            )

    structure = build_repository_structure(
        repository_path
    )

    if structure:

        overview_parts.append(
            "Repository file structure:"
        )

        overview_parts.append(
            structure
        )

    return "\n\n".join(
        overview_parts
    )


# ==================================================
# OVERVIEW RETRIEVAL
# ==================================================

def retrieve_repository_overview(
    repository_id,
    repository_path,
):
    print()
    print(
        "[OVERVIEW] Building repository overview..."
    )

    overview = build_repository_overview(
        repository_id,
        repository_path,
    )

    if not overview:

        print(
            "[OVERVIEW] No overview context found."
        )

        return None

    print(
        "[OVERVIEW] Overview context created."
    )

    return {
        "document": overview,
        "metadata": {
            "repository_id": repository_id,
            "file_path": "__repository_overview__",
            "symbol_name": "repository_overview",
            "symbol_type": "overview",
            "class_name": "",
            "language": "text",
        },
        "distance": 0.0,
        "score": 100.0,
    }


# ==================================================
# RETRIEVE CODE
# ==================================================

def retrieve_code(
    query,
    repository_id,
    top_k=DEFAULT_TOP_K,
):
    print()
    print("=" * 60)
    print("ENHANCED CODE RETRIEVAL")
    print("=" * 60)

    print(
        f"Repository : {repository_id}"
    )

    print(
        f"Query      : {query}"
    )

    print(
        f"Final Top K: {top_k}"
    )

    if not query or not str(query).strip():

        print(
            "ERROR: Empty query."
        )

        return {
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }

    query = str(
        query
    ).strip()

    if not repository_id:
        raise ValueError(
            "repository_id is required."
        )

    # ==================================================
    # QUERY ANALYSIS
    # ==================================================

    query_info = analyze_query(
        query
    )

    print()
    print(
        "[1] Query analysis"
    )

    print(
        "Normalized query:",
        query_info["normalized"],
    )

    print(
        "Tokens:",
        sorted(
            query_info["tokens"]
        ),
    )

    print(
        "Documentation query:",
        query_info[
            "documentation_query"
        ],
    )

    print(
        "Overview query:",
        query_info[
            "overview_query"
        ],
    )

    print(
        "Code query:",
        query_info[
            "code_query"
        ],
    )

    print(
        "Main/entry query:",
        query_info[
            "main_query"
        ],
    )

    print(
        "Implementation query:",
        query_info[
            "implementation_query"
        ],
    )

    print(
        "Caller query:",
        query_info[
            "caller_query"
        ],
    )

    print(
        "Frontend query:",
        query_info[
            "frontend_query"
        ],
    )

    print(
        "Backend query:",
        query_info[
            "backend_query"
        ],
    )

    print(
        "Test query:",
        query_info[
            "test_query"
        ],
    )

    print(
        "Filename candidates:",
        query_info[
            "filename_candidates"
        ],
    )

    print(
        "Route targets:",
        query_info[
            "route_targets"
        ],
    )

    print(
        "Function targets:",
        query_info[
            "function_targets"
        ],
    )

    print(
        "Component targets:",
        query_info[
            "component_targets"
        ],
    )

    # ==================================================
    # SPECIAL OVERVIEW RETRIEVAL
    # ==================================================

    repository_path = get_repository_path(
        repository_id
    )

    overview_result = None

    if query_info[
        "overview_query"
    ]:

        overview_result = retrieve_repository_overview(
            repository_id,
            repository_path,
        )

    # ==================================================
    # EMBEDDING
    # ==================================================

    print()
    print(
        "[2] Generating query embedding..."
    )

    query_embedding = generate_embedding(
        query
    )

    if query_embedding is None:

        print(
            "ERROR: Query embedding generation failed."
        )

        if overview_result:

            return {
                "documents": [
                    [
                        overview_result[
                            "document"
                        ]
                    ]
                ],
                "metadatas": [
                    [
                        overview_result[
                            "metadata"
                        ]
                    ]
                ],
                "distances": [
                    [0.0]
                ],
            }

        return {
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }

    try:

        print(
            "Embedding dimensions:",
            len(query_embedding),
        )

    except Exception:
        pass

    # ==================================================
    # CHROMA SEARCH
    # ==================================================

    print()
    print(
        "[3] Searching ChromaDB for candidates..."
    )

    candidate_top_k = max(
        CANDIDATE_TOP_K,
        top_k * 5,
    )

    print(
        "Candidate Top K:",
        candidate_top_k,
    )

    results = search_chunks(
        query_embedding=query_embedding,
        repository_id=repository_id,
        top_k=candidate_top_k,
    )

    documents = results.get(
        "documents",
        [[]],
    )[0]

    metadatas = results.get(
        "metadatas",
        [[]],
    )[0]

    distances = results.get(
        "distances",
        [[]],
    )[0]

    print()
    print(
        "Candidates retrieved:",
        len(documents),
    )

    unique_results = deduplicate_results(
        documents,
        metadatas,
        distances,
    )

    print(
        "Unique candidates:",
        len(unique_results),
    )

    # ==================================================
    # HYBRID RERANK
    # ==================================================

    print()
    print(
        "[4] Applying hybrid semantic + lexical reranking..."
    )

    ranked_results = []

    for result in unique_results:

        rerank_score = calculate_rerank_score(
            query_info=query_info,
            document=result[
                "document"
            ],
            metadata=result[
                "metadata"
            ],
            vector_distance=result[
                "distance"
            ],
        )

        ranked_results.append(
            {
                "document": result[
                    "document"
                ],
                "metadata": result[
                    "metadata"
                ],
                "distance": result[
                    "distance"
                ],
                "score": rerank_score,
            }
        )

    ranked_results.sort(
        key=lambda item: item[
            "score"
        ],
        reverse=True,
    )

    # ==================================================
    # OVERVIEW RESULT
    # ==================================================

    if overview_result:

        print()
        print(
            "[5] Overview query detected."
        )

        print(
            "Adding repository overview context."
        )

        ranked_results.insert(
            0,
            overview_result,
        )

    # ==================================================
    # FINAL RESULTS
    # ==================================================

    final_results = select_diverse_results(
        ranked_results=ranked_results,
        top_k=top_k,
    )

    final_documents = [
        result[
            "document"
        ]
        for result in final_results
    ]

    final_metadatas = [
        result[
            "metadata"
        ]
        for result in final_results
    ]

    final_distances = [
        result[
            "distance"
        ]
        for result in final_results
    ]

    print()
    print("=" * 60)
    print(
        "FINAL RETRIEVAL RESULTS"
    )
    print("=" * 60)

    print(
        "Candidates:",
        len(documents),
    )

    print(
        "After deduplication:",
        len(unique_results),
    )

    print(
        "Final results:",
        len(final_results),
    )

    for index, result in enumerate(
        final_results,
        start=1,
    ):

        metadata = result[
            "metadata"
        ]

        print()
        print(
            "-" * 60
        )

        print(
            f"Result #{index}"
        )

        print(
            "Rerank score:",
            round(
                result[
                    "score"
                ],
                4,
            ),
        )

        print(
            "Vector distance:",
            result[
                "distance"
            ],
        )

        print(
            "File:",
            get_file_path(
                metadata
            ),
        )

        print(
            "Symbol:",
            get_symbol_name(
                metadata
            ),
        )

        print(
            "Symbol type:",
            get_symbol_type(
                metadata
            ),
        )

        print(
            "Class:",
            get_class_name(
                metadata
            ),
        )

        print(
            "Language:",
            get_language(
                metadata
            ),
        )

        preview = (
            result[
                "document"
            ]
            or ""
        )[:500]

        print()
        print(
            "Preview:"
        )

        print(
            preview
        )

        if len(
            result[
                "document"
            ]
            or ""
        ) > 500:

            print(
                "..."
            )

    print()
    print("=" * 60)

    print(
        f"Retrieved {len(final_results)} "
        f"high-quality chunks from "
        f"'{repository_id}'"
    )

    print("=" * 60)

    return {
        "documents": [
            final_documents
        ],
        "metadatas": [
            final_metadatas
        ],
        "distances": [
            final_distances
        ],
    }


# ==================================================
# LOCAL TEST
# ==================================================

if __name__ == "__main__":

    repositories = list_repositories()

    if not repositories:

        print("=" * 60)
        print(
            "REPOSITORY RETRIEVAL"
        )
        print("=" * 60)

        print()
        print(
            "No downloaded repositories found."
        )

        print(
            "Download a GitHub repository first."
        )

        raise SystemExit

    print("=" * 60)
    print(
        "AVAILABLE REPOSITORIES"
    )
    print("=" * 60)

    print()

    for index, repository in enumerate(
        repositories,
        start=1,
    ):

        print(
            f"{index}. "
            f"{repository.get('repository_id', repository)}"
        )

    print()

    try:

        choice = int(
            input(
                "Select repository number: "
            )
        )

    except ValueError:

        print(
            "Invalid input. Please enter a number."
        )

        raise SystemExit

    if (
        choice < 1
        or choice > len(repositories)
    ):

        print(
            "Invalid repository selection."
        )

        raise SystemExit

    selected_repository = repositories[
        choice - 1
    ]

    if isinstance(
        selected_repository,
        dict,
    ):

        repository_id = (
            selected_repository.get(
                "repository_id"
            )
        )

    else:

        repository_id = (
            selected_repository
        )

    if not repository_id:

        print(
            "Could not determine repository ID."
        )

        raise SystemExit

    repository_path = get_repository_path(
        repository_id
    )

    print()
    print(
        f"Selected repository : "
        f"{repository_id}"
    )

    print(
        f"Repository path     : "
        f"{repository_path}"
    )

    query = input(
        "\nEnter a repository question: "
    )

    results = retrieve_code(
        query=query,
        repository_id=repository_id,
        top_k=5,
    )

    documents = results.get(
        "documents",
        [[]],
    )[0]

    metadatas = results.get(
        "metadatas",
        [[]],
    )[0]

    distances = results.get(
        "distances",
        [[]],
    )[0]

    if not documents:

        print()
        print(
            "No relevant repository context found."
        )

        raise SystemExit

    print()
    print("=" * 60)
    print(
        "ENHANCED REPOSITORY-ISOLATED SEARCH"
    )
    print("=" * 60)

    print(
        f"Repository : {repository_id}"
    )

    for index, document in enumerate(
        documents
    ):

        metadata = (
            metadatas[index]
            if index < len(metadatas)
            else {}
        )

        distance = (
            distances[index]
            if index < len(distances)
            else None
        )

        print()
        print(
            "-" * 60
        )

        print(
            f"Result     : {index + 1}"
        )

        print(
            "Repository :",
            metadata.get(
                "repository_id",
                "",
            ),
        )

        print(
            "File       :",
            metadata.get(
                "file_path",
                "",
            ),
        )

        print(
            "Symbol     :",
            metadata.get(
                "symbol_name",
                "",
            ),
        )

        print(
            "Class      :",
            metadata.get(
                "class_name",
                "",
            ),
        )

        print(
            "Distance   :",
            distance,
        )

        print()
        print(
            "Code:"
        )

        print(
            document
        )