# 2026-10-26 20:07 KST
import time

from ai_assign import call_model_with_hard_timeout, assign_with_fallback, build_prompt, call_model


def test_build_prompt_explains_rules_and_response_format():
    teams = [[{"student_no": "1", "main_role": "기획자", "sub_roles": []}]]
    unassigned = [{"student_no": "7", "main_role": "테스터", "sub_roles": []}]
    prompt = build_prompt(teams, unassigned)
    assert "기획자" in prompt and "웹 프로그래머" in prompt  # 필수 포함 역할 규칙
    assert "2~4명" in prompt or "2-4" in prompt  # 팀 정원 규칙
    assert '"7"' in prompt  # 배정 대상 학생 데이터 포함
    assert "student_no" in prompt and "team_id" in prompt  # 기대하는 JSON 응답 형식 설명


def test_call_model_sets_max_tokens_and_low_reasoning_effort():
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.update(json)

        class R:
            status_code = 200

            def json(self):
                return {"choices": [{"message": {"content": '{"7": 1}'}}]}

        return R()

    call_model("some/model:free", "prompt", "key", http_post=fake_post)
    assert captured["max_tokens"] >= 2000
    assert captured["reasoning"]["effort"] == "low"


def test_hard_timeout_cuts_off_slow_streaming_response():
    def slow_http_post(*args, **kwargs):
        time.sleep(0.3)  # 응답이 시작은 됐지만 느리게 옴을 흉내

        class R:
            status_code = 200

            def json(self):
                return {"choices": [{"message": {"content": "{}"}}]}

        return R()

    result = call_model_with_hard_timeout(
        "model-x", "prompt", "key", timeout=0.1, http_post=slow_http_post
    )
    assert result is None  # 0.1초 제한을 넘겼으므로 강제 종료되어야 함


def test_hard_timeout_returns_promptly_even_if_worker_keeps_running():
    def hanging_http_post(*args, **kwargs):
        time.sleep(3)  # 1차 모델이 실제로 응답 안 하고 한참 걸리는 상황을 흉내

        class R:
            status_code = 200

            def json(self):
                return {"choices": [{"message": {"content": "{}"}}]}

        return R()

    start = time.monotonic()
    result = call_model_with_hard_timeout(
        "model-x", "prompt", "key", timeout=0.2, http_post=hanging_http_post
    )
    elapsed = time.monotonic() - start
    assert result is None
    # ThreadPoolExecutor를 with 블록으로 쓰면 __exit__에서 shutdown(wait=True)가
    # 걸려 워커가 끝날 때까지(3초) 기다리게 됨 — timeout(0.2초)을 넘기면 안 됨
    assert elapsed < 1.0


def _student(no, main, subs=None):
    return {"student_no": no, "main_role": main, "sub_roles": subs or []}


def test_falls_back_to_second_model_when_first_fails(monkeypatch):
    calls = []

    def fake_call(model_name, prompt, api_key, timeout=120, http_post=None):
        calls.append(model_name)
        if model_name == "model-1":
            return None  # 1차 실패
        return {"7": 1, "8": 2}  # 2차 성공

    monkeypatch.setattr("ai_assign.call_model_with_hard_timeout", fake_call)

    teams = [
        [_student("1", "기획자"), _student("4", "웹 프로그래머")],
        [_student("2", "기획자"), _student("5", "웹 프로그래머")],
    ]
    unassigned = [_student("7", "테스터"), _student("8", "발표자")]
    result, logs = assign_with_fallback(
        teams, unassigned, "key", ["model-1", "model-2", "model-3"], {"1", "2", "4", "5", "7", "8"}
    )
    assert calls == ["model-1", "model-2"]
    assert result is not None


def test_coerces_string_team_ids_from_model_response(monkeypatch):
    # LLM이 team_id를 문자열로 주는 경우가 흔함 — 숫자로 바꿔 받아들여야 함
    monkeypatch.setattr(
        "ai_assign.call_model_with_hard_timeout", lambda *a, **k: {"7": "1", "8": "2"}
    )
    teams = [
        [_student("1", "기획자"), _student("4", "웹 프로그래머")],
        [_student("2", "기획자"), _student("5", "웹 프로그래머")],
    ]
    unassigned = [_student("7", "테스터"), _student("8", "발표자")]
    result, logs = assign_with_fallback(
        teams, unassigned, "key", ["model-1", "model-2", "model-3"], {"1", "2", "4", "5", "7", "8"}
    )
    assert result is not None
    assert logs[0]["status"] == "성공"


def test_rejects_team_id_out_of_range_without_crashing(monkeypatch):
    # team_id가 0이나 범위 밖이면 조용히 마지막 팀으로 새지 않고 실패로 처리해야 함
    monkeypatch.setattr("ai_assign.call_model_with_hard_timeout", lambda *a, **k: {"7": 0})
    teams = [[_student("1", "기획자"), _student("4", "웹 프로그래머")]]
    unassigned = [_student("7", "테스터")]
    result, logs = assign_with_fallback(
        teams, unassigned, "key", ["model-1", "model-2", "model-3"], {"1", "4", "7"}
    )
    assert logs[0]["status"] == "실패"  # team_id=0을 그대로 썼다면 마지막 팀으로 조용히 샜을 것
    assert result is not None  # 자체 배정(전수 탐색)으로는 정상적으로 성공해야 함


def test_non_dict_model_response_is_treated_as_failure_not_crash(monkeypatch):
    # 모델이 JSON 배열이나 문자열을 내도 TypeError 없이 다음 모델로 넘어가야 함
    responses = iter([["not", "a", "dict"], "also not a dict", {"7": 1, "8": 2}])
    monkeypatch.setattr(
        "ai_assign.call_model_with_hard_timeout", lambda *a, **k: next(responses)
    )
    teams = [
        [_student("1", "기획자"), _student("4", "웹 프로그래머")],
        [_student("2", "기획자"), _student("5", "웹 프로그래머")],
    ]
    unassigned = [_student("7", "테스터"), _student("8", "발표자")]
    result, logs = assign_with_fallback(
        teams, unassigned, "key", ["model-1", "model-2", "model-3"], {"1", "2", "4", "5", "7", "8"}
    )
    assert result is not None
    assert logs[0]["status"] == "실패" and logs[1]["status"] == "실패"
    assert logs[2]["status"] == "성공"


def test_self_assigns_when_all_three_models_fail(monkeypatch):
    monkeypatch.setattr("ai_assign.call_model_with_hard_timeout", lambda *a, **k: None)
    teams = [
        [_student("1", "기획자"), _student("4", "웹 프로그래머")],
        [_student("2", "기획자"), _student("5", "웹 프로그래머")],
    ]
    unassigned = [_student("7", "테스터")]
    result, logs = assign_with_fallback(
        teams, unassigned, "key", ["model-1", "model-2", "model-3"], {"1", "2", "4", "5", "7"}
    )
    assert result is not None
    assert len(logs) == 3  # 3번 다 실패 기록
