<!-- 2026-10-26 20:07 KST -->

# 팀 편성 웹 앱 — 설계 문서 (DSMP 중간과제)

## 1. 배경과 범위

데이터과학 미니프로젝트(AI-X) 중간과제. `중간과제 공고.pdf`에 기술된 요구사항을 그대로
구현 대상으로 삼는다. 이 문서는 공고의 요구사항을 반복하지 않고, **구현 설계(아키텍처,
모듈 분리, 알고리즘, 테스트 전략)에 대해서만** 기록한다. 기능 요구사항의 원천은 항상
`중간과제 공고.pdf`이며, 이 문서와 공고가 어긋나면 공고가 우선한다.

- 배점: 30점(쉬움 4 / 중간 8 / 어려움 12 / 시나리오 밖 6)
- 마감: 11/2(월) 23:59, 채점 11/3~11/4
- 제출물: 깃허브 저장소, 배포 주소, 관리자 비밀번호, 저장소 zip, README.md(7.1절 양식)

### 1.1 기능별 해결 수준 선택

3장 표의 6개 기능 전부 **어려운 해결**로 구현한다(점수 최대화 우선).

| 기능 | 선택 | 비고 |
|---|---|---|
| 다른 사람의 변경 보기 | 어려운(`st.fragment` 자동 갱신) | 구현 리스크 가장 높음 — §6 참고 |
| 필수 포함 역할을 지킬 수 없는 팀 | 어려운(지원 단계에서 막음) | |
| 같은 팀에 대기 중인 지원이 여럿 | 어려운(승인 직전 재검사) | |
| 마지막 자리 동시 입장 | 어려운(DB 유일성 제약) | 스키마로 해결, 별도 코드 불필요 |
| AI 응답이 늦을 때 | 어려운(전체 대기시간 강제 종료) | |
| 3차 모델까지 실패 | 어려운(규칙 만족 배정 전수 탐색) | |
| AI 대기 중 화면 | 어려운(몇 차 모델 대기 중인지 표시) | |
| DB 일시정지 방지 | 어려운(외부 예약 서비스) | GitHub Actions cron, §9 |

## 2. 모듈 구성

```
streamlit_app.py   진입점 — 로그인 분기, 학생/관리자 화면 렌더링, Streamlit key 지정(2.7절 표 그대로)
auth.py            로그인 검증, bcrypt 해시/검증, 세션 상태(student_no 또는 admin만 보관)
db.py              SQLAlchemy 엔진(st.cache_resource로 1회 생성) + 모든 쿼리 함수
rules.py           순수 함수 — DB/Streamlit 의존성 없음. 팀 규칙 판정의 단일 출처
ai_assign.py       OpenRouter 호출, 1차→2차→3차 폴백, 타임아웃, 3차 실패 시 자체 배정 호출
schema.sql          tf_ 테이블 정의(제약조건 포함)
tests/              rules.py·ai_assign.py에 대한 pytest 단위 테스트
docs/PRD.md, 구현 계획.md
README.md           7.1절 양식
```

설계 원칙: `rules.py`는 팀/지원/투표 상태를 평범한 파이썬 자료구조(dict/list)로 받아
판정 결과만 돌려준다. DB나 Streamlit을 몰라야 하며, 이것이 자동화된 pytest 테스트를
가능하게 하는 핵심 경계다.

## 3. 데이터 흐름 / 상태 관리

- `st.session_state`에는 로그인 주체(`student_no` 또는 `"admin"`)만 둔다.
- 팀 목록, 지원 현황, 투표 현황 등은 **매 렌더링마다 DB에서 새로 조회**한다. 세션에
  캐싱하지 않는다.
- 이유: Streamlit의 `session_state`는 브라우저 세션(=채점 프로그램이 여는 가상 학생별
  브라우저)마다 독립적이다. 캐싱하면 다른 학생의 지원/투표가 내 화면에 반영되지 않아,
  "다른 사람의 변경 보기" 점수뿐 아니라 그 이후 단계의 `result` 판정 자체가 틀어질 수
  있다(채점 프로그램은 화면에 보이는 현재 상태를 보고 다음 동작을 수행하므로 연쇄 오류
  위험).
- DB 연결은 앱 전역에서 1번만 생성하고 재사용한다(4.2절 요구사항, `st.cache_resource`).

## 4. 규칙 엔진 (`rules.py`)

