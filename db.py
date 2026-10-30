# 2026-10-26 20:07 KST
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from auth import hash_password, verify_password
from rules import check_team_constraints, format_result

load_dotenv()


def _normalize_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def get_engine():
    return create_engine(_normalize_url(os.getenv("DATABASE_URL")))


def bootstrap_admin(engine, admin_password: str) -> None:
    password_hash = hash_password(admin_password)
    with engine.begin() as conn:
        existing = conn.execute(
            text("select id from tf_students where student_no = 'admin'")
        ).fetchone()
        if existing:
            conn.execute(
                text("update tf_students set password_hash = :ph where student_no = 'admin'"),
                {"ph": password_hash},
            )
        else:
            conn.execute(
                text(
                    "insert into tf_students (student_no, name, main_role, password_hash, is_admin) "
                    "values ('admin', 'admin', NULL, :ph, true)"
                ),
                {"ph": password_hash},
            )


def upload_roster(engine, students: list[dict], team_count: int) -> None:
    default_password_hash = hash_password("1234")
    with engine.begin() as conn:
        conn.execute(text("delete from tf_votes"))
        conn.execute(text("delete from tf_applications"))
        conn.execute(text("delete from tf_members"))
        conn.execute(text("delete from tf_teams"))
        conn.execute(text("alter sequence tf_teams_id_seq restart with 1"))
        conn.execute(text("delete from tf_student_sub_roles"))
        conn.execute(text("delete from tf_students where student_no != 'admin'"))

        for student in students:
            result = conn.execute(
                text(
                    "insert into tf_students (student_no, name, main_role, password_hash, is_admin) "
                    "values (:no, :name, :role, :ph, false) returning id"
                ),
                {
                    "no": student["student_no"],
                    "name": student["name"],
                    "role": student["main_role"],
                    "ph": default_password_hash,
                },
            )
            student_id = result.scalar_one()
            for role in student["sub_roles"]:
                conn.execute(
                    text("insert into tf_student_sub_roles (student_id, role) values (:sid, :role)"),
                    {"sid": student_id, "role": role},
                )

        for i in range(team_count):
            conn.execute(
                text("insert into tf_teams (name) values (:name)"),
                {"name": f"팀{i + 1}"},
            )


def _sub_roles(conn, student_id: int) -> list[str]:
    return [
        r.role
        for r in conn.execute(
            text("select role from tf_student_sub_roles where student_id = :sid"), {"sid": student_id}
        )
    ]


def get_student(engine, student_no: str) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(
            text("select id, student_no, name, main_role, password_hash, is_admin "
                 "from tf_students where student_no = :no"),
            {"no": student_no},
        ).fetchone()
        if not row:
            return None
        sub_roles = _sub_roles(conn, row.id)
        return {
            "id": row.id,
            "student_no": row.student_no,
            "name": row.name,
            "main_role": row.main_role,
            "password_hash": row.password_hash,
            "is_admin": row.is_admin,
            "sub_roles": sub_roles,
        }


def verify_login(engine, student_no: str, password: str) -> dict | None:
    student = get_student(engine, student_no)
    if not student:
        return None
    if not verify_password(password, student["password_hash"]):
        return None
    return student


def get_teams(engine) -> list[list[dict]]:
    with engine.connect() as conn:
        team_ids = [r.id for r in conn.execute(text("select id from tf_teams order by id"))]
        teams = []
        for team_id in team_ids:
            rows = conn.execute(
                text(
                    "select s.student_no, s.main_role, s.id "
                    "from tf_members m join tf_students s on s.id = m.student_id "
                    "where m.team_id = :tid"
                ),
                {"tid": team_id},
            ).fetchall()
            members = []
            for row in rows:
                members.append(
                    {
                        "id": row.id,
                        "student_no": row.student_no,
                        "main_role": row.main_role,
                        "sub_roles": _sub_roles(conn, row.id),
                    }
                )
            teams.append(members)
        return teams


def get_unassigned_students(engine) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "select s.id, s.student_no, s.main_role from tf_students s "
                "where s.is_admin = false and s.id not in (select student_id from tf_members)"
            )
        ).fetchall()
        result = []
        for row in rows:
            result.append(
                {
                    "id": row.id,
                    "student_no": row.student_no,
                    "main_role": row.main_role,
                    "sub_roles": _sub_roles(conn, row.id),
                }
            )
        return result


def is_recruiting_closed(engine) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text("select value from tf_settings where key = 'recruiting_closed'")
        ).fetchone()
        return bool(row) and row.value == "true"


