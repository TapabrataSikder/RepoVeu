from dataclasses import dataclass, field


@dataclass
class CodeSymbol:
    type: str
    name: str
    parameters: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    file_path: str = ""
    language: str = ""
    start_line: int = 0
    end_line: int = 0
    class_name: str = ""
    return_type: str = ""
    visibility: str = ""
    annotations: list[str] = field(default_factory=list)