| 함수 | 역할 |
|---|---|
| `count_required_role_gap(team_members) -> int` | 기획자·웹 프로그래머 중 아직 못 채운 필수 역할 수. 한 학생이 둘 다 가능해도 1자리로만 계산(3장 "필수 포함 역할 자리 계산" 참고) |
| `can_apply(team, applicant) -> (bool, reason)` | 지원 가능 여부 — 정원, 주 역할 중복, 필수 포함 역할 자리 부족을 지원 시점에 검사(막힌 지원, 2.4절) |
| `revalidate_before_approval(team, candidate_application) -> bool` | **승인 직전 재검사**. 같은 팀에 대기 지원이 여럿일 때 "투표가 끝난 순서"로 처리하고, 승인 직전 정원/주 역할 중복/필수 포함 역할을 다시 검사 |
| `validate_final_assignment(teams) -> (bool, reason)` | 2.5절 4항의 5가지 검사. AI 배정안 검증과 자체 배정 양쪽에서 재사용 |
| `find_valid_assignment(unassigned, teams) -> teams \| None` | 3차 모델까지 실패했을 때 전수 탐색(백트래킹) + 가지치기(남은 필수 역할 수 기준)로 규칙을 만족하는 배정을 끝까지 탐색. 6.2절 9번에 따라 배정 대상 학생이 8명을 넘지 않도록 시나리오가 설계되므로 성능 문제 없음 |

## 5. AI 배정 흐름 (`ai_assign.py`)

```
for 순번, model in [1차, 2차, 3차]:
    assign_status에 "N차 모델 응답 대기 중" 표시
    ThreadPoolExecutor().submit(call_openrouter, ...).result(timeout=120)
      # requests의 timeout 인자만 쓰지 않는다 — "응답 시작까지만 재는" 흔한 실수를 피하려고
      # 전체 대기시간을 future.result(timeout=120)으로 강제 종료한다
    응답 있으면 validate_final_assignment()로 검사
    실패(타임아웃/429/빈 응답/빈 검사 실패)면 다음 모델로, tf_ai_logs에 기록
3차까지 실패 → find_valid_assignment()
그래도 없음 → "규칙을 지키는 배정이 없음" + 이유 표시, AI 호출 안 함(2.5절 8항)
```

무료 모델은 `max_tokens`를 넉넉히, 추론 모델이면 `reasoning_effort=low`를 넣어 빈 응답을
줄인다(4.3절 권장 사항 반영).

## 6. 실시간 갱신 (`st.fragment`)

학생 화면의 팀 목록 블록, 관리자 화면의 현황 블록을 각각
`@st.fragment(run_every="5s")`로 감싼다. 화면 상단에 "화면은 5초마다 자동으로 바뀜"
고정 안내를 둔다.

**리스크**: `run_every` 자동 갱신은 비교적 최신 Streamlit 기능이라 실제 동작을 반드시
검증해야 한다. 구현 후 **서로 다른 두 로그인 세션(학생 A/B 브라우저)으로 동시에 접속해
한쪽의 지원·투표가 5초 내에 다른 쪽 화면에 실제로 반영되는지** 수동으로 확인하는 것을
완료 조건에 포함한다. 여기서 실패하면 "다른 사람의 변경 보기" 배점뿐 아니라 2.7절에
따라 채점 프로그램이 멈출 위험이 있다.

## 7. 보안 체크리스트 (6.3절 감점 방지, 구현 시점에 바로 반영)

- 비밀번호는 bcrypt 해시로만 저장/비교 (10번, -2점)
- 관리자 전용 쿼리 함수는 `auth.py`가 역할을 확인해야만 호출 가능하도록 래핑 — 학생
  세션에서 호출 경로 자체를 차단 (11번, -3점)
- 로그인 실패 시 무조건 거부, 학번만으로 접근 불가 (12번, -3점)
- 키 값은 `os.getenv`로만 읽고, 로그/화면 어디에도 값 출력 금지 — "있음/없음"만 표시 (8번, -3점)
- `.env`는 `.gitignore`에 등록, 매 커밋 전 `git status`로 확인 (7번, -3점)
- `openrouter/free` 라우터 미사용 (DB와 AI 14번, -2점)
- 전체 테이블명 `tf_` 접두사 (13번, -1점)
- 2.7절 표의 Streamlit `key` 값을 표와 정확히 일치시킴 (채점 방해 15번, -5점)

## 8. DB 스키마 (5장 최소 참고안 확장)

