import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


# ==================================================
# ENGINEERING INTENT TYPES
# ==================================================

class EngineeringIntentType(str, Enum):
    """
    Supported engineering actions that the assistant
    can perform on a repository.
    """

    EXPLAIN = "explain"
    DEBUG = "debug"
    GENERATE_CODE = "generate_code"
    GENERATE_TEST = "generate_test"
    REFACTOR = "refactor"
    IMPACT_ANALYSIS = "impact_analysis"
    ARCHITECTURE = "architecture"
    SECURITY = "security"
    DEPENDENCY = "dependency"
    UNKNOWN = "unknown"


# ==================================================
# ENGINEERING INTENT RESULT
# ==================================================

@dataclass
class EngineeringIntent:
    """
    Represents the detected engineering intent of a
    developer question.
    """

    intent: EngineeringIntentType
    confidence: float
    requires_repository_context: bool
    requires_code_generation: bool
    requires_validation: bool
    target: Optional[str] = None
    reason: str = ""


# ==================================================
# INTENT CLASSIFIER
# ==================================================

class IntentClassifier:
    """
    Simple semantic-style engineering intent classifier.

    This version does not depend on exact questions.

    Instead of matching complete sentences, it looks
    for engineering concepts and combines their signals.

    Example:

        "Why is /auth/login returning 401?"

    is understood from signals such as:

        why + returning + 401

    rather than from one hard-coded question pattern.

    The classifier is deterministic and does not use an LLM.

    Later, an LLM can be added as a fallback for questions
    that remain ambiguous.
    """

    def __init__(self):
        self.intent_signals = {

            # --------------------------------------------------
            # DEBUG
            # --------------------------------------------------

            EngineeringIntentType.DEBUG: {
                "strong": [
                    "debug",
                    "debugging",
                    "bug",
                    "bugs",
                    "error",
                    "errors",
                    "exception",
                    "exceptions",
                    "crash",
                    "crashing",
                    "failure",
                    "failures",
                    "failing",
                    "fails",
                    "failed",
                    "broken",
                    "issue",
                    "issues",
                    "wrong",
                    "401",
                    "403",
                    "404",
                    "409",
                    "422",
                    "429",
                    "500",
                    "502",
                    "503",
                    "504",
                    "traceback",
                    "stacktrace",
                    "stack trace",
                ],

                "context": [
                    "why",
                    "causing",
                    "cause",
                    "root cause",
                    "returning",
                    "returns",
                    "throw",
                    "throws",
                    "thrown",
                    "not working",
                    "doesn't work",
                    "does not work",
                    "unexpected",
                    "problem",
                ],
            },

            # --------------------------------------------------
            # GENERATE TEST
            # --------------------------------------------------

            EngineeringIntentType.GENERATE_TEST: {
                "strong": [
                    "test",
                    "tests",
                    "testing",
                    "unit test",
                    "unit tests",
                    "integration test",
                    "integration tests",
                    "test case",
                    "test cases",
                ],

                "context": [
                    "write",
                    "create",
                    "generate",
                    "add",
                    "coverage",
                    "verify",
                    "validate",
                ],
            },

            # --------------------------------------------------
            # GENERATE CODE
            # --------------------------------------------------

            EngineeringIntentType.GENERATE_CODE: {
                "strong": [
                    "implement",
                    "implementation",
                    "generate code",
                    "write code",
                    "create code",
                    "add feature",
                    "add functionality",
                    "new endpoint",
                    "new api",
                    "new function",
                    "new class",
                    "new method",
                ],

                "context": [
                    "write",
                    "create",
                    "generate",
                    "build",
                    "add",
                    "implement",
                    "how can i",
                    "how do i",
                ],
            },

            # --------------------------------------------------
            # REFACTOR
            # --------------------------------------------------

            EngineeringIntentType.REFACTOR: {
                "strong": [
                    "refactor",
                    "refactoring",
                    "cleanup",
                    "clean up",
                    "restructure",
                    "simplify",
                    "duplication",
                    "code smell",
                    "maintainability",
                ],

                "context": [
                    "improve",
                    "better",
                    "simplify",
                    "clean",
                    "restructure",
                    "maintain",
                ],
            },

            # --------------------------------------------------
            # IMPACT ANALYSIS
            # --------------------------------------------------

            EngineeringIntentType.IMPACT_ANALYSIS: {
                "strong": [
                    "impact",
                    "affected",
                    "affected files",
                    "affected components",
                    "affected modules",
                    "downstream",
                    "upstream",
                    "depends on",
                    "dependencies on",
                    "where is this used",
                    "who uses",
                    "what uses",
                    "what will break",
                    "what could break",
                ],

                "context": [
                    "change",
                    "modify",
                    "update",
                    "replace",
                    "remove",
                    "affected",
                    "files",
                    "components",
                    "modules",
                    "parts",
                ],
            },

            # --------------------------------------------------
            # ARCHITECTURE
            # --------------------------------------------------

            EngineeringIntentType.ARCHITECTURE: {
                "strong": [
                    "architecture",
                    "architectural",
                    "system design",
                    "high level design",
                    "application flow",
                    "system flow",
                    "system structure",
                    "application structure",
                    "components interact",
                ],

                "context": [
                    "structure",
                    "components",
                    "modules",
                    "services",
                    "flow",
                    "design",
                    "interact",
                ],
            },

            # --------------------------------------------------
            # SECURITY
            # --------------------------------------------------

            EngineeringIntentType.SECURITY: {
                "strong": [
                    "security",
                    "secure",
                    "vulnerability",
                    "vulnerabilities",
                    "exploit",
                    "exploitable",
                    "sql injection",
                    "xss",
                    "csrf",
                    "api key",
                    "secret",
                    "secrets",
                    "authentication",
                    "authorization",
                    "permissions",
                ],

                "context": [
                    "risk",
                    "attack",
                    "protect",
                    "unsafe",
                    "exposed",
                    "permission",
                    "access",
                ],
            },

            # --------------------------------------------------
            # DEPENDENCY
            # --------------------------------------------------

            EngineeringIntentType.DEPENDENCY: {
                "strong": [
                    "dependency",
                    "dependencies",
                    "package",
                    "packages",
                    "library",
                    "libraries",
                    "requirements",
                    "package.json",
                    "requirements.txt",
                    "pyproject.toml",
                ],

                "context": [
                    "upgrade",
                    "upgrading",
                    "version",
                    "versions",
                    "install",
                    "update",
                    "remove",
                ],
            },

            # --------------------------------------------------
            # EXPLAIN
            # --------------------------------------------------

            EngineeringIntentType.EXPLAIN: {
                "strong": [
                    "explain",
                    "describe",
                    "purpose",
                    "meaning",
                    "understand",
                ],

                "context": [
                    "what",
                    "how",
                    "why",
                    "does",
                    "is",
                    "works",
                ],
            },
        }

    # ==================================================
    # PUBLIC METHOD
    # ==================================================

    def classify(self, question: str) -> EngineeringIntent:
        """
        Classify a developer question into an engineering
        intent.
        """

        if not isinstance(question, str):
            raise TypeError("question must be a string.")

        question = question.strip()

        if not question:
            return EngineeringIntent(
                intent=EngineeringIntentType.UNKNOWN,
                confidence=0.0,
                requires_repository_context=False,
                requires_code_generation=False,
                requires_validation=False,
                reason="The question is empty.",
            )

        normalized_question = self._normalize_question(
            question
        )

        scores = self._calculate_scores(
            normalized_question
        )

        detected_intent = self._select_intent(
            scores
        )

        confidence = self._calculate_confidence(
            scores,
            detected_intent,
        )

        return self._build_result(
            intent=detected_intent,
            confidence=confidence,
            question=normalized_question,
            scores=scores,
        )

    # ==================================================
    # NORMALIZATION
    # ==================================================

    def _normalize_question(
        self,
        question: str,
    ) -> str:
        """
        Normalize the question before classification.
        """

        question = question.lower()

        question = re.sub(
            r"\s+",
            " ",
            question,
        )

        return question.strip()

    # ==================================================
    # SIGNAL MATCHING
    # ==================================================

    def _contains_signal(
        self,
        question: str,
        signal: str,
    ) -> bool:
        """
        Check whether a signal exists as a complete word
        or phrase in the question.
        """

        if " " in signal:
            return signal in question

        pattern = rf"\b{re.escape(signal)}\b"

        return bool(
            re.search(
                pattern,
                question,
            )
        )

    # ==================================================
    # SCORE CALCULATION
    # ==================================================

    def _calculate_scores(
        self,
        question: str,
    ) -> dict:
        """
        Calculate an intent score using engineering signals.

        Strong signals contribute more than contextual
        signals.

        This allows different question wording to map
        to the same intent.
        """

        scores = {
            intent: 0
            for intent in self.intent_signals
        }

        for intent, signal_groups in self.intent_signals.items():

            strong_signals = signal_groups.get(
                "strong",
                [],
            )

            context_signals = signal_groups.get(
                "context",
                [],
            )

            for signal in strong_signals:

                if self._contains_signal(
                    question,
                    signal,
                ):
                    scores[intent] += 2

            for signal in context_signals:

                if self._contains_signal(
                    question,
                    signal,
                ):
                    scores[intent] += 1

        return scores

    # ==================================================
    # INTENT SELECTION
    # ==================================================

    def _select_intent(
        self,
        scores: dict,
    ) -> EngineeringIntentType:
        """
        Select the highest scoring intent.

        Explicit engineering actions receive priority
        when scores are equal.

        Debugging also receives priority when an error
        signal is combined with a problem/question signal.
        """

        if not scores:
            return EngineeringIntentType.UNKNOWN

        priority_order = [
            EngineeringIntentType.DEBUG,
            EngineeringIntentType.GENERATE_TEST,
            EngineeringIntentType.GENERATE_CODE,
            EngineeringIntentType.REFACTOR,
            EngineeringIntentType.IMPACT_ANALYSIS,
            EngineeringIntentType.SECURITY,
            EngineeringIntentType.DEPENDENCY,
            EngineeringIntentType.ARCHITECTURE,
            EngineeringIntentType.EXPLAIN,
        ]

        best_intent = EngineeringIntentType.UNKNOWN
        best_score = 0

        for intent in priority_order:

            score = scores.get(
                intent,
                0,
            )

            if score > best_score:
                best_score = score
                best_intent = intent

        return best_intent

    # ==================================================
    # CONFIDENCE
    # ==================================================

    def _calculate_confidence(
        self,
        scores: dict,
        selected_intent: EngineeringIntentType,
    ) -> float:
        """
        Calculate a deterministic confidence score.

        This is not a statistical probability.

        It is an internal indicator of how strongly the
        question matches the selected intent.
        """

        if selected_intent == EngineeringIntentType.UNKNOWN:
            return 0.0

        highest_score = scores.get(
            selected_intent,
            0,
        )

        if highest_score <= 0:
            return 0.0

        sorted_scores = sorted(
            scores.values(),
            reverse=True,
        )

        second_score = (
            sorted_scores[1]
            if len(sorted_scores) > 1
            else 0
        )

        if highest_score >= 5:
            confidence = 0.95

        elif highest_score >= 4:
            confidence = 0.90

        elif highest_score >= 3:
            confidence = 0.80

        elif highest_score == 2 and second_score == 0:
            confidence = 0.75

        elif highest_score == second_score:
            confidence = 0.55

        else:
            confidence = 0.65

        return round(
            confidence,
            2,
        )

    # ==================================================
    # RESULT BUILDER
    # ==================================================

    def _build_result(
        self,
        intent: EngineeringIntentType,
        confidence: float,
        question: str,
        scores: dict,
    ) -> EngineeringIntent:
        """
        Build the final structured intent object.
        """

        if intent == EngineeringIntentType.UNKNOWN:

            return EngineeringIntent(
                intent=EngineeringIntentType.UNKNOWN,
                confidence=0.0,
                requires_repository_context=False,
                requires_code_generation=False,
                requires_validation=False,
                reason=(
                    "No supported engineering intent "
                    "was detected."
                ),
            )

        requires_code_generation = intent in {
            EngineeringIntentType.GENERATE_CODE,
            EngineeringIntentType.GENERATE_TEST,
            EngineeringIntentType.REFACTOR,
        }

        requires_validation = intent in {
            EngineeringIntentType.DEBUG,
            EngineeringIntentType.GENERATE_CODE,
            EngineeringIntentType.GENERATE_TEST,
            EngineeringIntentType.REFACTOR,
        }

        requires_repository_context = (
            intent != EngineeringIntentType.UNKNOWN
        )

        reason = self._generate_reason(
            intent=intent,
            question=question,
            scores=scores,
        )

        target = self._extract_target(
            question
        )

        return EngineeringIntent(
            intent=intent,
            confidence=confidence,
            requires_repository_context=(
                requires_repository_context
            ),
            requires_code_generation=(
                requires_code_generation
            ),
            requires_validation=(
                requires_validation
            ),
            target=target,
            reason=reason,
        )

    # ==================================================
    # REASON GENERATION
    # ==================================================

    def _generate_reason(
        self,
        intent: EngineeringIntentType,
        question: str,
        scores: dict,
    ) -> str:
        """
        Generate a human-readable explanation for why
        an intent was selected.
        """

        score = scores.get(
            intent,
            0,
        )

        if intent == EngineeringIntentType.DEBUG:
            return (
                f"Detected debugging-related signals "
                f"with a score of {score}."
            )

        if intent == EngineeringIntentType.GENERATE_CODE:
            return (
                f"Detected code-generation or implementation "
                f"signals with a score of {score}."
            )

        if intent == EngineeringIntentType.GENERATE_TEST:
            return (
                f"Detected test-generation signals "
                f"with a score of {score}."
            )

        if intent == EngineeringIntentType.REFACTOR:
            return (
                f"Detected refactoring or code-improvement "
                f"signals with a score of {score}."
            )

        if intent == EngineeringIntentType.IMPACT_ANALYSIS:
            return (
                f"Detected change-impact or dependency "
                f"signals with a score of {score}."
            )

        if intent == EngineeringIntentType.ARCHITECTURE:
            return (
                f"Detected architecture or system-design "
                f"signals with a score of {score}."
            )

        if intent == EngineeringIntentType.SECURITY:
            return (
                f"Detected security-related signals "
                f"with a score of {score}."
            )

        if intent == EngineeringIntentType.DEPENDENCY:
            return (
                f"Detected dependency or package-related "
                f"signals with a score of {score}."
            )

        if intent == EngineeringIntentType.EXPLAIN:
            return (
                f"Detected code-explanation signals "
                f"with a score of {score}."
            )

        return "Intent detected from the developer question."

    # ==================================================
    # TARGET EXTRACTION
    # ==================================================

    def _extract_target(
        self,
        question: str,
    ) -> Optional[str]:
        """
        Attempt to identify an obvious target from the
        developer's question.

        This remains intentionally conservative.
        """

        patterns = [
            r"\bfunction\s+[`'\"]?([a-zA-Z_][a-zA-Z0-9_]*)",
            r"\bmethod\s+[`'\"]?([a-zA-Z_][a-zA-Z0-9_]*)",
            r"\bclass\s+[`'\"]?([a-zA-Z_][a-zA-Z0-9_]*)",
            r"\bfile\s+[`'\"]?([^`'\"]+)",
            r"\bendpoint\s+[`'\"]?([^`'\"]+)",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                question,
                re.IGNORECASE,
            )

            if match:
                return match.group(1).strip()

        return None


