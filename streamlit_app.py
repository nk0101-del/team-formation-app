# 2026-10-26 20:07 KST
import csv
import io
import os

import pandas  # noqa: F401  (st.fragment(run_every=...)의 백그라운드 스레드와 동시에 지연 임포트되며 순환 임포트 레이스가 나는 것을 막기 위해 메인 스레드에서 미리 로드)
import streamlit as st
from dotenv import load_dotenv

from auth import is_admin_login
from db import (
    apply_to_team,
    bootstrap_admin,
    cast_vote,
    close_recruiting,
    confirm_assignment,
    get_engine,
    get_my_pending_application,
    get_my_vote,
    get_pending_applications_for_team,
    get_student,
    get_teams,
    get_unassigned_students,
    is_recruiting_closed,
    run_ai_assignment,
    upload_roster,
    verify_login,
)
from rules import format_result

load_dotenv()


@st.cache_resource
def _init_engine():
    engine = get_engine()
    bootstrap_admin(engine, os.getenv("ADMIN_PASSWORD"))
    return engine


engine = _init_engine()

st.title("팀 편성")


def show_last_result():
    with st.container(key="result"):
        if "last_result" in st.session_state:
            st.write(st.session_state["last_result"])


def set_result_and_rerun(message: str):
    st.session_state["last_result"] = message
    st.rerun()


def _role_text(member: dict) -> str:
    if member["sub_roles"]:
        return f"{member['main_role']} / {', '.join(member['sub_roles'])}"
    return member["main_role"]


def render_login():
    with st.form("login_form"):
        student_no = st.text_input("학번", key="login_student_no")
        password = st.text_input("비밀번호", type="password", key="login_password")
        submitted = st.form_submit_button("로그인", key="login_submit")
    if submitted:
        student = verify_login(engine, student_no, password)
        if student:
            st.session_state["student_no"] = student_no
            st.rerun()
        else:
            with st.container(key="result"):
                st.write(format_result("막힘", "학번 또는 비밀번호가 올바르지 않음"))


def render_student_screen(student_no: str):
    show_last_result()

    @st.fragment(run_every="5s")
    def body():
        st.caption("화면은 5초마다 자동으로 바뀜")

        me = get_student(engine, student_no)
        with st.container(key="whoami"):
            st.write(f"로그인: {me['name']}")

        teams = get_teams(engine)
        my_team_id = None
        for i, members in enumerate(teams):
            if any(m["student_no"] == student_no for m in members):
                my_team_id = i + 1

        for i, members in enumerate(teams):
            team_id = i + 1
            with st.container(key=f"team_{team_id}"):
                title = f"팀{team_id}"
                if team_id == my_team_id:
                    title += " (내 팀)"
                st.write(title)
                if members:
                    for m in members:
                        st.write(f"- {m['name']} ({_role_text(m)})")
                else:
                    st.write("아직 팀이 없음")

        already_member = my_team_id is not None
        pending = get_my_pending_application(engine, student_no)
        closed = is_recruiting_closed(engine)
        can_apply = not already_member and not pending and not closed

        if can_apply:
            st.subheader("팀에 지원하기")
            for i in range(len(teams)):
                team_id = i + 1
                if st.button(f"팀{team_id}에 지원", key=f"apply_{team_id}"):
                    result = apply_to_team(engine, student_no, team_id)
                    set_result_and_rerun(result)

        if my_team_id is not None:
            st.subheader("내 팀에 들어온 지원")
            for app in get_pending_applications_for_team(engine, my_team_id):
                my_vote = get_my_vote(engine, app["application_id"], student_no)
                if my_vote:
                    st.write(f"{app['name']}: 내 투표: {my_vote}")
                else:
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("찬성", key=f"vote_yes_{app['student_no']}"):
                            result = cast_vote(engine, student_no, app["application_id"], "찬성")
                            set_result_and_rerun(result)
                    with col2:
                        if st.button("거부", key=f"vote_no_{app['student_no']}"):
                            result = cast_vote(engine, student_no, app["application_id"], "거부")
                            set_result_and_rerun(result)

    body()


