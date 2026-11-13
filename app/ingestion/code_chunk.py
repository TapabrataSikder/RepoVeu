from dataclasses import dataclass, field

@dataclass
class CodeChunk:
    content: str
    file_path: str
    language: str
    symbol_name: str = ""
    symbol_type: str = ""
    class_name: str = ""
    return_type: str = ""
    visibility: str = ""

    annotations: list[str] = field(
        default_factory=list
    )

    parameters: list[str] = field(
        default_factory=list
    )

    calls: list[str] = field(
        default_factory=list
    )

    start_line: int = 0

    end_line: int = 0