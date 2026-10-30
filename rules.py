# 2026-10-26 20:07 KST
REQUIRED_ROLES = ["기획자", "웹 프로그래머"]
ALL_ROLES = ["기획자", "웹 프로그래머", "프론트엔드 디자이너", "테스터", "보고서 작성자", "발표자"]


def has_role(student: dict, role: str) -> bool:
    return role == student["main_role"] or role in student["sub_roles"]


def count_required_role_gap(members: list[dict]) -> int:
    pl_capable = [m for m in members if has_role(m, "기획자")]
    wp_capable = [m for m in members if has_role(m, "웹 프로그래머")]
    for pl in pl_capable:
        if any(m is not pl and m in wp_capable for m in members):
            return 0
    if pl_capable or wp_capable:
        return 1
    return 2


def check_team_constraints(members: list[dict], applicant: dict, capacity: int = 4) -> tuple[bool, str | None]:
    if len(members) >= capacity:
        return False, "팀이 꽉 참"
    if any(m["main_role"] == applicant["main_role"] for m in members):
        return False, "같은 주 역할의 팀원이 있음"
    remaining_slots = capacity - (len(members) + 1)
    gap_after = count_required_role_gap(members + [applicant])
    if remaining_slots < gap_after:
        return False, "필수 포함 역할 자리 부족"
    return True, None


RESULT_PREFIXES = {"승인", "대기", "거절", "막힘"}


def format_result(prefix: str, detail: str = "") -> str:
    assert prefix in RESULT_PREFIXES
    return f"{prefix}: {detail}" if detail else prefix


def missing_required_roles(members: list[dict]) -> list[str]:
    return [r for r in REQUIRED_ROLES if not any(has_role(m, r) for m in members)]


def validate_final_assignment(
    teams: list[list[dict]], expected_student_nos: set[str]
) -> tuple[bool, str | None]:
    all_nos = [m["student_no"] for team in teams for m in team]
    if len(all_nos) != len(set(all_nos)) or set(all_nos) != expected_student_nos:
        return False, "배정 대상이 빠지거나 중복됨"

    for i, team in enumerate(teams):
        if not (2 <= len(team) <= 4):
            return False, f"팀{i + 1}의 인원이 2~4명이 아님"
        main_roles = [m["main_role"] for m in team]
        if len(main_roles) != len(set(main_roles)):
            return False, f"팀{i + 1}에 주 역할이 겹치는 학생이 있음"
        if count_required_role_gap(team) > 0:
            missing = missing_required_roles(team)
            if missing:
                return False, f"팀{i + 1}에 {', '.join(missing)}를 맡을 학생이 없음"
            return False, f"팀{i + 1}에서 기획자와 웹 프로그래머를 서로 다른 학생이 맡지 못함"

    return True, None


def find_valid_assignment(
    unassigned: list[dict], existing_teams: list[list[dict]]
) -> list[list[dict]] | None:
    teams = [list(team) for team in existing_teams]
    expected = {m["student_no"] for team in existing_teams for m in team} | {
        s["student_no"] for s in unassigned
    }

    def backtrack(index: int) -> bool:
        if index == len(unassigned):
            ok, _ = validate_final_assignment(teams, expected)
            return ok
        student = unassigned[index]
        for team in teams:
            if len(team) >= 4:
                continue
            team.append(student)
            if backtrack(index + 1):
                return True
            team.pop()
        return False

    if backtrack(0):
        return teams
    return None


def explain_infeasibility(unassigned: list[dict], existing_teams: list[list[dict]]) -> str | None:
    for i, team in enumerate(existing_teams):
        for role in missing_required_roles(team):
            if not any(has_role(s, role) for s in unassigned):
                return f"팀{i + 1}에 {role}를 맡을 학생이 없음"
    return None
