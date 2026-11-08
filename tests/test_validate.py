from owlpath_pipeline.validate import validate_dataset


def course(id, prereqs=None, coreqs=None, groups=("major-required",)):
    return {
        "id": id, "title": "t", "credits": "3", "description": "d",
        "catalogYear": "2026-2027", "catalogUrl": "https://catalog.kennesaw.edu/",
        "groups": list(groups), "prereqs": prereqs, "coreqs": coreqs, "notes": [],
    }


def dataset(courses):
    return {"catalogYear": "2026-2027", "source": "test", "courses": courses}


def test_valid_dataset_has_no_errors():
    data = dataset([course("CSE 1321"), course("CSE 1321L"),
                    course("CSE 1322", prereqs={"and": [{"course": "CSE 1321", "minGrade": "B"}, "CSE 1321L"]})])
    assert validate_dataset(data) == []


def test_string_leaf_is_a_course_reference():
    data = dataset([course("CS 3305", prereqs={"or": ["MATH 2345", {"external": "CSE 2300"}]})])
    assert any("MATH 2345" in e and "unknown" in e for e in validate_dataset(data))


def test_object_leaf_with_default_grade_is_error():
    data = dataset([course("CSE 1321"), course("CSE 1322", prereqs={"course": "CSE 1321", "minGrade": "C"})])
    assert any("short form" in e for e in validate_dataset(data))


def test_dangling_course_reference_is_error():
    data = dataset([course("CSE 1322", prereqs="CSE 1321")])
    assert any("CSE 1321" in e and "unknown" in e for e in validate_dataset(data))


def test_external_reference_need_not_exist():
    data = dataset([course("CS 3305", prereqs={"or": [{"external": "MTRE 2610"}, {"external": "CPE 3000"}]})])
    assert validate_dataset(data) == []


def test_prereq_cycle_is_error():
    data = dataset([course("CS 1000", prereqs="CS 2000"), course("CS 2000", prereqs="CS 1000")])
    assert any("cycle" in e for e in validate_dataset(data))


def test_mutual_corequisites_are_allowed():
    data = dataset([course("CSE 1321", coreqs="CSE 1321L"), course("CSE 1321L", coreqs="CSE 1321")])
    assert validate_dataset(data) == []


def test_schema_violation_is_error():
    bad = course("CS 3305"); bad["groups"] = ["not-a-group"]
    assert validate_dataset(dataset([bad])) != []
