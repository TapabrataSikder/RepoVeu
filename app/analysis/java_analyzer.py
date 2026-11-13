from tree_sitter_language_pack import get_parser
from app.analysis.code_model import CodeSymbol


def get_node_text(node, source_code):
    return source_code[
        node.start_byte:node.end_byte
    ].decode(
        "utf-8",
        errors="replace"
    )


def extract_java_methods(code, file_path=""):
    parser = get_parser("java")
    source_code = code.encode("utf-8")
    tree = parser.parse(source_code)

    methods = []

    def extract_calls(node):
        calls = []

        if node.type == "method_invocation":
            identifiers = [
                child
                for child in node.named_children
                if child.type == "identifier"
            ]

            if identifiers:
                calls.append(
                    get_node_text(
                        identifiers[-1],
                        source_code
                    )
                )

        for child in node.named_children:
            calls.extend(
                extract_calls(child)
            )

        return calls

    def extract_parameters(node):
        parameters = []

        for child in node.named_children:

            if child.type == "formal_parameters":

                for parameter in child.named_children:
                    parameters.append(
                        get_node_text(
                            parameter,
                            source_code
                        )
                    )

        return parameters

    def extract_return_type(node):

        for child in node.named_children:

            if child.type in {
                "void_type",
                "type_identifier",
                "integral_type",
                "floating_point_type",
                "boolean_type",
                "generic_type",
                "array_type",
                "scoped_type_identifier"
            }:
                return get_node_text(
                    child,
                    source_code
                )

        return ""

    def extract_modifiers(node):

        visibility = ""
        annotations = []

        for child in node.children:

            if child.type != "modifiers":
                continue

            for modifier in child.children:

                modifier_text = get_node_text(
                    modifier,
                    source_code
                ).strip()

                if modifier.type in {
                    "marker_annotation",
                    "annotation"
                }:
                    annotations.append(
                        modifier_text
                    )

                elif modifier_text in {
                    "public",
                    "private",
                    "protected"
                }:
                    visibility = modifier_text

        return visibility, annotations

    def extract_class_name(node):

        for child in node.named_children:

            if child.type == "identifier":
                return get_node_text(
                    child,
                    source_code
                )

        return ""

    def walk(node, current_class=""):

        if node.type == "class_declaration":
            current_class = extract_class_name(node)

        if node.type == "method_declaration":

            method_name = ""

            parameters = extract_parameters(node)

            calls = extract_calls(node)

            return_type = extract_return_type(node)

            visibility, annotations = extract_modifiers(
                node
            )

            for child in node.named_children:

                if child.type == "identifier":

                    method_name = get_node_text(
                        child,
                        source_code
                    )

                    break

            calls = list(
                dict.fromkeys(calls)
            )

            methods.append(
                CodeSymbol(
                    type="method",
                    name=method_name,
                    parameters=parameters,
                    calls=calls,
                    file_path=file_path,
                    language="java",
                    start_line=node.start_point.row + 1,
                    end_line=node.end_point.row + 1,
                    class_name=current_class,
                    return_type=return_type,
                    visibility=visibility,
                    annotations=annotations
                )
            )

        for child in node.named_children:

            walk(
                child,
                current_class
            )

    walk(tree.root_node)

    return methods


if __name__ == "__main__":

    code = """
package com.example.demo;

public class UserService {

    @Test
    public String getUser(String username) {
        User user = findUser(username);
        return user.getName();
    }

    private void deleteUser(String username) {
        validateUser(username);
        removeUser(username);
    }

    @Override
    public String toString() {
        return "UserService";
    }
}
"""

    file_path = "src/main/java/UserService.java"

    methods = extract_java_methods(
        code,
        file_path
    )

    print("=" * 50)
    print("JAVA METHOD ANALYSIS")
    print("=" * 50)

    for method in methods:

        print(f"Method      : {method.name}")
        print(f"Class       : {method.class_name}")
        print(f"Language    : {method.language}")
        print(f"File        : {method.file_path}")
        print(f"Visibility  : {method.visibility}")
        print(f"Return Type : {method.return_type}")
        print(f"Parameters  : {method.parameters}")
        print(f"Calls       : {method.calls}")
        print(f"Annotations : {method.annotations}")
        print(
            f"Lines       : "
            f"{method.start_line} - "
            f"{method.end_line}"
        )
        print("-" * 50)