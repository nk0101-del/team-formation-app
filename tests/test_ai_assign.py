# 2026-10-26 20:07 KST
import time

from ai_assign import call_model_with_hard_timeout, assign_with_fallback


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
