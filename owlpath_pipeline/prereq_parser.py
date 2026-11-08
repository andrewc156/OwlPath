"""Parse catalog prerequisite prose into an AND/OR tree (internal Expr form).

Examples it handles (2024-25 catalog wording):
  'A grade of "B" or higher in CSE 1321 and CSE 1321L'
  '(MATH 2345 or CSE 2300) and [(CSE 1322 and CSE 1322L each with a "B" or better), or MTRE 2610 ...]'
  'MATH 1113, or By Placement'        -> MATH 1113, note "By Placement"
Anything it can't place becomes a note plus a warning, so a human reviews it.
"""
import re
from dataclasses import dataclass

from .model import DEFAULT_MIN_GRADE, Expr, ParseResult

_TOKEN = re.compile(
    r"""
    (?P<GRADE_PREFIX>a\ grade\ of\ "(?P<pg>[A-F])"\ or\ (?:higher|better)\ in\b)
  | (?P<GRADE_SUFFIX>(?P<each>each\ )?with\ an?\ "(?P<sg>[A-F])"\ or\ (?:higher|better))
  | (?P<NOTE>by\ placement
      | (?:freshman|sophomore|junior|senior)\ standing
      | (?:by\ )?(?:instructor's|department's)(?:\ or\ department's)?\ permission
      | permission\ of\ (?:the\ )?(?:instructor|department))
  | (?P<COURSE>(?-i:[A-Z]{2,4}\ \d{4}[A-Z]?)\b)
  | (?P<AND>\band\b)
  | (?P<OR>\bor\b)
  | (?P<LP>[(\[])
  | (?P<RP>[)\]])
  | (?P<COMMA>,)
  | (?P<WS>\s+)
    """,
    re.IGNORECASE | re.VERBOSE,
)

_OPERAND_END = {"COURSE", "NOTE", "RP", "GRADE_SUFFIX"}
_OPERAND_START = {"COURSE", "NOTE", "LP", "GRADE_PREFIX"}


@dataclass
class _Tok:
    kind: str
    text: str
    grade: str | None = None
    each: bool = False


class _ParseError(Exception):
    pass


def _normalize(text: str) -> str:
    text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    text = text.replace(" ", " ")
    text = re.sub(r"(?<=[a-z])(?=[A-Z]{2,4}\s*\d{4})", " ", text)  # "inCSE 1321" -> "in CSE 1321"
    text = re.sub(r"\b([A-Z]{2,4})\s+(\d{4}[A-Z]?)\b", r"\1 \2", text)  # normalize spacing inside ids
    text = re.sub(r"\s+", " ", text).strip()
    return text.rstrip(".").strip()


def _tokenize(text: str, warnings: list[str]) -> list[_Tok]:
    toks: list[_Tok] = []
    buf = ""

    def flush() -> None:
        nonlocal buf
        leftover = buf.strip(" ,")
        if leftover:
            toks.append(_Tok("NOTE", leftover))
            warnings.append(f"unrecognized: {leftover}")
        buf = ""

    pos = 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            buf += text[pos]
            pos += 1
            continue
        kind = next(k for k in ("GRADE_PREFIX", "GRADE_SUFFIX", "NOTE", "COURSE", "AND", "OR", "LP", "RP", "COMMA", "WS")
                    if m.group(k) is not None)
        if kind == "WS" and buf:
            buf += m.group(0)  # keep unrecognized phrases together
        else:
            flush()
            if kind == "GRADE_PREFIX":
                toks.append(_Tok(kind, m.group(0), grade=m.group("pg").upper()))
            elif kind == "GRADE_SUFFIX":
                toks.append(_Tok(kind, m.group(0), grade=m.group("sg").upper(), each=bool(m.group("each"))))
            elif kind not in ("WS", "COMMA"):
                toks.append(_Tok(kind, m.group(0)))
        pos = m.end()
    flush()
    return toks


def _check_ambiguity(toks: list[_Tok], text: str, warnings: list[str]) -> None:
    stack: list[set[str]] = [set()]
    for t in toks:
        if t.kind == "LP":
            stack.append(set())
        elif t.kind == "RP" and len(stack) > 1:
            if {"AND", "OR"} <= stack.pop():
                warnings.append(f"ambiguous and/or precedence: {text}")
        elif t.kind in ("AND", "OR"):
            stack[-1].add(t.kind)
    if {"AND", "OR"} <= stack[0]:
        warnings.append(f"ambiguous and/or precedence: {text}")


