<!-- 2026-10-26 20:07 KST -->

# 팀 편성 웹 앱 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `중간과제 공고.pdf`가 요구하는 팀 편성 Streamlit 앱(쉬움/중간/어려움 시나리오 전부 어려운 해결 기준)을 구현하고 배포한다.

**Architecture:** 규칙 판정(`rules.py`)과 AI 호출(`ai_assign.py`)을 DB/Streamlit 의존성 없는 순수 함수로 분리해 pytest로 먼저 검증하고, 그 위에 `db.py`(쿼리 전담) → `streamlit_app.py`(UI, 2.7절 key 그대로)를 쌓는다. 세션에는 로그인 주체만 두고 나머지는 매 렌더링마다 DB를 재조회한다.

**Tech Stack:** Python 3.13, Streamlit, SQLAlchemy + psycopg2-binary(Supabase/Postgres), bcrypt, requests, pytest, GitHub Actions(스케줄).

**Spec:** [docs/superpowers/specs/2026-10-26-team-formation-app-design.md](../specs/2026-10-26-team-formation-app-design.md) — 기능 요구사항의 원천은 항상 `중간과제 공고.pdf`이며, 이 계획이 공고와 어긋나면 공고가 우선한다.

## Global Constraints

- 모든 DB 테이블명은 `tf_`로 시작한다(6.3절 13번, -1점).
- `streamlit_app.py`의 Streamlit 요소 `key`는 공고 2.7절 표와 토씨 하나까지 일치시킨다(채점 방해 15번, -5점).
- 비밀번호는 bcrypt 해시로만 저장·비교한다. 평문 비교 금지(보안 10번, -2점).
- 학생 세션에서 관리자 전용 함수(명단 업로드, 마감, AI 배정, 확정)를 호출할 경로 자체가 없어야 한다(보안 11번, -3점).
- 로그인 실패(학번 없음/비밀번호 불일치)는 무조건 거부한다. 학번만으로 접근 금지(보안 12번, -3점).
- `OPENROUTER_API_KEY`, `DATABASE_URL`, `ADMIN_PASSWORD` 값은 로그나 화면에 절대 출력하지 않는다. 존재 확인은 "있음/없음"만 출력한다(보안 8번, -3점).
- `.env`는 `.gitignore`에 포함하고 절대 커밋하지 않는다. 매 커밋 전 `git status`로 확인한다(보안 7번, -3점).
- `openrouter/free` 자동 라우터는 쓰지 않는다. `OPENROUTER_MODEL_1/2/3` 세 모델을 직접 순서대로 호출한다(DB와 AI 14번, -2점).
- AI 모델 타임아웃은 "응답이 시작될 때까지"가 아니라 "요청 전체에 대해 120초"가 강제되어야 한다(4.3절 흔한 실수).
- `st.session_state`에는 로그인 주체(`student_no` 또는 `"admin"`)만 두고, 팀/지원/투표 상태는 매 렌더링마다 DB에서 새로 읽는다(스펙 §3).
- DB 엔진(연결)은 앱 전역에서 1회만 생성해 재사용한다(4.2절).
- 기획자·웹 프로그래머는 서로 다른 학생이 맡아야 하며, 한 학생이 둘 다 가능해도 자리 계산에서는 1자리로만 센다(3장).
- 새로 만드는 모든 파일(코드/문서/SQL)은 첫머리에 생성 일시 주석을 KST 기준(`TZ=Asia/Seoul date "+%Y-%m-%d %H:%M"`로 확인)으로 남긴다. 기존 파일 수정 시에는 붙이지 않는다.
- 커밋 시 Git 전역 설정을 변경하지 않는다. 저자 정보는 `GIT_AUTHOR_NAME="nk0101-del" GIT_AUTHOR_EMAIL="na3kyung@gmail.com" GIT_COMMITTER_NAME="nk0101-del" GIT_COMMITTER_EMAIL="na3kyung@gmail.com"` 환경변수로 커밋별 지정한다.

## Review Focus

- **재지원 차단**: 결과를 기다리는 지원이 있는 학생이 다른 팀에 또 지원하면 막혀야 한다(2.4절 "한 학생의 지원"). → Task 7에서 `apply_to_team`이 이 경우를 검사하는 테스트를 추가한다.
- **투표자 집합의 동적 변경**: 지원 대기 중 다른 지원자가 먼저 승인되어 팀원이 되면, 새로 들어온 팀원도 기존 대기 지원에 투표할 수 있어야 한다(2.4절). → Task 7에서 투표 가능자 목록을 투표 시점에 재계산하는 테스트를 추가한다.
- **마감 시 1인팀 해체**: 모집 마감 때 팀원이 1명뿐인 팀의 학생은 "팀이 없는 학생"이 되어야 한다(2.5절 2번). → Task 8에서 `close_recruiting`에 대한 테스트를 추가한다.
- **AI 타임아웃의 전체 대기시간 강제**: `requests`의 `timeout` 인자만 쓰면 응답이 느리게 스트리밍될 때 120초를 넘길 수 있다(4.3절 명시된 흔한 실수). → Task 5에서 `ThreadPoolExecutor.result(timeout=...)`로 전체 시간을 강제하는 테스트를 추가한다.
- **result 문구의 접두어 고정**: 모든 `result` 안내는 반드시 "승인"/"대기"/"거절"/"막힘" 중 하나로 시작해야 하고(2.7절), 채점은 이 첫 단어만 비교한다(6.2절 3번). → Task 2에서 `format_result`가 잘못된 접두어를 거부하는 테스트를 추가한다.

---

## Task 1: 저장소 뼈대와 테스트 환경

**Files:**
- Create: `requirements.txt`, `.gitignore`, `.env.example`
- Create (placeholder, 나중 태스크가 채움): `docs/PRD.md`, `docs/구현 계획.md`

**Interfaces:**
- Produces: `venv`가 활성화된 개발 환경, `pytest`가 설치되어 실행 가능한 상태.

- [ ] **Step 1: venv 생성 및 활성화 확인**