# ==================================================
# CONVENIENCE FUNCTION
# ==================================================

def classify_engineering_intent(
    question: str,
) -> EngineeringIntent:
    """
    Convenience function for classifying a question.
    """

    classifier = IntentClassifier()

    return classifier.classify(
        question
    )


# ==================================================
# LOCAL TESTS
# ==================================================

if __name__ == "__main__":

    classifier = IntentClassifier()

    test_questions = [

        # --------------------------------------------------
        # EXPLAIN
        # --------------------------------------------------

        "What does this function do?",
        "How does authentication work?",
        "Can you explain the login flow?",

        # --------------------------------------------------
        # DEBUG
        # --------------------------------------------------

        "Why is /auth/login returning 401?",
        "Why does login fail?",
        "Why am I getting a 401?",
        "What is causing this error?",
        "Why is this endpoint failing?",
        "Why does this function throw an exception?",
        "The login endpoint is broken.",

        # --------------------------------------------------
        # GENERATE TEST
        # --------------------------------------------------

        "Write unit tests for validate_github_url.",
        "Create integration tests for the login API.",

        # --------------------------------------------------
        # GENERATE CODE
        # --------------------------------------------------

        "Implement OAuth authentication.",
        "How can I add a new orders endpoint?",
        "Write code for a new authentication function.",

        # --------------------------------------------------
        # REFACTOR
        # --------------------------------------------------

        "How can I refactor this function?",
        "How can I improve this code?",
        "Clean up the repository loader.",

        # --------------------------------------------------
        # IMPACT ANALYSIS
        # --------------------------------------------------

        "What files would I need to modify to change the login endpoint?",
        "Which components would be affected if I change authentication?",
        "What could break if I change the login flow?",

        # --------------------------------------------------
        # ARCHITECTURE
        # --------------------------------------------------

        "Explain the architecture of this application.",
        "How do the backend components interact?",

        # --------------------------------------------------
        # SECURITY
        # --------------------------------------------------

        "Are there any security vulnerabilities here?",
        "Is the authentication implementation secure?",

        # --------------------------------------------------
        # DEPENDENCY
        # --------------------------------------------------

        "How can I upgrade this dependency?",
        "What packages does this project depend on?",
    ]

    print()
    print("=" * 70)
    print("ENGINEERING INTENT CLASSIFIER TEST")
    print("=" * 70)

    for question in test_questions:

        result = classifier.classify(
            question
        )

        print()
        print(f"Question   : {question}")
        print(f"Intent     : {result.intent.value}")
        print(f"Confidence : {result.confidence}")
        print(
            f"Repo       : "
            f"{result.requires_repository_context}"
        )
        print(
            f"Code Gen   : "
            f"{result.requires_code_generation}"
        )
        print(
            f"Validation : "
            f"{result.requires_validation}"
        )
        print(
            f"Target     : "
            f"{result.target}"
        )
        print(
            f"Reason     : "
            f"{result.reason}"
        )