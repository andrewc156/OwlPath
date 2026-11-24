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
    (?P<GRADE_PREFIX>(?:an?\ )?(?:minimum\ )?(?:earned\ )?grades?\ of\ ["']?(?P<pg>[A-F])["']?\ or\ (?:higher|better)\ in\b)
  | (?P<GRADE_SUFFIX>(?P<each>(?:each|both|all)\ )?with\ (?:an?\ (?:(?:minimum\ )?grade\ of\ )?)?["'](?P<sg>[A-F])["']
      \ or\ (?:higher|better))
  | (?P<GRADE_MIN>(?:a\ )?minimum\ grade\ of\ ["'](?P<mg>[A-F])["'](?:\ or\ (?:higher|better))?)
  | (?P<NOTE>(?:by\ )?placement(?:\ (?:in)?to\ (?-i:[A-Z]{2,4}\ \d{4}[A-Z]?)(?:\ or\ higher)?)?
      | (?:admission\ to|acceptance\ into)\ .*?\ program\b
      | (?:freshman|sophomore|junior|senior|graduate)\ standing
      | (?:by\ )?(?:instructor's|department's)(?:\ or\ department's)?\ permission
      | (?:permission|consent|approval)\ of\ (?:the\ )?
        (?:instructor|department(?:\ chair)?|(?:[A-Z]{2,}\ )?program\ (?:director|coordinator)|advisor|dean)\b
      | ph\.d\.\ candidacy)
  | (?P<COURSE>(?-i:[A-Z]{2,4}\ \d{4}[A-Z]?)\b)
  | (?P<AND>\band\b|&)
  | (?P<OR>\bor\b)
  | (?P<LP>[(\[])
  | (?P<RP>[)\]])
  | (?P<COMMA>,)
  | (?P<WS>\s+)
    """,
    re.IGNORECASE | re.VERBOSE,
)

# A leftover phrase (no course id) that names one of these is a known kind of non-course requirement
# (admission, standing, major, hours, GPA, approval, certification): a note, shown and never blocking.
# Anything else, and any phrase ending in ":" (a per-major or per-program condition), still warns.
_REQUIREMENT_WORDS = re.compile(
    r"\b(?:admission|admitted|acceptance|accepted|standing|majors?|program|student|permission|consent|approval|approved"
    r"|credit\ hours|gpa|certificate|certification|endorsement|clinical|candidacy|enrolled|enrollment|placement"
    r"|equivalent|audition|portfolio|insurance|school\ of|degree|mba|ph\.?d|ed\.?\ ?[ds]|[bm]\.\ ?(?:ed|s|a|f\.?a)\b\.?)",
    re.IGNORECASE | re.VERBOSE)

_OPERAND_END = {"COURSE", "NOTE", "RP", "GRADE_SUFFIX"}
_OPERAND_START = {"COURSE", "NOTE", "LP", "GRADE_PREFIX"}


@dataclass
class _Tok:
    kind: str
    text: str
    grade: str | None = None
    each: bool = False
    known: bool = False  # a NOTE the parser recognized (placement, admission, standing, permission...)


class _ParseError(Exception):
    pass


def _normalize(text: str) -> str:
    text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    text = text.replace(" ", " ")
    text = re.sub(r"(?<=[a-z])(?=[A-Z]{2,4}\s*\d{4})", " ", text)  # "inCSE 1321" -> "in CSE 1321"
    text = re.sub(r"\b([A-Z]{2,4})\s+(\d{4}[A-Z]?)\b", r"\1 \2", text)  # normalize spacing inside ids
    text = re.sub(r"\(\s*or\s+(?:its\s+|an?\s+)?equivalent\s*\)", " or equivalent", text, flags=re.IGNORECASE)
    # "(GSS)", "(MBA/MSIS)": brackets around words with no course and no and/or group nothing; drop them.
    text = re.sub(r"\(([^()\[\]]*)\)",
                  lambda m: m.group(0) if re.search(r"[A-Z]{2,4} \d{4}|\b(?:and|or)\b", m.group(1), re.IGNORECASE)
                  else f" {m.group(1)} ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.rstrip(".").strip()


def _tokenize(text: str, warnings: list[str]) -> list[_Tok]:
    toks: list[_Tok] = []
    buf = ""

    def note(phrase: str, known: bool) -> None:
        # Words that sit right against another phrase, with no operator between, belong to it:
        # "Admission to Ed.D. Program" + "in Educational Leadership" is one requirement.
        if toks and toks[-1].kind == "NOTE":
            toks[-1].text += f" {phrase}"
            toks[-1].known = toks[-1].known or known
        else:
            toks.append(_Tok("NOTE", phrase, known=known))

    def flush() -> None:
        nonlocal buf
        leftover = buf.strip(" ,")
        if leftover:
            note(leftover, False)
        buf = ""

    pos = 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            buf += text[pos]
            pos += 1
            continue
        kind = next(k for k in ("GRADE_PREFIX", "GRADE_SUFFIX", "GRADE_MIN", "NOTE", "COURSE", "AND", "OR", "LP", "RP",
                                "COMMA", "WS") if m.group(k) is not None)
        if kind in ("WS", "COMMA") and buf:
            buf += m.group(0)  # keep an unrecognized phrase together, commas included
        else:
            flush()
            if kind == "GRADE_PREFIX":
                toks.append(_Tok(kind, m.group(0), grade=m.group("pg").upper()))
            elif kind == "GRADE_SUFFIX":
                toks.append(_Tok(kind, m.group(0), grade=m.group("sg").upper(), each=bool(m.group("each"))))
            elif kind == "GRADE_MIN":  # "A and B, minimum grade of 'C'" covers the whole group
                toks.append(_Tok("GRADE_SUFFIX", m.group(0), grade=m.group("mg").upper(), each=True))
            elif kind == "NOTE":
                note(m.group(0), True)
            elif kind not in ("WS", "COMMA"):
                toks.append(_Tok(kind, m.group(0)))
        pos = m.end()
    flush()
    # A phrase is fine as a note when the parser knows its kind, or it names a known requirement kind. Anything
    # else, and any phrase ending in ":" (a per-major or per-program condition), needs a person.
    for t in toks:
        if t.kind == "NOTE" and not t.known and (t.text.endswith(":") or not _REQUIREMENT_WORDS.search(t.text)):
            warnings.append(f"unrecognized: {t.text}")
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


def _clauses(text: str) -> list[str]:
    """Split on ";" outside brackets: KSU separates whole clauses that way, each one required."""
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == ";" and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return [p.strip(" ,") for p in parts if p.strip(" ,")]


def parse_requirement(text: str) -> ParseResult:
    warnings: list[str] = []
    clean = _normalize(text)
    clauses = _clauses(clean)
    if any(c.endswith(":") or re.search(r":\s", c) for c in clauses) and len(clauses) > 1:
        # "Business Majors: X; Non-business Majors: Y" is a choice by major, not "X and Y".
        return ParseResult(None, [clean], [f"could not parse (per-major clauses): {clean}"])
    exprs: list[Expr] = []
    for clause in clauses:
        toks = _tokenize(clause, warnings)
        if not toks:
            continue
        _check_ambiguity(toks, clause, warnings)
        toks = _insert_implicit_ops(toks, warnings)
        try:
            exprs.append(_Parser(toks).parse())
        except _ParseError as e:
            return ParseResult(None, [clean], warnings + [f"could not parse ({e}): {clean}"])
    if not exprs:
        return ParseResult(None, [], warnings)
    notes: list[str] = []
    expr = exprs[0] if len(exprs) == 1 else {"and": exprs}
    return ParseResult(_finish(expr, notes), notes, warnings)