Run: `python -m venv venv` 후 PowerShell에서 `venv\Scripts\Activate.ps1`
Expected: 프롬프트 앞에 `(venv)` 표시

- [ ] **Step 2: `requirements.txt` 작성**

```
streamlit
sqlalchemy
psycopg2-binary
bcrypt
requests
python-dotenv
pytest
```

- [ ] **Step 3: 설치 및 pytest 동작 확인**

Run: `pip install -r requirements.txt` 후 `pytest --version`
Expected: pytest 버전 출력, 에러 없음

- [ ] **Step 4: `.gitignore` 작성**

`.env`, `venv/`, `__pycache__/`, `*.pyc`, `.streamlit/secrets.toml` 포함

- [ ] **Step 5: `.env.example` 작성 (값은 비워둠, 주석에 KST 생성 일시 포함)**

```
OPENROUTER_API_KEY=
OPENROUTER_MODEL_1=
OPENROUTER_MODEL_2=
OPENROUTER_MODEL_3=
DATABASE_URL=
ADMIN_PASSWORD=
```

- [ ] **Step 6: GitHub 비공개 저장소 생성 (실행 시 사용자 확인 필요)**

Run (사용자 승인 후): `gh repo create <저장소명> --private --source=. --remote=origin`
Expected: 저장소 생성, `origin` 리모트 등록

- [ ] **Step 7: 커밋**

```bash
git add requirements.txt .gitignore .env.example
GIT_AUTHOR_NAME="nk0101-del" GIT_AUTHOR_EMAIL="na3kyung@gmail.com" GIT_COMMITTER_NAME="nk0101-del" GIT_COMMITTER_EMAIL="na3kyung@gmail.com" git commit -m "chore: 프로젝트 뼈대 추가"
```

---

## Task 2: 규칙 엔진 1부 — 필수 포함 역할 자리 계산과 지원 가능 판정

**Files:**
- Create: `rules.py`
- Test: `tests/test_rules.py`

**Interfaces:**
- Produces:
  - `REQUIRED_ROLES: list[str]` = `["기획자", "웹 프로그래머"]`
  - `has_role(student: dict, role: str) -> bool`
  - `count_required_role_gap(members: list[dict]) -> int`
  - `check_team_constraints(members: list[dict], applicant: dict, capacity: int = 4) -> tuple[bool, str | None]`
  - `RESULT_PREFIXES: set[str]` = `{"승인", "대기", "거절", "막힘"}`
  - `format_result(prefix: str, detail: str = "") -> str`
- Student dict 모양: `{"student_no": str, "main_role": str, "sub_roles": list[str]}`

- [ ] **Step 1: `count_required_role_gap` 실패 테스트 작성**

```python
# tests/test_rules.py
from rules import count_required_role_gap

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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_rules.py -v`
Expected: FAIL (`rules` 모듈/함수 없음)

- [ ] **Step 3: `has_role`, `count_required_role_gap` 구현**

`has_role`은 `role == student["main_role"] or role in student["sub_roles"]`.

`count_required_role_gap`은 필수 역할 2개(기획자, 웹 프로그래머)에 대해 **서로 다른 학생**을 배정할 수 있는 최대 매칭 크기를 구하고 `2 - 매칭크기`를 반환한다(한 학생이 두 역할 다 가능해도 1자리로만 셈). 멤버 수가 최대 4명이므로 아래처럼 완전탐색으로 충분하다:

```python
def count_required_role_gap(members):
    pl_capable = [m for m in members if has_role(m, "기획자")]
    wp_capable = [m for m in members if has_role(m, "웹 프로그래머")]
    for pl in pl_capable:
        if any(m is not pl and m in wp_capable for m in members):
            return 0
    if pl_capable or wp_capable:
        return 1
    return 2
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_rules.py -v`
Expected: 3개 PASS

- [ ] **Step 5: `check_team_constraints` 실패 테스트 작성**

```python
from rules import check_team_constraints

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
    # 테스터, 발표자 2명 있는 팀에 보고서 작성자가 지원 → 남는 자리 1개로 필수 역할 2개 못 채움
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
```

- [ ] **Step 6: 테스트 실패 확인**

Run: `pytest tests/test_rules.py -v`
Expected: FAIL (`check_team_constraints` 없음)

- [ ] **Step 7: `check_team_constraints(members, applicant, capacity=4)` 구현**

검사 순서: (1) `len(members) >= capacity`면 `(False, "팀이 꽉 참")`. (2) `applicant["main_role"]`이 기존 멤버 중 하나의 `main_role`과 같으면 `(False, "같은 주 역할의 팀원이 있음")`. (3) `capacity - (len(members)+1) < count_required_role_gap(members + [applicant])`이면 `(False, "필수 포함 역할 자리 부족")`. (4) 그 외 `(True, None)`.

- [ ] **Step 8: 테스트 통과 확인**

Run: `pytest tests/test_rules.py -v`
Expected: 전체 PASS

- [ ] **Step 9: `format_result` 테스트 작성 및 구현**

```python
import pytest
from rules import format_result

def test_format_result_with_detail():
    assert format_result("막힘", "같은 주 역할의 팀원이 있음") == "막힘: 같은 주 역할의 팀원이 있음"

def test_format_result_without_detail():
    assert format_result("승인") == "승인"

def test_format_result_rejects_invalid_prefix():
    with pytest.raises(AssertionError):
        format_result("완료")
```

구현:
```python
RESULT_PREFIXES = {"승인", "대기", "거절", "막힘"}

def format_result(prefix, detail=""):
    assert prefix in RESULT_PREFIXES
    return f"{prefix}: {detail}" if detail else prefix
```

- [ ] **Step 10: 전체 테스트 통과 확인 후 커밋**

Run: `pytest tests/test_rules.py -v` → 전체 PASS

```bash
git add rules.py tests/test_rules.py
GIT_AUTHOR_NAME="nk0101-del" GIT_AUTHOR_EMAIL="na3kyung@gmail.com" GIT_COMMITTER_NAME="nk0101-del" GIT_COMMITTER_EMAIL="na3kyung@gmail.com" git commit -m "feat: 필수 포함 역할 계산과 지원 가능 판정 구현"
```