def _insert_implicit_ops(toks: list[_Tok], warnings: list[str]) -> list[_Tok]:
    """Oxford-list rule: adjacent operands take the next operator at the same bracket depth."""
    out: list[_Tok] = []
    for i, t in enumerate(toks):
        if out and out[-1].kind in _OPERAND_END and t.kind in _OPERAND_START:
            depth, op = 0, None
            for later in toks[i:]:
                if later.kind == "LP":
                    depth += 1
                elif later.kind == "RP":
                    if depth == 0:
                        break
                    depth -= 1
                elif depth == 0 and later.kind in ("AND", "OR"):
                    op = later.kind
                    break
            if op is None:
                op = "AND"
                warnings.append(f"missing operator before '{t.text}', assumed and")
            out.append(_Tok(op, ""))
        out.append(t)
    return out


def _apply_grade(expr: Expr, grade: str) -> None:
    if "course" in expr:
        expr.setdefault("minGrade", grade)  # an inner, more specific grade wins
    for child in expr.get("and", expr.get("or", [])):
        _apply_grade(child, grade)


class _Parser:
    def __init__(self, toks: list[_Tok]):
        self.toks, self.i = toks, 0

    def peek(self, kind: str) -> bool:
        return self.i < len(self.toks) and self.toks[self.i].kind == kind

    def take(self) -> _Tok:
        t = self.toks[self.i]
        self.i += 1
        return t

    def each_suffix(self) -> _Tok | None:
        if self.peek("GRADE_SUFFIX") and self.toks[self.i].each:
            return self.take()
        return None

    def parse(self) -> Expr:
        expr = self.or_expr()
        if self.i != len(self.toks):
            raise _ParseError(f"unexpected '{self.toks[self.i].text}'")
        return expr

    def or_expr(self) -> Expr:
        items = [self.and_expr()]
        while self.peek("OR"):
            self.take()
            items.append(self.and_expr())
        if (s := self.each_suffix()) is not None:
            for it in items:
                _apply_grade(it, s.grade)
        return items[0] if len(items) == 1 else {"or": items}

    def and_expr(self) -> Expr:
        items = [self.unary()]
        while self.peek("AND"):
            self.take()
            items.append(self.unary())
        if len(items) > 1 and (s := self.each_suffix()) is not None:
            for it in items:
                _apply_grade(it, s.grade)
        return items[0] if len(items) == 1 else {"and": items}

    def unary(self) -> Expr:
        if self.peek("GRADE_PREFIX"):
            grade = self.take().grade
            expr = self.or_expr()  # the prefix covers the rest of this bracket level
            _apply_grade(expr, grade)
            return expr
        expr = self.primary()
        if self.peek("GRADE_SUFFIX") and not self.toks[self.i].each:
            _apply_grade(expr, self.take().grade)
        return expr

    def primary(self) -> Expr:
        if self.i >= len(self.toks):
            raise _ParseError("unexpected end")
        t = self.take()
        if t.kind == "COURSE":
            return {"course": t.text}
        if t.kind == "NOTE":
            return {"note": t.text}
        if t.kind == "LP":
            expr = self.or_expr()
            if not self.peek("RP"):
                raise _ParseError("unbalanced brackets")
            self.take()
            return expr
        raise _ParseError(f"unexpected '{t.text}'")


def _finish(expr: Expr, notes: list[str]) -> Expr | None:
    """Pull notes out, collapse single-child groups, flatten same-op nesting, drop default grades."""
    if "note" in expr:
        notes.append(expr["note"])
        return None
    if "course" in expr:
        if expr.get("minGrade") == DEFAULT_MIN_GRADE:
            del expr["minGrade"]
        return expr
    op = "and" if "and" in expr else "or"
    children: list[Expr] = []
    for child in expr[op]:
        done = _finish(child, notes)
        if done is None:
            continue
        children.extend(done[op] if op in done else [done])
    if not children:
        return None
    return children[0] if len(children) == 1 else {op: children}


def parse_requirement(text: str) -> ParseResult:
    warnings: list[str] = []
    clean = _normalize(text)
    toks = _tokenize(clean, warnings)
    if not toks:
        return ParseResult(None, [], warnings)
    _check_ambiguity(toks, clean, warnings)
    toks = _insert_implicit_ops(toks, warnings)
    try:
        expr = _Parser(toks).parse()
    except _ParseError as e:
        return ParseResult(None, [clean], warnings + [f"could not parse ({e}): {clean}"])
    notes: list[str] = []
    return ParseResult(_finish(expr, notes), notes, warnings)
