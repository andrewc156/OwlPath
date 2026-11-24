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
    r = parse_requirement("Dean waiver on file")
    assert r.expr is None and r.notes == ["Dean waiver on file"] and any("unrecognized" in w for w in r.warnings)


def test_oxford_list_inherits_operator():
    assert parse_requirement("CS 3305, CS 3503, and CS 3502").expr == {"and": [C("CS 3305"), C("CS 3503"), C("CS 3502")]}


def test_admission_phrase_with_and_inside_is_one_note():
    r = parse_requirement("Admission to the Data Science and Analytics, MS program")
    assert r.expr is None and r.notes == ["Admission to the Data Science and Analytics, MS program"] and r.warnings == []


def test_permission_of_program_coordinator_is_note():
    assert parse_requirement("Permission of MSDSA Program Coordinator").warnings == []


def test_course_and_permission_keeps_course_and_note():
    r = parse_requirement("STAT 7210 and permission of the instructor")
    assert r.expr == {"course": "STAT 7210"} and r.notes == ["permission of the instructor"]


def test_standing_and_candidacy_are_notes():
    for t in ("Graduate standing", "Ph.D. candidacy", "Consent of the dean"):
        r = parse_requirement(t)
        assert r.expr is None and r.notes == [t] and r.warnings == []


# --- KSU-wide wording (hold-clearing batch 1) ---

def test_grades_of_prefix_variants():
    for text in ['Grades of "B" or higher in PHYS 2212 and PHYS 2212L', 'Grade of "B" or higher in PHYS 2212 and PHYS 2212L',
                 "A grade of 'B' or higher in PHYS 2212 and PHYS 2212L", 'Earned grade of "B" or higher in PHYS 2212 and PHYS 2212L',
                 'Minimum grade of "B" or better in PHYS 2212 and PHYS 2212L']:
        r = parse_requirement(text)
        assert r.expr == {"and": [C("PHYS 2212", "B"), C("PHYS 2212L", "B")]} and r.warnings == [], text


def test_both_with_a_grade_of_suffix():
    r = parse_requirement('IT 1114 and CSE 1321, both with a grade of "B" or higher.')
    assert r.expr == {"and": [C("IT 1114", "B"), C("CSE 1321", "B")]} and r.warnings == []


def test_grade_prefix_with_comma_list_is_not_ambiguous():
    r = parse_requirement('(Grades of "B" or higher in ACCT 2101, ACCT 2102, ECON 2105, and ECON 2106) or ACCT 3100')
    assert r.expr == {"or": [{"and": [C("ACCT 2101", "B"), C("ACCT 2102", "B"), C("ECON 2105", "B"), C("ECON 2106", "B")]},
                             C("ACCT 3100")]}
    assert r.warnings == []


def test_ampersand_is_and():
    r = parse_requirement("MATH 2202 & ENGR 3801")
    assert r.expr == {"and": [C("MATH 2202"), C("ENGR 3801")]} and r.warnings == []


def test_placement_into_a_course_or_higher_is_one_note():
    r = parse_requirement("CHEM 1211 and (MATH 1111 or MATH 1113 or by placement to MATH 1113 or higher)")
    assert r.expr == {"and": [C("CHEM 1211"), {"or": [C("MATH 1111"), C("MATH 1113")]}]}
    assert r.notes == ["by placement to MATH 1113 or higher"] and r.warnings == []


def test_semicolon_separates_clauses_joined_by_and():
    r = parse_requirement("HIST 1111 or HIST 1112; ENGL 1102")
    assert r.expr == {"and": [{"or": [C("HIST 1111"), C("HIST 1112")]}, C("ENGL 1102")]} and r.warnings == []