---

## Task 3: 규칙 엔진 2부 — 최종 배정 검증과 전수 탐색 배정

**Files:**
- Modify: `rules.py`
- Test: `tests/test_rules.py`

**Interfaces:**
- Consumes: Task 2의 `has_role`, `count_required_role_gap`
- Produces:
  - `missing_required_roles(members: list[dict]) -> list[str]`
  - `validate_final_assignment(teams: list[list[dict]], expected_student_nos: set[str]) -> tuple[bool, str | None]`
  - `find_valid_assignment(unassigned: list[dict], existing_teams: list[list[dict]]) -> list[list[dict]] | None`

- [ ] **Step 1: `missing_required_roles` 테스트 작성 및 구현**

```python
from rules import missing_required_roles

def test_missing_required_roles_lists_uncovered_role():
    members = [{"student_no": "A", "main_role": "테스터", "sub_roles": []}]
    assert missing_required_roles(members) == ["기획자", "웹 프로그래머"]

def test_missing_required_roles_empty_when_covered():
    members = [
        {"student_no": "A", "main_role": "기획자", "sub_roles": []},
        {"student_no": "B", "main_role": "웹 프로그래머", "sub_roles": []},
    ]
    assert missing_required_roles(members) == []
```

구현: `[r for r in REQUIRED_ROLES if not any(has_role(m, r) for m in members)]`

- [ ] **Step 2: 테스트 통과 확인**

Run: `pytest tests/test_rules.py -v` → PASS

- [ ] **Step 3: `validate_final_assignment` 실패 테스트 작성 (2.5절 4항 5가지 검사)**

```python
from rules import validate_final_assignment

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
    teams = [[_student("1", "기획자")]]  # 1명뿐
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
```

- [ ] **Step 4: 테스트 실패 확인 후 구현**

`validate_final_assignment(teams, expected_student_nos)`:
1. 전체 학번 집합이 중복 없이 `expected_student_nos`와 정확히 같은지 확인 → 다르면 `(False, "배정 대상이 빠지거나 중복됨")`
2. 각 팀 `len(team)`이 2~4 범위인지 확인 → 아니면 `(False, f"팀{i+1}의 인원이 2~4명이 아님")`
3. 각 팀 내 `main_role` 중복 확인 → 있으면 `(False, f"팀{i+1}에 주 역할이 겹치는 학생이 있음")`
4. 각 팀 `count_required_role_gap(team) > 0`이면 `missing_required_roles(team)`으로 구체적 역할 이름을 넣어 `(False, f"팀{i+1}에 {', '.join(missing)}를 맡을 학생이 없음")` (missing이 비어있으면 `(False, f"팀{i+1}에서 기획자와 웹 프로그래머를 서로 다른 학생이 맡지 못함")`)
5. 전부 통과하면 `(True, None)`

- [ ] **Step 5: 테스트 통과 확인**

Run: `pytest tests/test_rules.py -v` → PASS

- [ ] **Step 6: `find_valid_assignment` 테스트 작성 (부록 1 6단계 기반)**

```python
from rules import find_valid_assignment

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
    existing_teams = [[_student("1", "테스터"), _student("2", "테스터"), _student("3", "테스터"), _student("4", "테스터")]]
    unassigned = [_student("5", "기획자")]
    assert find_valid_assignment(unassigned, existing_teams) is None
```

- [ ] **Step 7: 테스트 실패 확인 후 구현**

`find_valid_assignment(unassigned, existing_teams)`은 `unassigned`를 하나씩 기존 팀에 배치하는 백트래킹: 각 학생마다 각 팀(용량 4 이하인 팀)에 넣어보고 재귀, 막다른 골목이면 되돌림(기존 팀원은 절대 옮기지 않음 — 추가만 함). `unassigned`를 전부 배치한 뒤 `validate_final_assignment`로 최종 확인하고 통과하면 그 배치를, 전부 실패하면 `None`을 반환. 6.2절 9번에 따라 배정 대상이 8명을 넘지 않으므로 가지치기 없는 단순 백트래킹으로 충분하다(가지치기로 "남은 unassigned 수보다 팀들의 남은 total capacity가 작으면 즉시 포기" 정도만 추가해도 됨).

- [ ] **Step 8: 테스트 통과 확인 후 커밋**

Run: `pytest tests/test_rules.py -v` → 전체 PASS

```bash
git add rules.py tests/test_rules.py
GIT_AUTHOR_NAME="nk0101-del" GIT_AUTHOR_EMAIL="na3kyung@gmail.com" GIT_COMMITTER_NAME="nk0101-del" GIT_COMMITTER_EMAIL="na3kyung@gmail.com" git commit -m "feat: 최종 배정 검증과 전수 탐색 배정 구현"
```

---

## Task 4: 비밀번호 해시 (`auth.py`)

**Files:**
- Create: `auth.py`
- Test: `tests/test_auth.py`

**Interfaces:**
- Produces:
  - `hash_password(password: str) -> str`
  - `verify_password(password: str, hashed: str) -> bool`
  - `is_admin_login(student_no: str) -> bool`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_auth.py
from auth import hash_password, verify_password, is_admin_login

def test_hash_is_not_plaintext():
    hashed = hash_password("1234")
    assert hashed != "1234"

def test_verify_correct_password():
    hashed = hash_password("1234")
    assert verify_password("1234", hashed) is True

def test_verify_wrong_password_rejected():
    hashed = hash_password("1234")
    assert verify_password("wrong", hashed) is False

def test_is_admin_login():
    assert is_admin_login("admin") is True
    assert is_admin_login("2026301") is False
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_auth.py -v`
Expected: FAIL (`auth` 모듈 없음)

- [ ] **Step 3: `bcrypt`로 구현**

```python
import bcrypt

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def is_admin_login(student_no: str) -> bool:
    return student_no == "admin"
