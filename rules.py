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
