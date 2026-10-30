# 2026-10-26 20:07 KST
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from auth import hash_password, verify_password

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


def get_student(engine, student_no: str) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(
            text("select id, student_no, name, main_role, password_hash, is_admin "
                 "from tf_students where student_no = :no"),
            {"no": student_no},
        ).fetchone()
        if not row:
            return None
        sub_roles = [
            r.role
            for r in conn.execute(
                text("select role from tf_student_sub_roles where student_id = :sid"),
                {"sid": row.id},
            )
        ]
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
                sub_roles = [
                    r.role
                    for r in conn.execute(
                        text("select role from tf_student_sub_roles where student_id = :sid"),
                        {"sid": row.id},
                    )
                ]
                members.append(
                    {"student_no": row.student_no, "main_role": row.main_role, "sub_roles": sub_roles}
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
            sub_roles = [
                r.role
                for r in conn.execute(
                    text("select role from tf_student_sub_roles where student_id = :sid"),
                    {"sid": row.id},
                )
            ]
            result.append(
                {"student_no": row.student_no, "main_role": row.main_role, "sub_roles": sub_roles}
            )
        return result


def is_recruiting_closed(engine) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text("select value from tf_settings where key = 'recruiting_closed'")
        ).fetchone()
        return bool(row) and row.value == "true"
