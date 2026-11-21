"""Dataset validation: JSON Schema, then references, short form and prerequisite cycles."""
import json
from collections.abc import Iterator

from jsonschema import Draft202012Validator

from . import config
from .model import DEFAULT_MIN_GRADE, Logic

_validator = Draft202012Validator(json.loads(config.SCHEMA_PATH.read_text()))


def _course_leaves(logic: Logic | None) -> Iterator[tuple[str, dict | None]]:
    """Yield (course id, object leaf or None for a string leaf) for every in-graph course leaf."""
    if logic is None:
        return
    if isinstance(logic, str):
        yield logic, None
    elif "and" in logic or "or" in logic:
        for child in logic.get("and", logic.get("or", [])):
            yield from _course_leaves(child)
    elif "course" in logic:
        yield logic["course"], logic


def _find_cycles(prereqs: dict[str, list[str]]) -> list[str]:
    errors, state, stack = [], {}, []  # state: 1 = on stack, 2 = done

    def visit(node: str) -> None:
        state[node] = 1
        stack.append(node)
        for nxt in prereqs.get(node, []):
            if state.get(nxt) == 1:
                cycle = stack[stack.index(nxt):] + [nxt]
                errors.append("cycle: " + " -> ".join(cycle))
            elif nxt not in state:
                visit(nxt)
        stack.pop()
        state[node] = 2

    for node in sorted(prereqs):
        if node not in state:
            visit(node)
    return errors


def validate_dataset(data: dict) -> list[str]:
    schema_errors = [
        f"schema: {'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
        for e in sorted(_validator.iter_errors(data), key=lambda e: list(map(str, e.absolute_path)))
    ]
    if schema_errors:
        return schema_errors

    errors: list[str] = []
    ids = {c["id"] for c in data["courses"]}
    prereq_graph: dict[str, list[str]] = {}
    for c in data["courses"]:
        for field in ("prereqs", "coreqs"):
            for ref, leaf in _course_leaves(c[field]):
                if ref not in ids:
                    errors.append(f"{c['id']}: unknown course reference {ref}")
                if leaf is not None and leaf.get("minGrade") == DEFAULT_MIN_GRADE:
                    errors.append(f"{c['id']}: object leaf {ref} with grade C must use short form")
        prereq_graph[c["id"]] = [ref for ref, _ in _course_leaves(c["prereqs"]) if ref in ids]
    errors += [f"choices: unknown course {ref}" for choice in data["choices"] for ref in choice if ref not in ids]
    errors += _check_less_common(data, ids)
    return errors + _find_cycles(prereq_graph)


def _required_refs(logic: Logic | None, under_or: bool = False) -> Iterator[str]:
    """Course ids that must be taken: every in-graph leaf not inside an `or`."""
    if logic is None:
        return
    if isinstance(logic, str):
        if not under_or:
            yield logic
    elif "and" in logic or "or" in logic:
        for child in logic.get("and", logic.get("or", [])):
            yield from _required_refs(child, under_or or "or" in logic)
    elif "course" in logic and not under_or:
        yield logic["course"]


def _check_less_common(data: dict, ids: set[str]) -> list[str]:
    """A hidden option must belong to an either/or with a shown option, and never be a required prerequisite,
    or hiding it would hide something a student has to take."""
    hidden = set(data.get("lessCommon", []))
    errors = [f"lessCommon: unknown course {h}" for h in sorted(hidden - ids)]
    for h in sorted(hidden & ids):
        if not any(h in choice and any(o not in hidden for o in choice) for choice in data["choices"]):
            errors.append(f"lessCommon: {h} needs an either/or requirement with a shown option")
    for c in data["courses"]:
        for field in ("prereqs", "coreqs"):
            for ref in _required_refs(c[field]):
                if ref in hidden:
                    errors.append(f"lessCommon: {ref} is a required {field[:-1]} of {c['id']}, so it can't be hidden")
    return errors
