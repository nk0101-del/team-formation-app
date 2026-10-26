# 2026-10-26 20:07 KST
import pytest

from rules import count_required_role_gap, check_team_constraints, format_result


def test_gap_when_one_student_covers_both_required_roles_alone():
    members = [{"student_no": "A", "main_role": "기획자", "sub_roles": ["웹 프로그래머"]}]
    assert count_required_role_gap(members) == 1


def test_gap_zero_when_two_distinct_students_cover_roles():
    members = [
        {"student_no": "A", "main_role": "기획자", "sub_roles": []},
        {"student_no": "B", "main_role": "웹 프로그래머", "sub_roles": []},
    ]
    assert count_required_role_gap(members) == 0


def test_gap_two_when_no_one_covers_required_roles():
    members = [{"student_no": "A", "main_role": "테스터", "sub_roles": []}]
    assert count_required_role_gap(members) == 2


def test_blocked_when_team_full():
    members = [{"student_no": s, "main_role": "테스터", "sub_roles": []} for s in "ABCD"]
    applicant = {"student_no": "E", "main_role": "발표자", "sub_roles": []}
    ok, reason = check_team_constraints(members, applicant)
    assert ok is False and reason == "팀이 꽉 참"


def test_blocked_when_same_main_role_in_team():
    members = [{"student_no": "A", "main_role": "기획자", "sub_roles": []}]
    applicant = {"student_no": "B", "main_role": "기획자", "sub_roles": []}
    ok, reason = check_team_constraints(members, applicant)
    assert ok is False and reason == "같은 주 역할의 팀원이 있음"


def test_blocked_when_no_room_left_for_required_roles():
    members = [
        {"student_no": "A", "main_role": "테스터", "sub_roles": []},
        {"student_no": "B", "main_role": "발표자", "sub_roles": []},
    ]
    applicant = {"student_no": "C", "main_role": "보고서 작성자", "sub_roles": []}
    ok, reason = check_team_constraints(members, applicant)
    assert ok is False and reason == "필수 포함 역할 자리 부족"


def test_allowed_when_empty_team():
    ok, reason = check_team_constraints([], {"student_no": "A", "main_role": "기획자", "sub_roles": []})
    assert ok is True and reason is None


def test_format_result_with_detail():
    assert format_result("막힘", "같은 주 역할의 팀원이 있음") == "막힘: 같은 주 역할의 팀원이 있음"


def test_format_result_without_detail():
    assert format_result("승인") == "승인"


def test_format_result_rejects_invalid_prefix():
    with pytest.raises(AssertionError):
        format_result("완료")