```

- [ ] **Step 4: 테스트 통과 확인 후 커밋**

Run: `pytest tests/test_auth.py -v` → 전체 PASS

```bash
git add auth.py tests/test_auth.py
GIT_AUTHOR_NAME="nk0101-del" GIT_AUTHOR_EMAIL="na3kyung@gmail.com" GIT_COMMITTER_NAME="nk0101-del" GIT_COMMITTER_EMAIL="na3kyung@gmail.com" git commit -m "feat: bcrypt 비밀번호 해시/검증 구현"
```

---

## Task 5: AI 배정 호출과 폴백 (`ai_assign.py`)

**Files:**
- Create: `ai_assign.py`
- Test: `tests/test_ai_assign.py`

**Interfaces:**
- Consumes: Task 3의 `validate_final_assignment`, `find_valid_assignment`
- Produces:
  - `build_prompt(teams: list[list[dict]], unassigned: list[dict]) -> str`
  - `call_model(model_name: str, prompt: str, api_key: str, http_post=requests.post) -> dict | None` (성공 시 `{student_no: team_id}`, 실패 시 `None`)
  - `call_model_with_hard_timeout(model_name, prompt, api_key, timeout: int = 120, http_post=requests.post) -> dict | None`
  - `assign_with_fallback(teams, unassigned, api_key: str, models: list[str], expected_student_nos: set[str], on_status=lambda msg: None, http_post=requests.post) -> tuple[list[list[dict]] | None, list[dict]]` — 반환값 `(최종 배정 또는 None, 시도 로그 리스트)`. 로그 각 항목: `{"model": str, "attempt_no": int, "status": "성공"|"실패", "detail": str}`

이 모듈은 DB를 모른다 — `teams`/`unassigned`는 Task 3와 같은 Student dict 리스트로 받고, `assign_with_fallback`이 반환하는 최종 배정도 같은 모양(`list[list[dict]]`)이다. 3차까지 실패하면 내부에서 `find_valid_assignment`를 호출해 자체 배정한다.

- [ ] **Step 1: `call_model_with_hard_timeout`이 전체 대기시간을 강제하는 실패 테스트 작성**

```python
# tests/test_ai_assign.py
import time
from ai_assign import call_model_with_hard_timeout

def test_hard_timeout_cuts_off_slow_streaming_response():
    def slow_http_post(*args, **kwargs):
        time.sleep(0.3)  # 응답이 시작은 됐지만 느리게 옴을 흉내
        class R:
            status_code = 200
            def json(self): return {"choices": [{"message": {"content": "{}"}}]}
        return R()
    result = call_model_with_hard_timeout(
        "model-x", "prompt", "key", timeout=0.1, http_post=slow_http_post
    )
    assert result is None  # 0.1초 제한을 넘겼으므로 강제 종료되어야 함
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_ai_assign.py -v`
Expected: FAIL (모듈 없음)

- [ ] **Step 3: `build_prompt`, `call_model`, `call_model_with_hard_timeout` 구현**

`call_model`은 `http_post`로 OpenRouter 채팅 완료 API를 호출하고, 응답 JSON을 파싱해 `{student_no: team_id}` 딕셔너리를 반환한다. 429/비정상 상태코드/빈 콘텐츠/JSON 파싱 실패 시 `None`을 반환한다. `call_model_with_hard_timeout`은 `concurrent.futures.ThreadPoolExecutor(max_workers=1)`로 `call_model`을 제출하고 `future.result(timeout=timeout)`을 기다리며, `TimeoutError` 발생 시 `None`을 반환한다(이것이 "응답 시작까지만 재는" 흔한 실수를 피하는 지점).

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_ai_assign.py -v` → PASS

- [ ] **Step 5: `assign_with_fallback` 테스트 작성 (폴백 + 자체 배정)**

```python
from ai_assign import assign_with_fallback

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

    teams = [[_student("1", "기획자"), _student("4", "웹 프로그래머")],
             [_student("2", "기획자"), _student("5", "웹 프로그래머")]]
    unassigned = [_student("7", "테스터"), _student("8", "발표자")]
    result, logs = assign_with_fallback(
        teams, unassigned, "key", ["model-1", "model-2", "model-3"], {"1","2","4","5","7","8"}
    )
    assert calls == ["model-1", "model-2"]
    assert result is not None

def test_self_assigns_when_all_three_models_fail(monkeypatch):
    monkeypatch.setattr("ai_assign.call_model_with_hard_timeout", lambda *a, **k: None)
    teams = [[_student("1", "기획자"), _student("4", "웹 프로그래머")]]
    unassigned = [_student("7", "테스터", ["기획자"])]
    # 팀 하나뿐이면 4명 꽉 찰 수 있으니 2팀으로 구성해 자리 확보
    teams = [[_student("1", "기획자")], [_student("4", "웹 프로그래머")]]
    result, logs = assign_with_fallback(
        teams, unassigned, "key", ["model-1", "model-2", "model-3"], {"1","4","7"}
    )
    assert result is not None
    assert len(logs) == 3  # 3번 다 실패 기록
```

- [ ] **Step 6: 테스트 실패 확인 후 구현**

`assign_with_fallback`: `models` 리스트를 순회하며 `on_status(f"{i+1}차 모델 응답 대기 중")` 호출 → `call_model_with_hard_timeout` 호출 → 응답을 팀 구조에 반영한 뒤 `validate_final_assignment(new_teams, expected_student_nos)`로 검사 → 통과하면 `(new_teams, logs)` 반환, 실패/빈 응답이면 로그에 기록하고 다음 모델로. 세 모델 다 실패하면 `find_valid_assignment(unassigned, teams)` 호출, 성공하면 그 결과를, 실패하면 `(None, logs)`를 반환.

- [ ] **Step 7: 테스트 통과 확인 후 커밋**

Run: `pytest tests/test_ai_assign.py -v` → 전체 PASS

```bash
git add ai_assign.py tests/test_ai_assign.py
GIT_AUTHOR_NAME="nk0101-del" GIT_AUTHOR_EMAIL="na3kyung@gmail.com" GIT_COMMITTER_NAME="nk0101-del" GIT_COMMITTER_EMAIL="na3kyung@gmail.com" git commit -m "feat: OpenRouter 폴백과 전체 타임아웃 강제 구현"
```

