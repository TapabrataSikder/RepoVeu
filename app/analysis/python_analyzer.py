import ast

from app.analysis.code_model import CodeSymbol


# --------------------------------------------------
# Get function / method call name
# --------------------------------------------------

def get_call_name(node):
    """
    Get the name of a function or method call.
    """

    if isinstance(node.func, ast.Name):
        return node.func.id

    if isinstance(node.func, ast.Attribute):
        return node.func.attr

    return "unknown"


# --------------------------------------------------
# Extract calls from an AST node
# --------------------------------------------------

def extract_calls(node):
    """
    Extract function/method calls from an AST node.
    """

    calls = []

    for child in ast.walk(node):

        if isinstance(child, ast.Call):

            call_name = get_call_name(child)

            if call_name != "unknown":
                calls.append(call_name)

    # Remove duplicates while preserving order
    return list(dict.fromkeys(calls))


# --------------------------------------------------
# Extract function parameters
# --------------------------------------------------

def extract_parameters(node):
    """
    Extract parameters from a Python function.
    """

    parameters = []

    for arg in node.args.posonlyargs:
        parameters.append(arg.arg)

    for arg in node.args.args:
        parameters.append(arg.arg)

    for arg in node.args.kwonlyargs:
        parameters.append(arg.arg)

    if node.args.vararg:
        parameters.append(
            f"*{node.args.vararg.arg}"
        )

    if node.args.kwarg:
        parameters.append(
            f"**{node.args.kwarg.arg}"
        )

    return parameters


# --------------------------------------------------
# Analyze a Python function
# --------------------------------------------------

def analyze_function(node, file_path=""):
    """
    Extract information about a Python function.
    """

    parameters = extract_parameters(node)

    calls = extract_calls(node)

    # Return type if annotation exists
    return_type = ""

    if node.returns:

        if isinstance(node.returns, ast.Name):
            return_type = node.returns.id

        elif isinstance(node.returns, ast.Attribute):
            return_type = node.returns.attr

        else:
            return_type = ast.unparse(
                node.returns
            )

    # Decorators
    annotations = []

    for decorator in node.decorator_list:

        try:
            annotations.append(
                "@" + ast.unparse(decorator)
            )

        except Exception:
            pass

    # Include decorator line in chunk
    start_line = node.lineno

    if node.decorator_list:

        start_line = min(
            decorator.lineno
            for decorator in node.decorator_list
        )

    return CodeSymbol(
        type="function",
        name=node.name,
        parameters=parameters,
        calls=calls,
        file_path=file_path,
        language="python",
        start_line=start_line,
        end_line=node.end_lineno,
        return_type=return_type,
        annotations=annotations
    )


# --------------------------------------------------
# Extract module-level code
# --------------------------------------------------

def analyze_module_code(
    tree,
    code,
    file_path=""
):
    """
    Extract meaningful module-level code.

    This captures code that is not inside a function
    or class.

    Examples:

        from fastapi import FastAPI

        app = FastAPI()

        app.add_middleware(...)

    This is important because not every Python file
    contains functions.
    """

    lines = code.splitlines()

    module_nodes = []

    for node in tree.body:

        # Functions/classes are handled separately
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef
            )
        ):
            continue

        module_nodes.append(node)

    if not module_nodes:
        return None

    # Determine first and last line
    start_line = min(
        node.lineno
        for node in module_nodes
    )

    end_line = max(
        node.end_lineno
        for node in module_nodes
    )

    module_code = "\n".join(
        lines[start_line - 1:end_line]
    )

    if not module_code.strip():
        return None

    calls = []

    for node in module_nodes:

        calls.extend(
            extract_calls(node)
        )

    calls = list(
        dict.fromkeys(calls)
    )

    return CodeSymbol(
        type="module",
        name=file_path.split("\\")[-1].split("/")[-1],
        parameters=[],
        calls=calls,
        file_path=file_path,
        language="python",
        start_line=start_line,
        end_line=end_line,
        return_type="",
        annotations=[]
    )


# --------------------------------------------------
# Analyze Python source code
# --------------------------------------------------

def analyze_python_code(
    code,
    file_path=""
):
    """
    Analyze Python source code using AST.

    Extracts:

    - module-level code
    - functions
    - async functions
    """

    tree = ast.parse(code)

    symbols = []

    # --------------------------------------------------
    # Module-level code
    # --------------------------------------------------

    module_symbol = analyze_module_code(
        tree,
        code,
        file_path
    )

    if module_symbol:
        symbols.append(
            module_symbol
        )

    # --------------------------------------------------
    # Functions
    # --------------------------------------------------

    for node in ast.walk(tree):

        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef
            )
        ):

            function_info = analyze_function(
                node,
                file_path
            )

            symbols.append(
                function_info
            )

    return symbols


# --------------------------------------------------
# Test
# --------------------------------------------------

if __name__ == "__main__":

    code = """
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"message": "Hello"}

def login(username, password):

    user = get_user(username)

    if verify_password(password, user.password):
        return generate_token(user)

    return None
"""

    file_path = "app/main.py"

    symbols = analyze_python_code(
        code,
        file_path
    )

    print()
    print("=" * 60)
    print("PYTHON CODE ANALYSIS")
    print("=" * 60)

    print(
        f"Symbols found: {len(symbols)}"
    )

    for symbol in symbols:

        print()
        print("-" * 60)

        print(
            f"Type       : {symbol.type}"
        )

        print(
            f"Name       : {symbol.name}"
        )

        print(
            f"Language   : {symbol.language}"
        )

        print(
            f"File       : {symbol.file_path}"
        )

        print(
            f"Lines      : "
            f"{symbol.start_line} - "
            f"{symbol.end_line}"
        )

        print(
            f"Parameters : "
            f"{symbol.parameters}"
        )

        print(
            f"Calls      : "
            f"{symbol.calls}"
        )

        print(
            f"Annotations: "
            f"{symbol.annotations}"
        )