def test_requirement_phrases_without_courses_are_notes():
    for phrase in ["Engineering Standing", "Engineering Standing Requirements", "a Coles Partner Student", "BBA Major",
                   "B.S. major", "Admission to teacher education", "an issued pre-service certificate",
                   "Must have earned at least 30 credit hours", "60 credit hours with a minimum GPA of 2.0",
                   "Departmental Approval", "Candidates must be admitted to a KSU BCOE program",
                   "Admission to Yearlong Clinical Experience", "endorsement program"]:
        r = parse_requirement(f"MATH 2202 and {phrase}")
        assert r.expr == C("MATH 2202") and r.notes == [phrase] and r.warnings == [], phrase


def test_unknown_prose_and_labels_still_warn():
    assert parse_requirement("MATH 2202 and two semesters of chemistry").warnings
    r = parse_requirement("Business Majors: ECON 2105; Non-business Majors: ECON 2100")
    assert r.warnings  # a per-major condition must reach a person, never become "both"


# --- batch 2 ---

def test_phrase_with_commas_stays_one_note():
    r = parse_requirement("EDUC 2130 and Elementary Education, B.S. major")
    assert r.expr == C("EDUC 2130") and r.notes == ["Elementary Education, B.S. major"] and r.warnings == []


def test_words_right_after_a_known_phrase_join_it():
    r = parse_requirement("Admission to Ed.D. Program in Educational Leadership")
    assert r.expr is None and r.notes == ["Admission to Ed.D. Program in Educational Leadership"] and r.warnings == []
    r = parse_requirement("HS 2200; HS major or Non-majors with permission of the department.")
    assert r.expr == C("HS 2200") and r.warnings == []


def test_admission_to_a_degree_is_a_note():
    r = parse_requirement("Admission to Elementary and Early Childhood Education, M.Ed.")
    assert r.expr is None and r.warnings == []


def test_trailing_minimum_grade_applies_to_the_group():
    r = parse_requirement("((IT 1114 and IT 1114L, minimum grade of 'B') or (CSE 1321 and CSE 1321L, minimum grade of 'B'))")
    assert r.expr == {"or": [{"and": [C("IT 1114", "B"), C("IT 1114L", "B")]}, {"and": [C("CSE 1321", "B"), C("CSE 1321L", "B")]}]}
    assert r.warnings == []


def test_parentheses_without_courses_or_operators_are_unwrapped():
    r = parse_requirement("GEOG 4405 and permission of the Geospatial Sciences (GSS) Internship Coordinator.")
    assert r.expr == C("GEOG 4405") and r.warnings == []
    r = parse_requirement("CE 3201 (or equivalent) or approval of instructor")
    assert r.expr == C("CE 3201") and r.warnings == []


def test_course_requirements_in_words_still_warn():
    assert parse_requirement("Any General Education DN core curriculum course").warnings
    assert parse_requirement("MATH 2202 and two semesters of chemistry").warnings


# --- batch 3 ---

def test_course_or_higher_is_a_note_not_a_requirement():
    r = parse_requirement("ENGL 1101 and (MATH 1001 or higher)")
    assert r.expr == C("ENGL 1101") and r.notes == ["MATH 1001 or higher"] and r.warnings == []


def test_with_minimum_grade_binds_to_its_course():
    r = parse_requirement('BLAW 2200 with minimum grade of "B" and (Admission to a Coles BBA Program or a Coles Partner Student)')
    assert r.expr == C("BLAW 2200", "B") and r.warnings == []


def test_concurrent_registration_alternative_is_a_note():
    r = parse_requirement("CE 3702 or concurrent registration")
    assert r.expr == C("CE 3702") and r.warnings == []


def test_mixed_and_or_is_fine_when_both_readings_agree():
    for text in ["Admission to Computer Science Ph.D. program, Computer Science MS Program, or Interdisciplinary Engineering Ph.D. program",
                 "60 credit hours with a minimum GPA of 2.0, and Admission to the Coles Program OR student in a Coles Partner Program",
                 "Admission to the Ed.D. Program and EDRS 8100 or its equivalent"]:
        assert parse_requirement(text).warnings == [], text
    assert parse_requirement("Admission to the Ed.D. Program and EDRS 8100 or its equivalent").expr == C("EDRS 8100")
    # a real difference between the readings still warns
    assert parse_requirement("MATH 1111 or MATH 1113 and CSE 1321").warnings