def render_admin_screen():
    with st.container(key="whoami"):
        st.write("로그인: 관리자")
    show_last_result()

    roster_file = st.file_uploader("명단 CSV", key="admin_roster_file")
    team_count = st.number_input("팀 수", min_value=1, step=1, value=1, key="admin_team_count")
    if st.button("처음 상태 만들기", key="admin_start"):
        if roster_file is None:
            set_result_and_rerun(format_result("막힘", "명단 파일이 없음"))
        else:
            content = roster_file.getvalue().decode("utf-8-sig")
            students = []
            for row in csv.DictReader(io.StringIO(content)):
                sub = row["sub_roles"].strip()
                students.append(
                    {
                        "student_no": row["student_no"],
                        "name": row["name"],
                        "main_role": row["main_role"],
                        "sub_roles": sub.split(";") if sub else [],
                    }
                )
            upload_roster(engine, students, int(team_count))
            st.session_state["assign_proposal"] = None
            st.session_state["assign_status_text"] = ""
            set_result_and_rerun(
                format_result("승인", f"학생 {len(students)}명, 팀 {int(team_count)}개로 초기화함")
            )

    if st.button("모집 마감", key="admin_close"):
        close_recruiting(engine)
        set_result_and_rerun(format_result("승인", "모집을 마감함"))

    @st.fragment(run_every="5s")
    def status_view():
        st.caption("화면은 5초마다 자동으로 바뀜")
        for i, members in enumerate(get_teams(engine)):
            team_id = i + 1
            with st.container(key=f"team_{team_id}"):
                st.write(f"팀{team_id}")
                if members:
                    for m in members:
                        st.write(f"- {m['name']} ({_role_text(m)})")
                else:
                    st.write("(비어 있음)")
        with st.container(key="unassigned"):
            names = [s["name"] for s in get_unassigned_students(engine)]
            st.write(", ".join(names) if names else "없음")

    status_view()

    assign_status_box = st.container(key="assign_status")
    with assign_status_box:
        if "assign_status_text" in st.session_state:
            st.write(st.session_state["assign_status_text"])

    if st.button("AI 배정", key="admin_assign"):
        placeholder = assign_status_box.empty()

        def on_status(msg):
            st.session_state["assign_status_text"] = msg
            placeholder.write(msg)

        models = [os.getenv("OPENROUTER_MODEL_1"), os.getenv("OPENROUTER_MODEL_2"), os.getenv("OPENROUTER_MODEL_3")]
        proposal, logs, fail_reason = run_ai_assignment(
            engine, os.getenv("OPENROUTER_API_KEY"), models, on_status=on_status
        )
        if proposal is None:
            st.session_state["assign_status_text"] = format_result("막힘", fail_reason)
            st.session_state["assign_proposal"] = None
            set_result_and_rerun(format_result("막힘", fail_reason))
        else:
            st.session_state["assign_proposal"] = proposal
            st.session_state["assign_status_text"] = "배정안을 확인하고 확정하세요"
            set_result_and_rerun(format_result("승인", "배정안을 만듦. 확인 후 확정하세요"))

    proposal = st.session_state.get("assign_proposal")
    if proposal is not None:
        st.subheader("배정안 (확정 전)")
        for i, members in enumerate(proposal):
            st.write(f"팀{i + 1}: " + ", ".join(f"{m['name']}({_role_text(m)})" for m in members))
        if st.button("배정안 확정", key="admin_confirm"):
            confirm_assignment(engine, proposal)
            st.session_state["assign_proposal"] = None
            st.session_state["assign_status_text"] = ""
            set_result_and_rerun(format_result("승인", "배정을 확정함"))


if "student_no" not in st.session_state:
    st.session_state["student_no"] = None

if st.session_state["student_no"] is None:
    render_login()
elif is_admin_login(st.session_state["student_no"]):
    render_admin_screen()
else:
    render_student_screen(st.session_state["student_no"])
