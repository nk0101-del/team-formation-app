# 2026-10-26 20:07 KST
import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

import requests

from rules import validate_final_assignment, find_valid_assignment


def build_prompt(teams: list[list[dict]], unassigned: list[dict]) -> str:
    return json.dumps({"teams": teams, "unassigned": unassigned}, ensure_ascii=False)


def call_model(model_name: str, prompt: str, api_key: str, http_post=requests.post) -> dict | None:
    try:
        response = http_post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
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