---

## Task 6: DB 스키마와 읽기/초기화 레이어 (`schema.sql` + `db.py`)

> **사용자 작업 필요**: 이 태스크를 시작하기 전에 Supabase 프로젝트를 만들고 `.env`의 `DATABASE_URL`을 채워야 한다. 계정 생성이 필요한 작업이라 Claude가 대신 할 수 없다. 준비되면 알려줄 것.

**Files:**
- Create: `schema.sql`
- Create: `db.py`

**Interfaces:**
- Consumes: Task 4의 `hash_password`, `verify_password`
- Produces:
  - `get_engine() -> Engine` (`st.cache_resource`는 `streamlit_app.py`에서 감쌈, `db.py`는 평범한 `create_engine` 반환)
  - `bootstrap_admin(engine, admin_password: str) -> None`
  - `upload_roster(engine, students: list[dict], team_count: int) -> None` — `students`는 CSV를 파싱한 `{"student_no","name","main_role","sub_roles"}` 리스트
  - `get_student(engine, student_no: str) -> dict | None`
  - `verify_login(engine, student_no: str, password: str) -> dict | None`
  - `get_teams(engine) -> list[list[dict]]` — 인덱스 `i`가 "팀{i+1}"에 대응한다(`team_id = i+1`, 팀은 생성 순서대로 연속 번호이고 삭제되지 않으므로 이 대응이 항상 성립). 각 항목은 그 팀의 현재 Student dict 리스트(`rules.py`/`ai_assign.py`가 쓰는 모양과 동일, wrapper 없음)
  - `get_unassigned_students(engine) -> list[Student]`
  - `is_recruiting_closed(engine) -> bool`

- [ ] **Step 1: `schema.sql` 작성**

```sql
create table tf_students (
    id serial primary key,
    student_no text unique not null,
    name text not null,
    main_role text check (main_role in ('기획자','웹 프로그래머','프론트엔드 디자이너','테스터','보고서 작성자','발표자')),
    password_hash text not null,
    is_admin boolean not null default false
);

create table tf_student_sub_roles (
    student_id integer references tf_students(id),
    role text check (role in ('기획자','웹 프로그래머','프론트엔드 디자이너','테스터','보고서 작성자','발표자'))
);

create table tf_teams (
    id serial primary key,
    name text unique not null
);

create table tf_members (
    team_id integer references tf_teams(id),
    slot_no integer check (slot_no between 1 and 4),
    student_id integer unique references tf_students(id),
    primary key (team_id, slot_no)
);

create table tf_applications (
    id serial primary key,
    team_id integer references tf_teams(id),
    student_id integer references tf_students(id),
    status text check (status in ('대기','승인','거절')),
    reason text,
    created_at timestamptz not null default now()
);

create table tf_votes (
    application_id integer references tf_applications(id),
    voter_id integer references tf_students(id),
    vote text check (vote in ('찬성','거부')),
    primary key (application_id, voter_id)
);

create table tf_settings (
    key text primary key,
    value text
);

create table tf_ai_logs (
    id serial primary key,
    batch_id text,
    model_name text,
    attempt_no integer,
    status text,
    raw_response text,
    created_at timestamptz not null default now()
);
```

- [ ] **Step 2: Supabase SQL 편집기에서 `schema.sql` 실행 (사용자 확인 후 Claude가 `psql`/Python 스크립트로 대행 가능)**

Run: `.env`의 `DATABASE_URL`로 접속해 `schema.sql` 적용
Expected: 7개 `tf_` 테이블 생성 확인(`\dt tf_*` 또는 Supabase Table Editor)

- [ ] **Step 3: `get_engine`, `bootstrap_admin` 구현 및 수동 검증**

`bootstrap_admin`은 `student_no="admin"`인 행이 없으면 생성, 있으면 `password_hash`를 `hash_password(admin_password)`로 갱신(2.1절 "명단을 다시 올려도 관리자 계정은 남김" 반영 — admin 행은 `upload_roster`가 지우지 않는다).

Run: 간단한 스크립트로 `bootstrap_admin(get_engine(), "test1234")` 실행 후 Supabase Table Editor에서 `tf_students`에 `admin` 행이 생겼는지 확인
Expected: `is_admin=true`인 행 1개, `password_hash`가 `test1234`와 다른 문자열

- [ ] **Step 4: `upload_roster` 구현 및 수동 검증**

`tf_applications`, `tf_votes`, `tf_members`를 비우고(admin 행 유지), `students` 리스트로 `tf_students`/`tf_student_sub_roles`를 다시 채운 뒤, `team_count`만큼 `tf_teams`(이름 "팀1","팀2",...)를 빈 상태로 만든다. 비밀번호는 전부 `hash_password("1234")`.

Run: `어려움.csv`를 파싱해 `upload_roster(engine, students, 4)` 호출 후 Supabase에서 학생 16명 + 팀 4개 확인
Expected: `tf_students` 16+1(admin)행, `tf_teams` 4행, `tf_members` 0행

- [ ] **Step 5: `get_student`, `verify_login`, `get_teams`, `get_unassigned_students`, `is_recruiting_closed` 구현 및 수동 검증**

`verify_login`은 `get_student`로 조회 후 `verify_password`로 비교, 실패 시 `None`(보안 12번 — 학번만으로 통과 금지).

Run: `verify_login(engine, "2026301", "1234")`와 `verify_login(engine, "2026301", "wrong")`를 각각 호출
Expected: 전자는 학생 dict, 후자는 `None`

- [ ] **Step 6: 커밋**

```bash
git add schema.sql db.py
GIT_AUTHOR_NAME="nk0101-del" GIT_AUTHOR_EMAIL="na3kyung@gmail.com" GIT_COMMITTER_NAME="nk0101-del" GIT_COMMITTER_EMAIL="na3kyung@gmail.com" git commit -m "feat: DB 스키마와 읽기/초기화 레이어 구현"
```

---

## Task 7: 학생 액션 레이어 — 지원/투표 (`db.py` 확장)

