from tree_sitter_language_pack import get_parser

from app.analysis.code_model import CodeSymbol


def get_node_text(node, source_code):
    """
    Return the text represented by a Tree-sitter node.
    """

    return source_code[
        node.start_byte:node.end_byte
    ].decode(
        "utf-8",
        errors="replace"
    )


def extract_javascript_functions(code, file_path=""):
    """
    Extract JavaScript function information.

    Returns:
        list[CodeSymbol]
    """

    parser = get_parser("javascript")

    source_code = code.encode("utf-8")

    tree = parser.parse(source_code)

    functions = []

    def extract_calls(node, calls):
        """
        Find function calls inside a function.
        """

        if node.type == "call_expression":

            if node.named_children:

                function_node = node.named_children[0]

                function_name = get_node_text(
                    function_node,
                    source_code
                )

                calls.append(function_name)

        for child in node.named_children:
            extract_calls(child, calls)

    def walk(node):

        if node.type == "function_declaration":

            function_name = None
            parameters = []
            calls = []

            for child in node.named_children:

                # Function name
                if child.type == "identifier":

                    function_name = get_node_text(
                        child,
                        source_code
                    )

                # Parameters
                elif child.type == "formal_parameters":

                    for parameter in child.named_children:

                        parameters.append(
                            get_node_text(
                                parameter,
                                source_code
                            )
                        )

                # Function body
                elif child.type == "statement_block":

                    extract_calls(
                        child,
                        calls
                    )

            # Remove duplicate calls
            calls = list(dict.fromkeys(calls))

            functions.append(
                CodeSymbol(
                    type="function",
                    name=function_name,
                    parameters=parameters,
                    calls=calls,
                    file_path=file_path,
                    language="javascript",
                    start_line=node.start_point.row + 1,
                    end_line=node.end_point.row + 1
                )
            )

        for child in node.named_children:
            walk(child)

    walk(tree.root_node)

    return functions


if __name__ == "__main__":

    code = """
function login(username, password) {

    const user = getUser(username);

    if (verifyPassword(password, user.password)) {
        return generateToken(user);
    }

    return null;
}

function logout(user) {

    clearSession(user);

}
"""

    file_path = "frontend/auth.js"

    functions = extract_javascript_functions(
        code,
        file_path
    )

    print()
    print("=" * 60)
    print("JAVASCRIPT FUNCTION ANALYSIS")
    print("=" * 60)

    for function in functions:

        print()
        print(f"Function   : {function.name}")
        print(f"Language   : {function.language}")
        print(f"File       : {function.file_path}")

        print("Parameters :")

        for parameter in function.parameters:
            print(f"  - {parameter}")

        print("Calls      :")

        for call in function.calls:
            print(f"  - {call}()")

        print(
            f"Lines      : "
            f"{function.start_line} - "
            f"{function.end_line}"
        )

        print("-" * 60)