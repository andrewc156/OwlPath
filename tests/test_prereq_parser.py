from owlpath_pipeline.prereq_parser import parse_requirement


def C(i, g=None):
    return {"course": i, **({"minGrade": g} if g else {})}


def test_grade_prefix_applies_to_all_courses():
    r = parse_requirement('A grade of "B" or higher in CSE 1321 and CSE 1321L')
    assert r.expr == {"and": [C("CSE 1321", "B"), C("CSE 1321L", "B")]} and r.warnings == []


def test_concurrent_with_nested_or():
    r = parse_requirement("CSE 1322L and (MATH 1113 or MATH 1190 or MATH 1179 or MATH 2202)")
    assert r.expr == {"and": [C("CSE 1322L"), {"or": [C("MATH 1113"), C("MATH 1190"), C("MATH 1179"), C("MATH 2202")]}]}


def test_cs3305_mixed_brackets_each_with_and_with():
    r = parse_requirement('(MATH 2345 or CSE 2300) and [(CSE 1322 and CSE 1322L each with a "B" or better), '
                          'or MTRE 2610 with a "B" or better, or CPE 3000 with a "B" or better]')
    assert r.expr == {"and": [
        {"or": [C("MATH 2345"), C("CSE 2300")]},
        {"or": [{"and": [C("CSE 1322", "B"), C("CSE 1322L", "B")]}, C("MTRE 2610", "B"), C("CPE 3000", "B")]}]}
    assert r.warnings == []


def test_placement_alternative_becomes_note():
    r = parse_requirement("MATH 1113, or By Placement")
    assert r.expr == C("MATH 1113") and r.notes == ["By Placement"]


def test_standing_only_has_no_expr():
    r = parse_requirement("Senior standing")
    assert r.expr is None and r.notes == ["Senior standing"] and r.warnings == []


def test_permission_is_note():
    r = parse_requirement("CS 3305 or By Instructor's or Department's permission.")
    assert r.expr == C("CS 3305") and r.notes == ["By Instructor's or Department's permission"]


def test_glued_typo_and_curly_quotes_and_nbsp():
    r = parse_requirement("A grade of “B” or higher inCSE 1321")
    assert r.expr == C("CSE 1321", "B") and r.warnings == []


def test_or_higher_and_or_better_are_equivalent():
    assert parse_requirement('CS 3305 with a "B" or higher').expr == parse_requirement('CS 3305 with a "B" or better').expr


def test_unbracketed_mixed_and_or_warns():
    r = parse_requirement("MATH 1113 or MATH 1190 and CSE 1321")
    assert any("ambiguous" in w for w in r.warnings)


def test_unrecognized_text_warns_and_is_kept_as_note():
    r = parse_requirement("Approval of the dean")
    assert r.expr is None and r.notes == ["Approval of the dean"] and any("unrecognized" in w for w in r.warnings)


def test_oxford_list_inherits_operator():
    assert parse_requirement("CS 3305, CS 3503, and CS 3502").expr == {"and": [C("CS 3305"), C("CS 3503"), C("CS 3502")]}