**Files:**
- Modify: `db.py`

**Interfaces:**
- Consumes: Task 2의 `check_team_constraints`, `format_result`; Task 6의 `get_teams`, `get_student`
- Produces:
  - `get_my_pending_application(engine, student_no: str) -> dict | None` — `{"application_id", "team_id", "status"}`
  - `apply_to_team(engine, student_no: str, team_id: int) -> str` — `format_result`로 만든 문자열(`"승인"`, `"대기"`, `"막힘: ..."`)
  - `cast_vote(engine, voter_no: str, application_id: int, vote: str) -> str` — `"찬성"`/`"거부"`, 결과를 `format_result`로 반환(`"승인"`, `"대기"`, `"거절"`)

- [ ] **Step 1: "결과를 기다리는 지원이 있으면 재지원 막힘" 수동 테스트 시나리오 작성**

Run (Supabase에 연결된 상태로 임시 스크립트 또는 Python REPL):
```python
apply_to_team(engine, "2026307", 1)   # 팀1에 지원 → 대기(팀원 있는 팀이라 가정)
result = apply_to_team(engine, "2026307", 2)  # 결과 기다리는 중 다른 팀에 또 지원
assert result.startswith("막힘")
```
Expected: 두 번째 호출이 `"막힘"`으로 시작

- [ ] **Step 2: `apply_to_team` 구현**

흐름: (a) `student_no`에게 "결과를 기다리는 지원"(`status="대기"`)이나 이미 팀원인 상태가 있으면 `format_result("막힘", "...")` 반환. (b) 모집 마감 상태면 `format_result("막힘", "모집이 마감됨")`. (c) `get_teams(engine)[team_id - 1]`로 해당 팀의 현재 멤버 리스트를 구해 `check_team_constraints`로 검사 — 실패하면 `format_result("막힘", reason)`. (d) 빈 팀이면 즉시 `tf_members`에 추가하고 `format_result("승인")`. (e) 팀원 있는 팀이면 `tf_applications`에 `status="대기"`로 기록하고 `format_result("대기")`.

- [ ] **Step 3: Step 1 시나리오로 수동 검증**

Expected: Step 1의 assert 통과

- [ ] **Step 4: "투표자 집합의 동적 변경" 수동 테스트 시나리오 작성 및 검증**

Run:
```python
apply_to_team(engine, "2026304", 1)      # 학생4가 팀1에 지원 → 대기
cast_vote(engine, "2026301", app_id, "찬성")  # 기존 팀원1이 찬성 → 아직 대기(팀원 더 있으면)
apply_to_team(engine, "2026307", 1)      # 그 사이 다른 지원 처리 등으로 학생4가 이미 팀원이 됐다고 가정
# 학생4가 새 팀원이 된 뒤 들어온 지원(학생7)에 대해 학생4도 투표할 수 있어야 함
cast_vote(engine, "2026304", app_id_2, "찬성")
```
Expected: 에러 없이 투표가 기록됨(투표 가능자 목록을 투표 시점의 현재 `tf_members`로 재계산했기 때문)

- [ ] **Step 5: `cast_vote` 구현**

`cast_vote`는 (a) 이미 투표했으면 그대로 두고 현재 상태 반환(한 번 투표하면 못 바꿈, 2.4절). (b) `vote="거부"`면 즉시 `status="거절"`로 갱신, `format_result("거절")`. (c) `vote="찬성"`이면, `get_teams(engine)[team_id - 1]`로 **그 시점에 다시 조회한** 팀 멤버 전원이 찬성했는지 확인 — 아니면 `format_result("대기")`. (d) 전원 찬성이면 **승인 직전 재검사**: `check_team_constraints(현재팀원, 지원자)`를 다시 호출 — 실패하면 `status="거절"`, `format_result("거절")`; 성공하면 `tf_members`에 추가, `status="승인"`, `format_result("승인")`.

- [ ] **Step 6: Step 4 시나리오로 수동 검증, 커밋**

```bash
git add db.py
GIT_AUTHOR_NAME="nk0101-del" GIT_AUTHOR_EMAIL="na3kyung@gmail.com" GIT_COMMITTER_NAME="nk0101-del" GIT_COMMITTER_EMAIL="na3kyung@gmail.com" git commit -m "feat: 학생 지원/투표 액션과 승인 직전 재검사 구현"
```

---

## Task 8: 관리자 액션 레이어 — 마감/AI 배정/확정 (`db.py` 확장)

**Files:**
- Modify: `db.py`

**Interfaces:**
- Consumes: Task 3의 `validate_final_assignment`; Task 5의 `assign_with_fallback`; Task 6의 `get_teams`, `get_unassigned_students`
- Produces:
  - `close_recruiting(engine) -> None`
  - `run_ai_assignment(engine, api_key: str, models: list[str], on_status=lambda msg: None) -> tuple[list[list[dict]] | None, list[dict], str | None]` — `(제안, 로그, 실패사유_또는_None)`. 제안이 `None`이면 실패사유에 "규칙을 지키는 배정이 없음" 계열 문구를 담는다.
  - `confirm_assignment(engine, proposal: list[list[dict]]) -> None`

- [ ] **Step 1: "마감 시 1인팀 해체" 수동 테스트 시나리오 작성**

Run:
```python
# 팀3에 학생6 1명만 있는 상태를 만든 뒤
close_recruiting(engine)
unassigned = get_unassigned_students(engine)
assert any(s["student_no"] == "학생6의 학번" for s in unassigned)
teams = get_teams(engine)
assert all(len(t["members"]) != 1 for t in teams)
```
Expected: 1인팀이던 팀이 빈 팀이 되고 그 학생이 unassigned에 나타남

- [ ] **Step 2: `close_recruiting` 구현**

`tf_settings`에 마감 플래그 기록 → `status="대기"`인 모든 지원을 `"거절"`로 갱신 → 멤버가 1명뿐인 팀에서 그 멤버를 제거(팀은 빈 채로 남김, `tf_teams` 행 자체는 삭제하지 않음).

- [ ] **Step 3: Step 1 시나리오로 수동 검증**

