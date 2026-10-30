# 2026-10-26 20:07 KST
import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

import requests

from rules import validate_final_assignment, find_valid_assignment


def build_prompt(teams: list[list[dict]], unassigned: list[dict]) -> str:
    data = json.dumps({"teams": teams, "unassigned": unassigned}, ensure_ascii=False)
    return (
        "당신은 팀 프로젝트 팀 편성을 돕는 배정 도우미입니다. "
        "teams는 이미 확정된 팀들이고, 각 팀의 기존 팀원은 절대 다른 팀으로 옮기면 안 됩니다. "
        "unassigned에 있는 학생들만 teams 중 하나(기존 팀 순서, 1번부터 시작하는 team_id)에 새로 배정하세요.\n\n"
        "규칙:\n"
        "1. 각 팀의 최종 인원은 2~4명이어야 합니다.\n"
        "2. 한 팀 안에서 같은 주 역할(main_role)을 가진 학생이 2명 이상이면 안 됩니다.\n"
        "3. 모든 팀에는 기획자 역할을 맡을 수 있는 학생과 웹 프로그래머 역할을 맡을 수 있는 학생이 "
        "서로 다른 사람으로 1명씩 있어야 합니다(주 역할 또는 보조 역할 모두 인정).\n\n"
        f"데이터(JSON):\n{data}\n\n"
        "응답은 다른 설명 없이 JSON 객체 하나만 출력하세요. "
        "키는 unassigned 학생의 student_no(문자열), 값은 그 학생을 배정할 team_id(1부터 시작하는 정수)입니다. "
        '예: {"student_no": team_id, ...}'
    )


def call_model(model_name: str, prompt: str, api_key: str, http_post=requests.post) -> dict | None:
    try:
        response = http_post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 4000,
                "reasoning": {"effort": "low"},
            },
        )
    except Exception:
        return None

    if response.status_code != 200:
        return None

    try:
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except Exception:
        return None

    if not parsed:
        return None
    return parsed


def call_model_with_hard_timeout(
    model_name: str, prompt: str, api_key: str, timeout: int = 120, http_post=requests.post
) -> dict | None:
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(call_model, model_name, prompt, api_key, http_post)
        try:
            return future.result(timeout=timeout)
        except FutureTimeoutError:
            return None


def assign_with_fallback(
    teams: list[list[dict]],
    unassigned: list[dict],
    api_key: str,
    models: list[str],
    expected_student_nos: set[str],
    on_status=lambda msg: None,
    http_post=requests.post,
) -> tuple[list[list[dict]] | None, list[dict]]:
    logs = []
    prompt = build_prompt(teams, unassigned)

    for attempt_no, model_name in enumerate(models, start=1):
        on_status(f"{attempt_no}차 모델 응답 대기 중")
        mapping = call_model_with_hard_timeout(model_name, prompt, api_key, http_post=http_post)

        if not mapping:
            logs.append({"model": model_name, "attempt_no": attempt_no, "status": "실패", "detail": "응답 없음/실패"})
            continue

        candidate = [list(team) for team in teams]
        try:
            for student in unassigned:
                team_id = mapping[student["student_no"]]
                candidate[team_id - 1].append(student)
        except (KeyError, IndexError):
            logs.append({"model": model_name, "attempt_no": attempt_no, "status": "실패", "detail": "배정안 형식 오류"})
            continue

        ok, reason = validate_final_assignment(candidate, expected_student_nos)
        if ok:
            logs.append({"model": model_name, "attempt_no": attempt_no, "status": "성공", "detail": ""})
            return candidate, logs
        logs.append({"model": model_name, "attempt_no": attempt_no, "status": "실패", "detail": reason})

    self_assigned = find_valid_assignment(unassigned, teams)
    return self_assigned, logs
