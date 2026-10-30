-- 2026-10-26 20:07 KST
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