- [ ] **Step 4: `run_ai_assignment` 구현**

`get_teams`, `get_unassigned_students`로 현재 상태를 읽어 `assign_with_fallback`에 전달, 반환된 `(제안, 로그)`를 `tf_ai_logs`에 기록하고 `(제안, 로그, None)` 또는 제안이 `None`이면 `(None, 로그, "규칙을 지키는 배정이 없음")`을 반환. **아직 DB에 저장하지 않는다**(2.5절 7번 — 확정 전까지 보여주기만).

- [ ] **Step 5: `confirm_assignment` 구현 및 수동 검증**

`proposal`(`list[list[dict]]`, Task 3/5와 동일하게 인덱스 `i`가 `team_id = i+1`에 대응)을 저장 직전에 `validate_final_assignment`로 한 번 더 확인(방어적). 통과하면 각 팀(`i+1`)의 `proposal[i]`를 순회해, **그 팀에 이미 `tf_members`로 존재하지 않는 학생만** 새로 삽입한다(기존 팀원은 지원/투표 단계에서 이미 저장되어 있으므로 중복 삽입 방지, 또한 "이미 팀에 있는 학생은 옮기지 않음" 요구사항과 일치).

Run: 전체 흐름(`close_recruiting` → `run_ai_assignment` → `confirm_assignment`)을 부록 1(쉬움) 명단으로 수동 실행
Expected: 최종 `get_unassigned_students(engine)`가 빈 리스트, `get_teams(engine)`의 각 팀이 2~4명이고 `validate_final_assignment`를 통과

- [ ] **Step 6: 커밋**

```bash
git add db.py
GIT_AUTHOR_NAME="nk0101-del" GIT_AUTHOR_EMAIL="na3kyung@gmail.com" GIT_COMMITTER_NAME="nk0101-del" GIT_COMMITTER_EMAIL="na3kyung@gmail.com" git commit -m "feat: 모집 마감과 AI 배정/확정 로직 구현"
```

---

## Task 9: Streamlit UI — 로그인과 학생 화면

**Files:**
- Create: `streamlit_app.py`

**Interfaces:**
- Consumes: Task 6의 `get_engine`(캐싱), `verify_login`, `get_teams`, `get_unassigned_students`, `is_recruiting_closed`; Task 7의 `get_my_pending_application`, `apply_to_team`, `cast_vote`; Task 4의 `is_admin_login`

- [ ] **Step 1: 로그인 화면 구현**

`st.text_input(key="login_student_no")`, `st.text_input(key="login_password", type="password")`, `st.form_submit_button(key="login_submit")`. 성공 시 `st.session_state["student_no"]`에 학번(또는 `"admin"`) 저장. 실패 시 `result`(key="result") 컨테이너에 `format_result("막힘", "학번 또는 비밀번호가 올바르지 않음")` 출력.

- [ ] **Step 2: 로그인 후 분기 — `is_admin_login`이면 Task 10의 관리자 화면, 아니면 학생 화면 렌더링**

- [ ] **Step 3: 로그인한 사람 표시**

`st.container(key="whoami")`에 이름(관리자면 "관리자") 표시

- [ ] **Step 4: 팀 목록 — `st.fragment(run_every="5s")`로 감싼 블록**

`teams = get_teams(engine)`를 `enumerate(teams)`로 순회하며 `team_id = i + 1`을 구하고, 각 팀을 `st.container(key=f"team_{team_id}")`로 표시, 멤버 이름과 역할 표시. 로그인한 학생의 팀은 "내 팀" 표시로 구별. 팀이 없으면 "아직 팀이 없음" 표시(채점 대상 아님). 화면 상단에 "화면은 5초마다 자동으로 바뀜" 고정 안내.

- [ ] **Step 5: 지원 단추**

각 팀에 `st.button(key=f"apply_{team_id}")`. 이미 팀이 있거나, 결과 기다리는 지원이 있거나, 모집 마감이면 단추를 숨기거나 `disabled=True`(2.8절). 누르면 `apply_to_team` 호출 결과를 `st.container(key="result")`에 출력.

- [ ] **Step 6: 내 팀에 들어온 지원에 투표**

내 팀에 대한 대기 중인 지원들을 나열, 각각 `st.button(key=f"vote_yes_{지원자학번}")`/`st.button(key=f"vote_no_{지원자학번}")`. 이미 투표했으면 숨기거나 비활성화하고 "내 투표: 찬성"처럼 표시(2.8절). 누르면 `cast_vote` 결과를 `result` 컨테이너에 출력.

- [ ] **Step 7: 로컬에서 `streamlit run streamlit_app.py`로 학생 로그인 수동 확인**

Run: `streamlit run streamlit_app.py`, 가상 학생으로 로그인해 팀 목록이 보이는지 확인
Expected: 로그인/팀 목록 화면 정상 렌더링, 에러 없음

- [ ] **Step 8: 커밋**

```bash
git add streamlit_app.py
GIT_AUTHOR_NAME="nk0101-del" GIT_AUTHOR_EMAIL="na3kyung@gmail.com" GIT_COMMITTER_NAME="nk0101-del" GIT_COMMITTER_EMAIL="na3kyung@gmail.com" git commit -m "feat: 로그인 화면과 학생 화면 구현"
```

---

## Task 10: Streamlit UI — 관리자 화면

**Files:**
- Modify: `streamlit_app.py`

**Interfaces:**
- Consumes: Task 6의 `upload_roster`; Task 8의 `close_recruiting`, `run_ai_assignment`, `confirm_assignment`, `get_unassigned_students`

- [ ] **Step 1: 명단 올리기**

`st.file_uploader(key="admin_roster_file")`(CSV를 `utf-8-sig`로 읽음), `st.number_input(key="admin_team_count")`, `st.button(key="admin_start")`. 누르면 CSV 파싱 후 `upload_roster` 호출, 결과를 `result`에 `format_result("승인", "...")`로 출력.

- [ ] **Step 2: 모집 마감**

`st.button(key="admin_close")` → `close_recruiting` 호출 → `result`에 출력.

