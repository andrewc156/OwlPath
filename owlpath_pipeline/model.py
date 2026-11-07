"""Shared types. Expr is the internal form (every leaf an object); Logic is the output form."""
from dataclasses import dataclass, field
from typing import Any

DEFAULT_MIN_GRADE = "C"

# JSON-shaped dicts; kept as aliases rather than classes so they serialize directly.
#   Expr:  {"and": [Expr]} | {"or": [Expr]} | {"course": str, "minGrade"?: str} | {"external": str, "minGrade"?: str}
#   Logic: same, but an in-graph course with grade C is a plain str, and
#          {"course": X, "minGrade": "C"} is never written.
Expr = dict[str, Any]
Logic = str | dict[str, Any]



@dataclass
class ParseResult:
    """Parsed prerequisite prose. expr leaves are all {"course": ...}; build decides course vs external."""
    expr: Expr | None
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
