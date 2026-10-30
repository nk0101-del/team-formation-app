# 2026-10-26 20:07 KST
import pytest

from rules import (
    count_required_role_gap,
    check_team_constraints,
    format_result,
    missing_required_roles,
    validate_final_assignment,
    find_valid_assignment,
    explain_infeasibility,
    all_members_approved,
)


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


def test_missing_required_roles_lists_uncovered_role():
    members = [{"student_no": "A", "main_role": "테스터", "sub_roles": []}]
    assert missing_required_roles(members) == ["기획자", "웹 프로그래머"]


def test_missing_required_roles_empty_when_covered():
    members = [
        {"student_no": "A", "main_role": "기획자", "sub_roles": []},
        {"student_no": "B", "main_role": "웹 프로그래머", "sub_roles": []},
    ]
    assert missing_required_roles(members) == []


def _student(no, main, subs=None):
    return {"student_no": no, "main_role": main, "sub_roles": subs or []}


def test_valid_assignment_passes():
    teams = [
        [_student("1", "기획자"), _student("2", "웹 프로그래머")],
        [_student("3", "기획자"), _student("4", "웹 프로그래머")],
    ]
    ok, reason = validate_final_assignment(teams, {"1", "2", "3", "4"})
    assert ok is True and reason is None


def test_fails_when_student_missing():
    teams = [[_student("1", "기획자"), _student("2", "웹 프로그래머")]]
    ok, reason = validate_final_assignment(teams, {"1", "2", "3"})
    assert ok is False


def test_fails_when_team_size_out_of_range():
    teams = [[_student("1", "기획자")]]
    ok, reason = validate_final_assignment(teams, {"1"})
    assert ok is False


def test_fails_when_main_role_duplicated():
    teams = [[_student("1", "기획자"), _student("2", "기획자")]]
    ok, reason = validate_final_assignment(teams, {"1", "2"})
    assert ok is False


def test_fails_when_required_role_missing_with_named_reason():
    teams = [[_student("1", "테스터"), _student("2", "발표자")]]
    ok, reason = validate_final_assignment(teams, {"1", "2"})
    assert ok is False
    assert "기획자" in reason and "웹 프로그래머" in reason


def test_find_valid_assignment_places_remaining_students():
    existing_teams = [
        [_student("1", "기획자"), _student("4", "웹 프로그래머")],
        [_student("2", "기획자"), _student("5", "웹 프로그래머")],
        [_student("3", "기획자"), _student("6", "웹 프로그래머")],
    ]
    unassigned = [
        _student("7", "프론트엔드 디자이너", ["발표자"]),
        _student("8", "테스터", ["보고서 작성자", "발표자"]),
    ]
    result = find_valid_assignment(unassigned, existing_teams)
    assert result is not None
    all_nos = {s["student_no"] for team in result for s in team}
    assert all_nos == {"1", "2", "3", "4", "5", "6", "7", "8"}
    ok, _ = validate_final_assignment(result, all_nos)
    assert ok is True


def test_find_valid_assignment_returns_none_when_impossible():
    existing_teams = [
        [_student("1", "테스터"), _student("2", "테스터"), _student("3", "테스터"), _student("4", "테스터")]
    ]
    unassigned = [_student("5", "기획자")]
    assert find_valid_assignment(unassigned, existing_teams) is None


def test_explain_infeasibility_names_the_team_and_role():
    existing_teams = [
        [_student("1", "기획자"), _student("2", "웹 프로그래머")],
        [_student("6", "기획자"), _student("7", "웹 프로그래머")],
        [_student("3", "기획자"), _student("4", "발표자")],
    ]
    # 팀3은 기획자는 있지만 웹 프로그래머를 맡을 사람이 아예 없고, 팀이 없는 학생 중에도 없음
    unassigned = [_student("5", "보고서 작성자")]
    reason = explain_infeasibility(unassigned, existing_teams)
    assert reason == "팀3에 웹 프로그래머를 맡을 학생이 없음"


def test_explain_infeasibility_returns_none_when_no_clear_culprit():
    # 모든 팀에 필요한 역할을 맡을 후보가 있지만 자리 배치상 안 되는 경우
    existing_teams = [[_student("1", "기획자"), _student("2", "웹 프로그래머")]]
    unassigned = [_student("3", "테스터")]
    assert explain_infeasibility(unassigned, existing_teams) is None


def test_all_members_approved_requires_every_member_to_vote_yes():
    members = [{"id": 1}, {"id": 2}]
    assert all_members_approved(members, {1: "찬성", 2: "찬성"}) is True
    assert all_members_approved(members, {1: "찬성"}) is False  # 2번이 아직 투표 안 함
    assert all_members_approved(members, {1: "찬성", 2: "거부"}) is False


def test_all_members_approved_false_when_team_empty():
    # 빈 팀은 "전원 찬성"으로 셀 수 없음(모든 멤버가 찬성했다는 게 공허하게 참이 되는 것을 막음)
    assert all_members_approved([], {}) is False
