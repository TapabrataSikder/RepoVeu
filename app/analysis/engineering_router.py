from dataclasses import dataclass
from typing import Optional

from app.analysis.intent_classifier import (
    EngineeringIntent,
    EngineeringIntentType,
    IntentClassifier,
)


# ==================================================
# ENGINEERING ROUTE
# ==================================================

@dataclass
class EngineeringRoute:
    """
    Represents the workflow selected for a developer
    request.

    This is intentionally separate from
    EngineeringIntent.

    EngineeringIntent answers:

        "What does the developer want?"

    EngineeringRoute answers:

        "Which internal workflow should handle it?"
    """

    intent: EngineeringIntentType

    workflow: str

    use_rag: bool

    generate_code: bool

    run_validation: bool

    requires_user_approval: bool

    target: Optional[str] = None

    reason: str = ""


# ==================================================
# ENGINEERING ROUTER
# ==================================================

class EngineeringRouter:
    """
    Routes developer questions to the appropriate
    engineering workflow.

    IMPORTANT:

    This class does NOT:
        - call an LLM
        - retrieve from ChromaDB
        - modify repository files
        - generate code
        - execute tests

    It only decides which workflow should be used.
    """

    def __init__(
        self,
        classifier: Optional[IntentClassifier] = None,
    ):
        """
        Initialize the router.

        A classifier can be injected for testing.

        If no classifier is supplied, a default
        IntentClassifier is created.
        """

        self.classifier = classifier or IntentClassifier()

    # ==================================================
    # PUBLIC API
    # ==================================================

    def route(
        self,
        question: str,
    ) -> EngineeringRoute:
        """
        Classify and route a developer question.

        Parameters
        ----------
        question:
            Developer's natural-language request.

        Returns
        -------
        EngineeringRoute
            Selected engineering workflow.
        """

        intent = self.classifier.classify(
            question
        )

        return self._build_route(
            intent
        )

    # ==================================================
    # ROUTE BUILDER
    # ==================================================

    def _build_route(
        self,
        intent: EngineeringIntent,
    ) -> EngineeringRoute:
        """
        Convert an EngineeringIntent into an internal
        workflow.
        """

        intent_type = intent.intent

        if intent_type == EngineeringIntentType.EXPLAIN:
            return EngineeringRoute(
                intent=intent_type,
                workflow="code_explanation",
                use_rag=True,
                generate_code=False,
                run_validation=False,
                requires_user_approval=False,
                target=intent.target,
                reason=(
                    "The developer is asking for an "
                    "explanation of the repository code."
                ),
            )

        if intent_type == EngineeringIntentType.DEBUG:
            return EngineeringRoute(
                intent=intent_type,
                workflow="debugging",
                use_rag=True,
                generate_code=True,
                run_validation=True,
                requires_user_approval=True,
                target=intent.target,
                reason=(
                    "The developer is reporting an issue "
                    "or asking for a root-cause analysis."
                ),
            )

        if intent_type == EngineeringIntentType.GENERATE_CODE:
            return EngineeringRoute(
                intent=intent_type,
                workflow="code_generation",
                use_rag=True,
                generate_code=True,
                run_validation=True,
                requires_user_approval=True,
                target=intent.target,
                reason=(
                    "The developer wants new functionality "
                    "or an implementation."
                ),
            )

        if intent_type == EngineeringIntentType.GENERATE_TEST:
            return EngineeringRoute(
                intent=intent_type,
                workflow="test_generation",
                use_rag=True,
                generate_code=True,
                run_validation=True,
                requires_user_approval=True,
                target=intent.target,
                reason=(
                    "The developer wants tests generated "
                    "for repository code."
                ),
            )

        if intent_type == EngineeringIntentType.REFACTOR:
            return EngineeringRoute(
                intent=intent_type,
                workflow="refactoring",
                use_rag=True,
                generate_code=True,
                run_validation=True,
                requires_user_approval=True,
                target=intent.target,
                reason=(
                    "The developer wants existing code "
                    "improved or restructured."
                ),
            )

        if intent_type == EngineeringIntentType.IMPACT_ANALYSIS:
            return EngineeringRoute(
                intent=intent_type,
                workflow="impact_analysis",
                use_rag=True,
                generate_code=False,
                run_validation=False,
                requires_user_approval=False,
                target=intent.target,
                reason=(
                    "The developer wants to understand "
                    "which parts of the repository may "
                    "be affected by a change."
                ),
            )

        if intent_type == EngineeringIntentType.ARCHITECTURE:
            return EngineeringRoute(
                intent=intent_type,
                workflow="architecture_analysis",
                use_rag=True,
                generate_code=False,
                run_validation=False,
                requires_user_approval=False,
                target=intent.target,
                reason=(
                    "The developer wants to understand "
                    "the structure or architecture of "
                    "the repository."
                ),
            )

        if intent_type == EngineeringIntentType.SECURITY:
            return EngineeringRoute(
                intent=intent_type,
                workflow="security_analysis",
                use_rag=True,
                generate_code=False,
                run_validation=False,
                requires_user_approval=False,
                target=intent.target,
                reason=(
                    "The developer wants to identify or "
                    "understand security-related issues."
                ),
            )

        if intent_type == EngineeringIntentType.DEPENDENCY:
            return EngineeringRoute(
                intent=intent_type,
                workflow="dependency_analysis",
                use_rag=True,
                generate_code=False,
                run_validation=False,
                requires_user_approval=False,
                target=intent.target,
                reason=(
                    "The developer wants information about "
                    "packages, libraries, or dependencies."
                ),
            )

        return EngineeringRoute(
            intent=EngineeringIntentType.UNKNOWN,
            workflow="general_rag",
            use_rag=True,
            generate_code=False,
            run_validation=False,
            requires_user_approval=False,
            target=intent.target,
            reason=(
                "The request could not be mapped to a "
                "specific engineering workflow, so the "
                "existing general RAG pipeline will handle it."
            ),
        )


# ==================================================
# CONVENIENCE FUNCTION
# ==================================================

def route_engineering_request(
    question: str,
) -> EngineeringRoute:
    """
    Convenience function for routing a developer
    question.
    """

    router = EngineeringRouter()

    return router.route(
        question
    )


# ==================================================
# LOCAL TEST
# ==================================================

if __name__ == "__main__":

    router = EngineeringRouter()

    test_questions = [
        "What does validate_github_url do?",
        "How is authentication implemented?",
        "Why is the login API returning a 500 error?",
        "Debug the repository loading issue.",
        "Generate code to add OAuth authentication.",
        "Implement a new orders endpoint.",
        "Write unit tests for validate_github_url.",
        "Create integration tests for the login API.",
        "How can I refactor this function?",
        "What files will be affected if I change authentication?",
        "Explain the architecture of this application.",
        "Are there any security vulnerabilities?",
        "What packages does this project depend on?",
    ]

    print()
    print("=" * 70)
    print("ENGINEERING ROUTER TEST")
    print("=" * 70)

    for question in test_questions:

        route = router.route(
            question
        )

        print()
        print(f"Question        : {question}")
        print(f"Intent          : {route.intent.value}")
        print(f"Workflow        : {route.workflow}")
        print(f"Use RAG         : {route.use_rag}")
        print(f"Generate Code   : {route.generate_code}")
        print(f"Run Validation  : {route.run_validation}")
        print(
            f"User Approval   : "
            f"{route.requires_user_approval}"
        )
        print(f"Target          : {route.target}")
        print(f"Reason          : {route.reason}")