- [ ] **Step 3: 팀이 없는 학생 표시**

`st.container(key="unassigned")`에 `get_unassigned_students` 결과의 이름 나열.

- [ ] **Step 4: AI 배정**

`st.button(key="admin_assign")` → `run_ai_assignment` 호출, 진행 중 `st.container(key="assign_status")`에 `on_status` 콜백으로 "N차 모델 응답 대기 중" 갱신. 결과가 `None`이면 `assign_status`에 "규칙을 지키는 배정이 없음: 이유" 표시. 제안이 있으면 학생 이름/역할/배정될 팀을 표로 보여줌(아직 미확정).

- [ ] **Step 5: 배정안 확정**

`st.button(key="admin_confirm")` → `confirm_assignment` 호출 → `result`에 `format_result("승인", "배정을 확정함")` 출력.

- [ ] **Step 6: 관리자 화면 현황 블록을 `st.fragment(run_every="5s")`로 감싸기**

- [ ] **Step 7: 로컬에서 부록 1(쉬움) 시나리오 전체를 관리자+학생 두 세션으로 수동 실행**

Run: `어려움.csv`가 아닌 `쉬움.csv`로 명단 업로드 → 부록 1의 6단계를 전부 순서대로 수행
Expected: 각 단계의 `result` 첫 단어가 공고 부록 1의 "기대 결과"와 일치

- [ ] **Step 8: 커밋**

```bash
git add streamlit_app.py
GIT_AUTHOR_NAME="nk0101-del" GIT_AUTHOR_EMAIL="na3kyung@gmail.com" GIT_COMMITTER_NAME="nk0101-del" GIT_COMMITTER_EMAIL="na3kyung@gmail.com" git commit -m "feat: 관리자 화면(명단/마감/AI 배정/확정) 구현"
```

---

## Task 11: DB 일시정지 방지 + 문서

**Files:**
- Create: `.github/workflows/keep-db-awake.yml`
- Create: `README.md`, `docs/PRD.md`, `docs/구현 계획.md`(내용 채움)

**Interfaces:**
- 없음(독립적인 운영/문서 작업)

- [ ] **Step 1: GitHub Actions 워크플로 작성**

매일 1회(`schedule: cron`) 배포된 Streamlit 주소를 `curl`로 호출하는 워크플로(2.1절에 따라 앱 시작 시 admin 계정이 갱신되며 DB 요청이 발생함을 이용).

- [ ] **Step 2: `README.md` 작성 (7.1절 양식 그대로)**

배포 주소, PRD/구현계획 위치, 기능별 고른 해결(전부 "어려운 해결"), 모델 3개 이름(`.env`의 `OPENROUTER_MODEL_1/2/3` 실제 값), AI 호출 실패 사례 1건+화면, 발견한 클로드 오류 사례 1건+근거, 발견한 문제점 1건+근거. 5~7항은 구현 중 실제로 겪은 사례를 수동으로 채워 넣어야 하므로 이 Step은 플레이스홀더 구조만 만들고, Task 12 수동 검증 중 실제 사례로 채운다.

- [ ] **Step 3: `docs/PRD.md`, `docs/구현 계획.md` 작성**

이 설계 스펙(§1~§13)과 이 구현 계획 문서의 내용을 요약해 정리.

- [ ] **Step 4: 커밋**

```bash
git add .github/workflows/keep-db-awake.yml README.md docs/PRD.md "docs/구현 계획.md"
GIT_AUTHOR_NAME="nk0101-del" GIT_AUTHOR_EMAIL="na3kyung@gmail.com" GIT_COMMITTER_NAME="nk0101-del" GIT_COMMITTER_EMAIL="na3kyung@gmail.com" git commit -m "docs: README/PRD/구현 계획과 DB 유지 워크플로 추가"
```

---

## Task 12: 전체 시나리오 수동 검증 + 배포

> **사용자 작업 필요**: OpenRouter API 키 발급, Streamlit Community Cloud 계정/배포, (아직이면) Supabase 비공개 설정 확인 — 계정 관련 작업은 사용자가 직접 한다.

**Files:**
- Modify: `README.md`(7.1절 5~7항을 실제 사례로 채움)

- [ ] **Step 1: 부록 1(쉬움) 시나리오 전체를 로컬 앱에서 처음부터 끝까지 재실행, 매 단계 `result` 확인**

- [ ] **Step 2: 부록 2(중간) 시나리오 전체 실행 — 막힘/거절/승인 직전 재검사 포함**

- [ ] **Step 3: 부록 3(어려움) 시나리오 전체 실행 — 필수 포함 역할 자리 막힘, 승인 직전 재검사로 거절 포함**

- [ ] **Step 4: 두 개의 브라우저 세션(학생 A/B)으로 동시 접속해 `st.fragment` 자동 갱신이 5초 내에 반영되는지 확인**

Expected: 한쪽에서 지원/투표하면 다른 쪽 화면이 새로고침 없이 갱신됨 — 실패 시 Task 9/10으로 돌아가 수정

- [ ] **Step 5: GitHub 저장소 공개 전환 준비, Streamlit Community Cloud 배포(사용자 계정 작업), Secrets 입력**

- [ ] **Step 6: 배포된 주소에서 부록 1 시나리오를 한 번 더 실행(배포 후 스모크 테스트 — 로컬 통과가 배포 정확성을 보장하지 않음)**

- [ ] **Step 7: README.md 7.1절 5~7항을 이번 검증 중 실제로 겪은 사례(AI 호출 실패, 잘못된 추론, 발견한 문제점)로 채우고 스크린샷을 `img/`에 저장**

- [ ] **Step 8: 최종 커밋 및 저장소 공개 전환**

```bash
git add README.md img/
GIT_AUTHOR_NAME="nk0101-del" GIT_AUTHOR_EMAIL="na3kyung@gmail.com" GIT_COMMITTER_NAME="nk0101-del" GIT_COMMITTER_EMAIL="na3kyung@gmail.com" git commit -m "docs: 시나리오 검증 결과와 README 근거 사례 반영"
git push -u origin master
```
