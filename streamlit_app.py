# 2026-10-26 20:07 KST
import os

import pandas  # noqa: F401  (st.fragment(run_every=...)의 백그라운드 스레드와 동시에 지연 임포트되며 순환 임포트 레이스가 나는 것을 막기 위해 메인 스레드에서 미리 로드)
import streamlit as st
from dotenv import load_dotenv

from auth import is_admin_login
from db import (
    apply_to_team,
    bootstrap_admin,
    cast_vote,
    get_engine,
    get_my_pending_application,
    get_my_vote,
    get_pending_applications_for_team,
    get_teams,
    get_unassigned_students,
    is_recruiting_closed,
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
    with st.container(key="whoami"):
        st.write(f"로그인: {student_no}")
    show_last_result()

    @st.fragment(run_every="5s")
    def team_list():
        st.caption("화면은 5초마다 자동으로 바뀜")
        for i, members in enumerate(get_teams(engine)):
            team_id = i + 1
            with st.container(key=f"team_{team_id}"):
                title = f"팀{team_id}"
                if any(m["student_no"] == student_no for m in members):
                    title += " (내 팀)"
                st.write(title)
                if members:
                    for m in members:
                        st.write(f"- {m['student_no']} ({m['main_role']})")
                else:
                    st.write("아직 팀이 없음")

    team_list()

    teams = get_teams(engine)
    my_team_id = None
    for i, members in enumerate(teams):
        if any(m["student_no"] == student_no for m in members):
            my_team_id = i + 1

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
                st.write(f"{app['student_no']}: 내 투표: {my_vote}")
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


if "student_no" not in st.session_state:
    st.session_state["student_no"] = None

if st.session_state["student_no"] is None:
    render_login()
elif is_admin_login(st.session_state["student_no"]):
    with st.container(key="whoami"):
        st.write("로그인: 관리자")
    st.write("관리자 화면은 다음 작업에서 구현합니다.")
else:
    render_student_screen(st.session_state["student_no"])