```sql
tf_students(id, student_no UNIQUE, name, main_role, password_hash, is_admin)
tf_student_sub_roles(student_id, role)
tf_teams(id, name UNIQUE)
tf_members(team_id, slot_no CHECK(1~4), student_id UNIQUE, PRIMARY KEY(team_id, slot_no))
tf_applications(id, team_id, student_id, status CHECK(대기,승인,거절), reason, created_at)
tf_votes(application_id, voter_id, vote CHECK(찬성,거부), PRIMARY KEY(application_id, voter_id))
tf_settings(key, value)
tf_ai_logs(id, batch_id, model_name, attempt_no, status, raw_response, created_at)
```

`tf_members`의 `(team_id, slot_no)`·`student_id` 유일성 제약이 "마지막 자리 동시 입장"의
어려운 해결을 DB 레벨에서 공짜로 보장한다. `tf_ai_logs`는 README 7.1절 5~6항(AI 호출
실패 사례, 클로드 오류 사례) 근거 자료로도 활용한다. 테이블을 만든 SQL은 반드시
`schema.sql`에 그대로 남긴다(채점자가 Supabase에 직접 접근 못 하므로 이 파일이 유일한
증거, 없으면 유일성 제약 0.5점 및 13·10번 항목 확인 불가 처리됨).

## 9. DB 일시정지 방지 (어려운 해결)

공고 2.1절에 따르면 관리자 계정은 **앱이 시작할 때마다** 생성/갱신되므로, 앱 홈 화면만
열어도 DB 요청이 발생한다. 별도의 DB 클라이언트 스크립트 없이, **GitHub Actions
scheduled workflow(cron, 매일 1회)가 배포된 Streamlit 주소를 `curl`로 호출**하는 것만으로
충분하다. 이 워크플로는 저장소 자체에 포함하여 제출한다.

## 10. 테스트 전략

1. `tests/test_rules.py` — 부록 1(쉬움)·2(중간)·3(어려움) 연습 시나리오의 각 단계를
   `rules.py` 함수 호출에 대한 입력→기대결과 pytest 케이스로 그대로 옮긴다. 앱 없이
   규칙 로직 정확성을 자동 확인.
2. `tests/test_ai_assign.py` — OpenRouter 응답을 모킹하여 폴백(1차 실패→2차 성공),
   3차까지 실패→자체 배정, 타임아웃 처리 경로를 테스트.
3. 실제 Streamlit 앱(로컬)으로 부록 1~3 시나리오를 처음부터 끝까지 수동 실행, 각 단계
   `result` 문구가 기대 결과와 일치하는지 확인. §6의 멀티세션(동시 로그인) 갱신 확인
   포함.
4. **배포 후 스모크 테스트**(CLAUDE.md 5번 원칙) — Streamlit Community Cloud 배포 주소,
   Secrets 반영, 실제 Supabase 연결, 타임아웃 동작을 배포 환경에서 한 번 더 확인. 로컬
   통과를 정확성의 증거로 삼지 않는다.

## 11. 저장소 구조 / 환경 변수

```
DP_Task/
  streamlit_app.py, auth.py, db.py, rules.py, ai_assign.py
  schema.sql
  requirements.txt
  .env.example       (값 없는 템플릿, 실제 .env는 .gitignore)
  .gitignore
  README.md
  docs/PRD.md, docs/구현 계획.md
  tests/test_rules.py, tests/test_ai_assign.py
  img/               (README 근거 스크린샷)
  .github/workflows/keep-db-awake.yml
```

`.env` 항목: `OPENROUTER_API_KEY`, `OPENROUTER_MODEL_1/2/3`, `DATABASE_URL`,
`ADMIN_PASSWORD`. 모델 3개는 하드코딩하지 않고 환경 변수로 분리한다 — 무료 모델 목록은
수시로 바뀌므로, 배포 직전 openrouter.ai/models(Free 필터)에서 실제 가용 모델을 확인해
채워 넣는다.

개발 환경: 설치되어 있는 Python 3.13으로 `venv` 하나 생성해 진행(추가 도구 불필요).

## 12. 미해결 전제조건 (사용자가 직접 해야 하는 작업)

구현/코드 작성은 지금 진행 가능하지만, 아래는 계정 생성이 필요해 본인이 직접 해야 한다.
해당 단계에서 안내한다.

- OpenRouter API 키 발급 (가입은 완료됨)
- Supabase 프로젝트 생성 + `DATABASE_URL` 확보
- GitHub 비공개 저장소 생성(사용자의 `gh` CLI 인증 확인됨 — 대신 생성 가능, 실행 전 확인받음)
- Streamlit Community Cloud 배포 + Secrets 입력

## 13. 다음 단계

이 설계를 바탕으로 `writing-plans` 스킬을 사용해 구현 계획을 수립한다.
