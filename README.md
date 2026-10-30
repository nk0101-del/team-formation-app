# 팀 편성 웹 앱

데이터과학 미니프로젝트(AI-X) 중간과제. `중간과제 공고.pdf`의 요구사항을 구현한 Streamlit 앱.

## 1. 배포 주소

(Task 12에서 Streamlit Community Cloud 배포 후 채움)

## 2. PRD와 구현 계획의 위치

- `docs/PRD.md`
- `docs/구현 계획.md`

## 3. 고른 해결 방법

3장 표의 6개 기능 전부 **어려운 해결**로 구현함.

| 기능 | 해결 | 비고 |
|---|---|---|
| 다른 사람의 변경 보기 | 어려운 해결 | `st.fragment(run_every="5s")`로 팀 목록을 5초마다 자동 갱신 |
| 필수 포함 역할을 지킬 수 없는 팀 | 어려운 해결 | 지원 단계에서 `rules.check_team_constraints`로 자리 부족을 미리 막음 |
| 같은 팀에 대기 중인 지원이 여럿 | 어려운 해결 | 승인 직전에 `rules.check_team_constraints`로 재검사 |
| 마지막 자리에 두 명이 동시에 들어감 | 어려운 해결 | `tf_members`의 `(team_id, slot_no)`와 `student_id` 유일성 제약으로 DB가 막음 |
| AI 응답이 늦을 때 | 어려운 해결 | `ThreadPoolExecutor.result(timeout=...)`로 전체 대기시간 강제 종료 |
| 3차 모델까지 실패 | 어려운 해결 | `rules.find_valid_assignment`로 규칙을 만족하는 배정을 전수 탐색 |
| AI 대기 중 화면 | 어려운 해결 | `assign_status` 컨테이너에 몇 차 모델 대기 중인지 표시 |
| DB(Supabase)가 일시정지되지 않게 | 어려운 해결 | `.github/workflows/keep-db-awake.yml`이 매일 배포 주소를 호출 |

## 4. 쓴 모델 3개의 이름

(Task 12에서 openrouter.ai/models(Free 필터)에서 실제 가용 모델을 확인해 `.env`의 `OPENROUTER_MODEL_1/2/3`에 채운 뒤 여기에 적음)

## 5. 오픈라우터 AI 모델 호출 실패 사례

(Task 12 배포 후 실제 호출 실패 사례와 화면 캡처로 채움)

## 6. 과제 해결 과정에서 클로드가 잘못된 추론이나 답변을 한 사례

구현 중 발견하고 고친 버그들(전부 `.superpowers/sdd/2026-10-26-team-formation-app/progress.md` 원장의 `Ruling:` 항목에 근거로 남아 있음):

1. **upload_roster가 팀 ID 시퀀스를 리셋하지 않은 문제**: `tf_teams`를 `delete`만 하고 `serial` 시퀀스를 그대로 둬서, 명단을 두 번째 올릴 때부터 새 팀의 DB id가 1..N이 아니게 되어 "team_1의 1은 관리자가 만든 팀1,팀2,...의 번호"라는 전제가 깨지고 `tf_members` 외래키 위반이 났음. `db.py`의 `upload_roster`를 직접 재실행해 발견했고, `alter sequence tf_teams_id_seq restart with 1`을 추가해 고침.
2. **upload_roster가 마감 표시를 지우지 않은 문제**: 공고 2.6절은 "지원, 투표, 팀원, 마감 표시를 모두 지우고" 초기화하라고 명시하는데, `tf_settings`(마감 표시)를 지우는 코드가 빠져 있어서 한 번 마감한 뒤 새 명단을 올려도 계속 "막힘: 모집이 마감됨"이 나는 걸 수동 시나리오 검증 중 발견. `upload_roster`에 `delete from tf_settings`를 추가해 고침.
3. **버튼 클릭 직후 `st.rerun()`이 방금 쓴 result를 지우는 문제**: 지원/투표 단추를 누른 직후 `st.rerun()`을 또 호출하면, 그 실행에서 `result` 컨테이너에 써 둔 메시지가 다음 재실행에서 바로 지워져 "단계마다 result를 확인"(6.2절)할 수 없게 됨을 실제 브라우저로 직접 테스트하다 발견. `st.session_state`에 결과를 담아 재실행 뒤에도 보이게 고침.

## 7. 본인이 제출한 앱에서 발견한 문제점이나 개선 필요 사항

(Task 12에서 연습 시나리오 1~3을 끝까지 수동 실행하며 발견한 사례와 화면으로 채움)

## 개발 환경

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # 값을 채운 뒤 사용
pytest
streamlit run streamlit_app.py
```