def test_name_fragments_in_a_group_without_courses_are_fine():
    r = parse_requirement("A declared major within the College of Science and Mathematics.")
    assert r.expr is None and r.warnings == []
    r = parse_requirement("COMM 2240 and (Journalism and Emerging Media, B.S., Media and Entertainment, B.S., or Public Relations, B.S. major.)")
    assert r.expr == C("COMM 2240") and r.warnings == []
    # longer unknown prose still warns, even beside a known phrase
    assert parse_requirement("Admission to the program and two semesters of chemistry").warnings


def test_degree_abbreviations_eligibility_and_varies_are_notes():
    for text in ["ART 1100 and ART 1150. This course is for Art, BFA or Digital Animation, BFA majors only",
                 "ECE 3000 and Eligibility to take GACE", "Varies by topic"]:
        assert parse_requirement(text).warnings == [], text
    assert parse_requirement("Varies by program: ARED 4650, or MUED 4650").warnings  # a per-program list still warns


# --- batch 4 ---

def test_missing_operator_is_fine_when_and_or_or_give_the_same_requirement():
    for text, expr in [("TPS Major. TPS 1600", C("TPS 1600")),
                       ("ART 3500; ART 2990 (may also be taken concurrently).", {"and": [C("ART 3500"), C("ART 2990")]}),
                       ("Acceptance into the Music Entertainment and Business program or completion of MUTC 3200", C("MUTC 3200"))]:
        r = parse_requirement(text)
        assert r.expr == expr and r.warnings == [], text
    assert parse_requirement("MATH 2202 MATH 2203").warnings  # two courses side by side: and or or matters


def test_inactive_markers_and_one_of_the_following_prefix():
    r = parse_requirement("One of the following courses: ENGL 2110, ENGL 2121 [Inactive], or ENGL 2300 [Inactive] .")
    assert r.expr == {"or": [C("ENGL 2110"), C("ENGL 2121"), C("ENGL 2300")]} and r.warnings == []


def test_recommended_clause_is_a_note():
    r = parse_requirement("BIOL 3300 and BIOL 3300L; Recommended - BIOL 3340")
    assert r.expr == {"and": [C("BIOL 3300"), C("BIOL 3300L")]} and r.notes == ["Recommended - BIOL 3340"] and r.warnings == []


def test_label_in_a_clause_without_courses_is_a_note():
    r = parse_requirement("JOUR 3330&nbsp;and COMM 2340; must be a declared major in the School of Communication & Media. "
                          "Non-Majors: Permission of the School required.")
    assert r.expr == {"and": [C("JOUR 3330"), C("COMM 2340")]} and r.warnings == []
    assert parse_requirement("Business Majors: MATH 1111; Non-business Majors: MATH 1101").warnings


def test_leading_and_after_semicolon_and_stray_quotes():
    r = parse_requirement("Must be a fully admitted music major; and permission of the instructor.")
    assert r.expr is None and r.warnings == []
    r = parse_requirement('MUTC 2200 or (MUTC 2100 with a "B" or higher") or (MUTC 1120 with a "B" or higher)')
    assert r.expr == {"or": [C("MUTC 2200"), C("MUTC 2100", "B"), C("MUTC 1120", "B")]} and r.warnings == []


def test_more_requirement_words():
    for text in ["DANC 3200 or Dance Major or Dance Minor", "ENGL 2110 and Completion of 90 hours",
                 "ARH 3990 and ENGL 1102; senior status.", "POLS 2280 and consent of the department chair"]:
        assert parse_requirement(text).warnings == [], text