def get_my_pending_application(engine, student_no: str) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "select a.id, a.team_id, a.status from tf_applications a "
                "join tf_students s on s.id = a.student_id "
                "where s.student_no = :no and a.status = '대기'"
            ),
            {"no": student_no},
        ).fetchone()
        if not row:
            return None
        return {"application_id": row.id, "team_id": row.team_id, "status": row.status}


def apply_to_team(engine, student_no: str, team_id: int) -> str:
    if is_recruiting_closed(engine):
        return format_result("막힘", "모집이 마감됨")

    applicant = get_student(engine, student_no)

    with engine.connect() as conn:
        already_member = conn.execute(
            text("select 1 from tf_members where student_id = :sid"), {"sid": applicant["id"]}
        ).fetchone()
    if already_member:
        return format_result("막힘", "이미 팀이 있음")

    if get_my_pending_application(engine, student_no):
        return format_result("막힘", "결과를 기다리는 지원이 있음")

    team_members = get_teams(engine)[team_id - 1]
    applicant_for_rules = {
        "student_no": applicant["student_no"],
        "main_role": applicant["main_role"],
        "sub_roles": applicant["sub_roles"],
    }
    ok, reason = check_team_constraints(team_members, applicant_for_rules)
    if not ok:
        return format_result("막힘", reason)

    if not team_members:
        with engine.begin() as conn:
            conn.execute(
                text("insert into tf_members (team_id, slot_no, student_id) values (:tid, 1, :sid)"),
                {"tid": team_id, "sid": applicant["id"]},
            )
        return format_result("승인")

    with engine.begin() as conn:
        conn.execute(
            text("insert into tf_applications (team_id, student_id, status) values (:tid, :sid, '대기')"),
            {"tid": team_id, "sid": applicant["id"]},
        )
    return format_result("대기")


def cast_vote(engine, voter_no: str, application_id: int, vote: str) -> str:
    voter = get_student(engine, voter_no)

    with engine.connect() as conn:
        current_status = conn.execute(
            text("select status from tf_applications where id = :aid"), {"aid": application_id}
        ).fetchone()
        if current_status.status != "대기":
            return format_result(current_status.status)

        already_voted = conn.execute(
            text("select 1 from tf_votes where application_id = :aid and voter_id = :vid"),
            {"aid": application_id, "vid": voter["id"]},
        ).fetchone()
        if already_voted:
            app_row = conn.execute(
                text("select status from tf_applications where id = :aid"), {"aid": application_id}
            ).fetchone()
            return format_result(app_row.status)

    with engine.begin() as conn:
        conn.execute(
            text("insert into tf_votes (application_id, voter_id, vote) values (:aid, :vid, :vote)"),
            {"aid": application_id, "vid": voter["id"], "vote": vote},
        )

    if vote == "거부":
        with engine.begin() as conn:
            conn.execute(
                text("update tf_applications set status = '거절' where id = :aid"), {"aid": application_id}
            )
        return format_result("거절")

    with engine.connect() as conn:
        app_row = conn.execute(
            text("select team_id, student_id from tf_applications where id = :aid"), {"aid": application_id}
        ).fetchone()
    team_id, applicant_id = app_row.team_id, app_row.student_id

    current_members = get_teams(engine)[team_id - 1]
    with engine.connect() as conn:
        vote_rows = conn.execute(
            text("select voter_id, vote from tf_votes where application_id = :aid"), {"aid": application_id}
        ).fetchall()
    votes_by_voter = {v.voter_id: v.vote for v in vote_rows}
    all_approved = len(current_members) > 0 and all(
        votes_by_voter.get(m["id"]) == "찬성" for m in current_members
    )

    if not all_approved:
        return format_result("대기")

    with engine.connect() as conn:
        arow = conn.execute(
            text("select student_no, main_role from tf_students where id = :sid"), {"sid": applicant_id}
        ).fetchone()
        applicant_for_rules = {
            "student_no": arow.student_no,
            "main_role": arow.main_role,
            "sub_roles": _sub_roles(conn, applicant_id),
        }

    ok, reason = check_team_constraints(current_members, applicant_for_rules)
    if not ok:
        with engine.begin() as conn:
            conn.execute(
                text("update tf_applications set status = '거절', reason = :r where id = :aid"),
                {"r": reason, "aid": application_id},
            )
        return format_result("거절")

    with engine.begin() as conn:
        next_slot = len(current_members) + 1
        conn.execute(
            text("insert into tf_members (team_id, slot_no, student_id) values (:tid, :slot, :sid)"),
            {"tid": team_id, "slot": next_slot, "sid": applicant_id},
        )
        conn.execute(
            text("update tf_applications set status = '승인' where id = :aid"), {"aid": application_id}
        )
    return format_result("승인")
