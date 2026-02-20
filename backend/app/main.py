from fastapi import FastAPI, Depends, HTTPException, status, Query, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from . import models, schemas, auth, database
from .google_sheets import GoogleSheetsSync
from datetime import timedelta, date, time, datetime
from typing import List
import os
import re
import uuid

# Initialize templates
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "../../templates"))

app = FastAPI(title="University Attendance System")
VALID_STUDY_STATUSES = {"studying", "inactive"}

# Mount static files
app.mount("/static", StaticFiles(directory="./static"), name="static")

# Initialize Google Sheets sync
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1nJ7-eGB-gYJNgm5CTqodenKnUSQlhMeFs2gVLuyxEsM/edit?gid=1653075363#gid=1653075363"
try:
    google_sheets_sync = GoogleSheetsSync(GOOGLE_SHEET_URL)
except Exception as e:
    print(f"Google Sheets sync initialization failed: {e}")
    google_sheets_sync = None

# Создаём таблицы при старте (только для dev!)
@app.on_event("startup")
def startup():
    database.ensure_compatible_schema()
    models.Base.metadata.create_all(bind=database.engine)
    # Schedule is displayed directly from Google Sheets in UI section "Расписание".
    # Avoid DB sync on startup to prevent showing stale or incorrectly parsed rows.


def get_current_user_role(login: str = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    """Get the current user's role"""
    user = db.query(models.User).filter(models.User.login == login).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def check_role_access(current_user: models.User, required_roles: List[str]):
    """Check if user has required role"""
    if current_user.role not in required_roles:
        raise HTTPException(status_code=403, detail="Access denied")


def ensure_default_group(db: Session) -> models.Group:
    group = db.query(models.Group).filter(models.Group.name == "0").first()
    if group:
        return group
    group = models.Group(name="0")
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


def normalize_user_group_and_teacher_links(db: Session, user: models.User, teacher_group_ids: List[int] | None = None):
    default_group = ensure_default_group(db)

    if user.role in {"admin", "dean"}:
        user.group_id = default_group.id
        user.taught_groups = []
        user.is_monitor = False
    elif user.role == "teacher":
        user.group_id = default_group.id
        if teacher_group_ids is not None:
            groups = db.query(models.Group).filter(models.Group.id.in_(teacher_group_ids)).all() if teacher_group_ids else []
            user.taught_groups = groups
        user.is_monitor = False
    else:
        if user.group_id is None:
            raise HTTPException(status_code=400, detail="Student/monitor must have group")


def serialize_user(user: models.User) -> schemas.User:
    teacher_group_ids = [group.id for group in user.taught_groups] if user.role == "teacher" else []
    return schemas.User(
        id=user.id,
        personal_id=user.personal_id,
        full_name=user.full_name,
        login=user.login,
        role=user.role,
        group_id=user.group_id,
        group_name=user.group.name if user.group else None,
        is_monitor=user.is_monitor,
        email=user.email,
        birth_date=user.birth_date,
        direction_code=user.direction_code,
        direction_name=user.direction_name,
        faculty=user.faculty,
        study_status=user.study_status,
        stream_year=user.stream_year,
        education_form=user.education_form,
        teacher_group_ids=teacher_group_ids,
    )


def can_mark_attendance(current_user: models.User, student: models.User) -> bool:
    if current_user.role in {"admin", "dean", "teacher"}:
        return True

    is_student_monitor = current_user.role == "student" and bool(current_user.is_monitor)
    is_legacy_monitor_role = current_user.role == "monitor"
    if is_student_monitor or is_legacy_monitor_role:
        return current_user.group_id is not None and current_user.group_id == student.group_id

    return False


def check_student_access(current_user: models.User, student_id: int, db: Session):
    """Check if current user can access student data based on role"""
    student = db.query(models.User).filter(models.User.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if current_user.role in {"admin", "dean"}:
        return True

    if current_user.role == "teacher":
        teacher_groups_ids = [group.id for group in current_user.taught_groups]
        if student.group_id in teacher_groups_ids:
            return True
        raise HTTPException(status_code=403, detail="Access denied: Student not in your groups")

    if can_mark_attendance(current_user, student):
        return True

    if current_user.role == "student" and current_user.id == student_id:
        return True

    raise HTTPException(status_code=403, detail="Access denied")


def check_schedule_access(current_user: models.User, schedule: models.Schedule, db: Session):
    """Check if current user can access a schedule based on role"""
    if current_user.role in {"admin", "dean"}:
        return True

    if current_user.role == "teacher":
        teacher_groups_ids = [group.id for group in current_user.taught_groups]
        if schedule.group_id in teacher_groups_ids:
            return True
        raise HTTPException(status_code=403, detail="Access denied: Schedule not in your groups")

    is_student_monitor = current_user.role == "student" and bool(current_user.is_monitor)
    if current_user.role == "monitor" or is_student_monitor:
        if schedule.group_id != current_user.group_id:
            raise HTTPException(status_code=403, detail="Access denied: Schedule not in your group")
        return True

    if current_user.role == "student":
        if schedule.group_id != current_user.group_id:
            raise HTTPException(status_code=403, detail="Access denied: Schedule not in your group")
        return True

    raise HTTPException(status_code=403, detail="Access denied")


@app.post("/register", response_model=schemas.User)
def register(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    existing_user = db.query(models.User).filter(models.User.login == user.login).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Login already registered")
    if user.personal_id:
        pid_exists = db.query(models.User).filter(models.User.personal_id == user.personal_id).first()
        if pid_exists:
            raise HTTPException(status_code=400, detail="Personal ID already exists")
    if user.study_status not in VALID_STUDY_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid study status")

    db_user = models.User(
        full_name=user.full_name,
        login=user.login,
        password_hash=auth.hash_password(user.password),
        role=user.role,
        group_id=user.group_id,
        is_monitor=user.is_monitor,
        email=user.email,
        birth_date=user.birth_date,
        direction_code=user.direction_code,
        direction_name=user.direction_name,
        faculty=user.faculty,
        study_status=user.study_status,
        stream_year=user.stream_year,
        education_form=user.education_form,
        personal_id=(user.personal_id or f"U-{uuid.uuid4().hex[:10]}"),
    )
    db.add(db_user)
    db.flush()

    normalize_user_group_and_teacher_links(db, db_user, user.teacher_group_ids)

    db.commit()
    db.refresh(db_user)
    return serialize_user(db_user)


from fastapi import Form
from pydantic import BaseModel

class LoginRequest(BaseModel):
    login: str
    password: str

@app.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.login == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Неверный логин или пароль")
    if user.study_status == "inactive":
        raise HTTPException(status_code=403, detail="Пользователь неактивен. Вход запрещен")
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.login, "role": user.role}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Create a new endpoint that accepts JSON data
@app.post("/api/login", response_model=schemas.Token)
def api_login(
    login_request: LoginRequest,
    db: Session = Depends(database.get_db)
):
    """Login endpoint that accepts JSON data"""
    user = db.query(models.User).filter(models.User.login == login_request.login).first()
    if not user or not auth.verify_password(login_request.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Неверный логин или пароль")
    if user.study_status == "inactive":
        raise HTTPException(status_code=403, detail="Пользователь неактивен. Вход запрещен")
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.login, "role": user.role}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.put("/users/{user_id}/password/change")
def change_password(
    user_id: int,
    user_update: schemas.PasswordChange,
    current_user: models.User = Depends(get_current_user_role),
    db: Session = Depends(database.get_db)
):
    if user_update.user_id != user_id:
        raise HTTPException(status_code=400, detail="User ID mismatch")

    if current_user.id != user_id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    if not auth.verify_password(user_update.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Неверный старый пароль")

    target_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    target_user.password_hash = auth.hash_password(user_update.new_password)
    db.commit()

    return {"message": "Password updated successfully"}


@app.put("/users/me/password")
def change_own_password(
    password_change: schemas.OwnPasswordChange,
    current_user: models.User = Depends(get_current_user_role),
    db: Session = Depends(database.get_db)
):
    # Verify old password
    if not auth.verify_password(password_change.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Неверный старый пароль")
    
    # Update password
    current_user.password_hash = auth.hash_password(password_change.new_password)
    db.commit()
    
    return {"message": "Password updated successfully"}


@app.get("/users/me", response_model=schemas.User)
def read_users_me(current_user: models.User = Depends(get_current_user_role)):
    return serialize_user(current_user)


@app.get("/api/users/me", response_model=schemas.User)
def read_api_users_me(current_user: models.User = Depends(get_current_user_role)):
    return read_users_me(current_user)


@app.get("/users/{user_id}", response_model=schemas.User)
def get_user(user_id: int, current_user: models.User = Depends(get_current_user_role), db: Session = Depends(database.get_db)):
    check_role_access(current_user, ["admin", "dean"])
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return serialize_user(user)


@app.get("/users", response_model=List[schemas.User])
def get_users(
    skip: int = 0, 
    limit: int = 100, 
    role_filter: str = Query(None, description="Filter by role"),
    group_id: int = Query(None, description="Filter by group ID"),
    current_user: models.User = Depends(get_current_user_role), 
    db: Session = Depends(database.get_db)
):
    check_role_access(current_user, ["admin", "dean", "teacher", "monitor"])
    
    query = db.query(models.User)
    
    if role_filter:
        query = query.filter(models.User.role == role_filter)
    
    if group_id:
        query = query.filter(models.User.group_id == group_id)
    
    users = query.offset(skip).limit(limit).all()
    return [serialize_user(user) for user in users]


@app.put("/users/{user_id}", response_model=schemas.User)
def update_user(
    user_id: int,
    user_update: schemas.UserUpdate,
    current_user: models.User = Depends(get_current_user_role),
    db: Session = Depends(database.get_db)
):
    check_role_access(current_user, ["admin"])

    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_update.full_name is not None:
        db_user.full_name = user_update.full_name
    if user_update.login is not None:
        existing_user = db.query(models.User).filter(models.User.login == user_update.login).first()
        if existing_user and existing_user.id != user_id:
            raise HTTPException(status_code=400, detail="Login already registered")
        db_user.login = user_update.login
    if user_update.role is not None:
        db_user.role = user_update.role
    if user_update.group_id is not None:
        db_user.group_id = user_update.group_id
    if user_update.is_monitor is not None:
        db_user.is_monitor = user_update.is_monitor
    if user_update.email is not None:
        db_user.email = user_update.email
    if user_update.birth_date is not None:
        db_user.birth_date = user_update.birth_date
    if user_update.direction_code is not None:
        db_user.direction_code = user_update.direction_code
    if user_update.direction_name is not None:
        db_user.direction_name = user_update.direction_name
    if user_update.faculty is not None:
        db_user.faculty = user_update.faculty
    if user_update.study_status is not None:
        if user_update.study_status not in VALID_STUDY_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid study status")
        db_user.study_status = user_update.study_status
    if user_update.stream_year is not None:
        db_user.stream_year = user_update.stream_year
    if user_update.education_form is not None:
        db_user.education_form = user_update.education_form
    if user_update.personal_id is not None:
        pid_exists = db.query(models.User).filter(models.User.personal_id == user_update.personal_id, models.User.id != user_id).first()
        if pid_exists:
            raise HTTPException(status_code=400, detail="Personal ID already exists")
        db_user.personal_id = user_update.personal_id
    if user_update.password is not None:
        db_user.password_hash = auth.hash_password(user_update.password)

    normalize_user_group_and_teacher_links(db, db_user, user_update.teacher_group_ids)

    db.commit()
    db.refresh(db_user)
    return serialize_user(db_user)


@app.delete("/users/{user_id}")
def delete_user(user_id: int, current_user: models.User = Depends(get_current_user_role), db: Session = Depends(database.get_db)):
    check_role_access(current_user, ["admin"])
    
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(db_user)
    db.commit()
    return {"message": "User deleted successfully"}


@app.get("/groups", response_model=List[schemas.Group])
def get_groups(current_user: models.User = Depends(get_current_user_role), db: Session = Depends(database.get_db)):
    groups = db.query(models.Group).all()
    return [schemas.Group(id=group.id, name=group.name) for group in groups]


@app.post("/groups", response_model=schemas.Group)
def create_group(group: schemas.GroupCreate, current_user: models.User = Depends(get_current_user_role), db: Session = Depends(database.get_db)):
    check_role_access(current_user, ["admin"])

    exists = db.query(models.Group).filter(models.Group.name == group.name).first()
    if exists:
        raise HTTPException(status_code=400, detail="Group already exists")

    db_group = models.Group(name=group.name)
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return schemas.Group(id=db_group.id, name=db_group.name)

@app.delete("/groups/{group_id}")
def delete_group(
    group_id: int,
    current_user: models.User = Depends(get_current_user_role),
    db: Session = Depends(database.get_db),
):
    check_role_access(current_user, ["admin"])

    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if group.name == "0":
        raise HTTPException(status_code=400, detail="Default group cannot be deleted")

    has_users = db.query(models.User).filter(models.User.group_id == group_id).first()
    if has_users:
        raise HTTPException(status_code=400, detail="Cannot delete group with users")

    has_schedule = db.query(models.Schedule).filter(models.Schedule.group_id == group_id).first()
    if has_schedule:
        raise HTTPException(status_code=400, detail="Cannot delete group with schedule")

    db.execute(models.group_subjects.delete().where(models.group_subjects.c.group_id == group_id))
    db.execute(models.teacher_groups.delete().where(models.teacher_groups.c.group_id == group_id))
    db.delete(group)
    db.commit()
    return {"message": "Group deleted"}



@app.get("/subjects", response_model=List[schemas.Subject])
def get_subjects(current_user: models.User = Depends(get_current_user_role), db: Session = Depends(database.get_db)):
    subjects = db.query(models.Subject).all()
    return [schemas.Subject(id=subj.id, name=subj.name, teacher_id=subj.teacher_id) for subj in subjects]


@app.post("/subjects", response_model=schemas.Subject)
def create_subject(subject: schemas.SubjectCreate, current_user: models.User = Depends(get_current_user_role), db: Session = Depends(database.get_db)):
    check_role_access(current_user, ["admin"])
    
    db_subject = models.Subject(name=subject.name, teacher_id=subject.teacher_id)
    db.add(db_subject)
    db.commit()
    db.refresh(db_subject)
    return schemas.Subject(id=db_subject.id, name=db_subject.name, teacher_id=db_subject.teacher_id)


@app.get("/group-subjects", response_model=List[schemas.GroupSubjectView])
def get_group_subjects_view(
    current_user: models.User = Depends(get_current_user_role),
    db: Session = Depends(database.get_db)
):
    query = (
        db.query(models.Group.id, models.Group.name, models.Subject.id, models.Subject.name, models.Subject.teacher_id, models.User.full_name)
        .join(models.group_subjects, models.group_subjects.c.group_id == models.Group.id)
        .join(models.Subject, models.Subject.id == models.group_subjects.c.subject_id)
        .outerjoin(models.User, models.User.id == models.Subject.teacher_id)
    )

    if current_user.role in {"student", "monitor"}:
        query = query.filter(models.Group.id == current_user.group_id)
    elif current_user.role == "teacher":
        query = query.filter(models.Subject.teacher_id == current_user.id)
    # dean/admin see all

    rows = query.order_by(models.Group.name.asc(), models.Subject.name.asc()).all()
    return [
        schemas.GroupSubjectView(
            group_id=row[0],
            group_name=row[1],
            subject_id=row[2],
            subject_name=row[3],
            teacher_id=row[4],
            teacher_name=row[5],
        )
        for row in rows
    ]


@app.post("/group-subjects", response_model=schemas.GroupSubjectView)
def bind_group_subject(
    payload: schemas.GroupSubjectBind,
    current_user: models.User = Depends(get_current_user_role),
    db: Session = Depends(database.get_db),
):
    check_role_access(current_user, ["admin"])

    group = db.query(models.Group).filter(models.Group.id == payload.group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    subject = db.query(models.Subject).filter(models.Subject.id == payload.subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    if payload.teacher_id is not None:
        teacher = db.query(models.User).filter(models.User.id == payload.teacher_id, models.User.role == "teacher").first()
        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher not found")
        subject.teacher_id = teacher.id

        teacher_group_link = db.execute(
            models.teacher_groups.select().where(
                (models.teacher_groups.c.teacher_id == teacher.id)
                & (models.teacher_groups.c.group_id == payload.group_id)
            )
        ).first()
        if not teacher_group_link:
            db.execute(models.teacher_groups.insert().values(teacher_id=teacher.id, group_id=payload.group_id))

    exists = db.execute(
        models.group_subjects.select().where(
            (models.group_subjects.c.group_id == payload.group_id)
            & (models.group_subjects.c.subject_id == payload.subject_id)
        )
    ).first()
    if not exists:
        db.execute(models.group_subjects.insert().values(group_id=payload.group_id, subject_id=payload.subject_id))

    db.commit()
    db.refresh(subject)

    teacher_name = None
    if subject.teacher_id:
        teacher_obj = db.query(models.User).filter(models.User.id == subject.teacher_id).first()
        teacher_name = teacher_obj.full_name if teacher_obj else None

    return schemas.GroupSubjectView(
        group_id=group.id,
        group_name=group.name,
        subject_id=subject.id,
        subject_name=subject.name,
        teacher_id=subject.teacher_id,
        teacher_name=teacher_name,
    )


@app.delete("/group-subjects")
def unbind_group_subject(
    group_id: int = Query(...),
    subject_id: int = Query(...),
    current_user: models.User = Depends(get_current_user_role),
    db: Session = Depends(database.get_db),
):
    check_role_access(current_user, ["admin"])

    deleted = db.execute(
        models.group_subjects.delete().where(
            (models.group_subjects.c.group_id == group_id)
            & (models.group_subjects.c.subject_id == subject_id)
        )
    )
    if deleted.rowcount == 0:
        raise HTTPException(status_code=404, detail="Binding not found")

    subject = db.query(models.Subject).filter(models.Subject.id == subject_id).first()
    if subject and subject.teacher_id:
        remaining = db.query(models.Subject.id).join(
            models.group_subjects, models.group_subjects.c.subject_id == models.Subject.id
        ).filter(
            models.Subject.teacher_id == subject.teacher_id,
            models.group_subjects.c.group_id == group_id,
        ).first()
        if not remaining:
            db.execute(
                models.teacher_groups.delete().where(
                    (models.teacher_groups.c.teacher_id == subject.teacher_id)
                    & (models.teacher_groups.c.group_id == group_id)
                )
            )

    db.commit()
    return {"message": "Binding removed"}


@app.get("/schedule", response_model=List[schemas.Schedule])
def get_schedule(
    group_id: int = Query(None, description="Filter by group ID"),
    date_from: date = Query(None, description="Filter from date"),
    date_to: date = Query(None, description="Filter to date"),
    current_user: models.User = Depends(get_current_user_role),
    db: Session = Depends(database.get_db)
):
    query = db.query(models.Schedule)
    
    # Apply filters based on user role
    if current_user.role == "student" or current_user.role == "monitor":
        query = query.filter(models.Schedule.group_id == current_user.group_id)
    elif current_user.role == "teacher":
        teacher_group_ids = [g.id for g in current_user.taught_groups]
        query = query.filter(models.Schedule.group_id.in_(teacher_group_ids))
    # Admin and dean can see all schedules
    
    if group_id:
        query = query.filter(models.Schedule.group_id == group_id)
    
    if date_from:
        query = query.filter(models.Schedule.date >= date_from)
    
    if date_to:
        query = query.filter(models.Schedule.date <= date_to)
    
    schedules = query.all()
    return [
        schemas.Schedule(
            id=sched.id,
            subject_id=sched.subject_id,
            group_id=sched.group_id,
            date=sched.date,
            start_time=sched.start_time,
            end_time=sched.end_time,
            teacher_id=sched.teacher_id
        ) for sched in schedules
    ]


@app.post("/schedule", response_model=schemas.Schedule)
def create_schedule(schedule: schemas.ScheduleCreate, current_user: models.User = Depends(get_current_user_role), db: Session = Depends(database.get_db)):
    check_role_access(current_user, ["admin"])
    
    db_schedule = models.Schedule(**schedule.dict())
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)
    return schemas.Schedule(
        id=db_schedule.id,
        subject_id=db_schedule.subject_id,
        group_id=db_schedule.group_id,
        date=db_schedule.date,
        start_time=db_schedule.start_time,
        end_time=db_schedule.end_time,
        teacher_id=db_schedule.teacher_id
    )


@app.get("/attendance", response_model=List[schemas.Attendance])
def get_attendance(
    schedule_id: int = Query(None, description="Filter by schedule ID"),
    user_id: int = Query(None, description="Filter by user ID"),
    current_user: models.User = Depends(get_current_user_role),
    db: Session = Depends(database.get_db)
):
    query = db.query(models.Attendance)
    
    # Students can only see their own attendance
    if current_user.role == "student":
        query = query.filter(models.Attendance.user_id == current_user.id)
    elif current_user.role == "monitor":
        # Monitors can only see attendance for their group
        query = query.join(models.User).filter(models.User.group_id == current_user.group_id)
    elif current_user.role == "teacher":
        # Teachers can see attendance for their groups
        teacher_group_ids = [g.id for g in current_user.taught_groups]
        query = query.join(models.User).filter(models.User.group_id.in_(teacher_group_ids))
    # Admin and dean can see all attendance
    
    if schedule_id:
        query = query.filter(models.Attendance.schedule_id == schedule_id)
    
    if user_id:
        query = query.filter(models.Attendance.user_id == user_id)
    
    attendances = query.all()
    return [
        schemas.Attendance(
            id=att.id,
            schedule_id=att.schedule_id,
            user_id=att.user_id,
            status=att.status
        ) for att in attendances
    ]


@app.post("/attendance", response_model=schemas.Attendance)
def create_attendance(attendance: schemas.AttendanceCreate, current_user: models.User = Depends(get_current_user_role), db: Session = Depends(database.get_db)):
    # Check access permissions
    schedule = db.query(models.Schedule).filter(models.Schedule.id == attendance.schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    check_schedule_access(current_user, schedule, db)
    
    student = db.query(models.User).filter(models.User.id == attendance.user_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    check_student_access(current_user, attendance.user_id, db)
    
    # Check if attendance already exists
    existing_attendance = db.query(models.Attendance).filter(
        models.Attendance.schedule_id == attendance.schedule_id,
        models.Attendance.user_id == attendance.user_id
    ).first()
    
    if existing_attendance:
        # Update existing attendance
        existing_attendance.status = attendance.status
        db.commit()
        db.refresh(existing_attendance)
        return schemas.Attendance(
            id=existing_attendance.id,
            schedule_id=existing_attendance.schedule_id,
            user_id=existing_attendance.user_id,
            status=existing_attendance.status
        )
    else:
        # Create new attendance
        db_attendance = models.Attendance(**attendance.dict())
        db.add(db_attendance)
        db.commit()
        db.refresh(db_attendance)
        return schemas.Attendance(
            id=db_attendance.id,
            schedule_id=db_attendance.schedule_id,
            user_id=db_attendance.user_id,
            status=db_attendance.status
        )


@app.put("/attendance/{attendance_id}", response_model=schemas.Attendance)
def update_attendance(attendance_id: int, attendance_update: schemas.AttendanceUpdate, current_user: models.User = Depends(get_current_user_role), db: Session = Depends(database.get_db)):
    db_attendance = db.query(models.Attendance).filter(models.Attendance.id == attendance_id).first()
    if not db_attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    
    schedule = db.query(models.Schedule).filter(models.Schedule.id == db_attendance.schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    check_schedule_access(current_user, schedule, db)
    check_student_access(current_user, db_attendance.user_id, db)
    
    db_attendance.status = attendance_update.status
    db.commit()
    db.refresh(db_attendance)
    return schemas.Attendance(
        id=db_attendance.id,
        schedule_id=db_attendance.schedule_id,
        user_id=db_attendance.user_id,
        status=db_attendance.status
    )


@app.get("/student-schedule/{student_id}")
def get_student_schedule(student_id: int, current_user: models.User = Depends(get_current_user_role), db: Session = Depends(database.get_db)):
    # Check if current user can access this student's schedule
    check_student_access(current_user, student_id, db)
    
    student = db.query(models.User).filter(models.User.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Get schedule for the student's group
    schedules = db.query(models.Schedule).filter(models.Schedule.group_id == student.group_id).all()
    
    return [
        {
            "id": sched.id,
            "subject_id": sched.subject_id,
            "group_id": sched.group_id,
            "date": sched.date,
            "start_time": sched.start_time,
            "end_time": sched.end_time,
            "teacher_id": sched.teacher_id
        } for sched in schedules
    ]




def is_monitor_actor(current_user: models.User) -> bool:
    return current_user.role == "monitor" or (current_user.role == "student" and bool(current_user.is_monitor))


def can_manage_subject_attendance(current_user: models.User, group_id: int) -> bool:
    if current_user.role in {"admin", "dean", "teacher"}:
        return True
    if is_monitor_actor(current_user):
        return current_user.group_id == group_id
    return False


@app.get("/attendance/subject/{subject_id}/matrix")
def get_subject_attendance_matrix(
    subject_id: int,
    group_id: int = Query(..., description="Group ID"),
    current_user: models.User = Depends(get_current_user_role),
    db: Session = Depends(database.get_db),
):
    if not can_manage_subject_attendance(current_user, group_id):
        raise HTTPException(status_code=403, detail="Access denied")

    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    subject = db.query(models.Subject).filter(models.Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    schedules = (
        db.query(models.Schedule)
        .filter(models.Schedule.subject_id == subject_id, models.Schedule.group_id == group_id)
        .order_by(models.Schedule.date.asc(), models.Schedule.start_time.asc(), models.Schedule.id.asc())
        .all()
    )

    students = (
        db.query(models.User)
        .filter(models.User.group_id == group_id, models.User.role.in_(["student", "monitor"]))
        .order_by(models.User.full_name.asc())
        .all()
    )

    attendance_rows = (
        db.query(models.Attendance)
        .join(models.Schedule, models.Schedule.id == models.Attendance.schedule_id)
        .filter(models.Schedule.subject_id == subject_id, models.Schedule.group_id == group_id)
        .all()
    )

    status_map = {}
    for att in attendance_rows:
        status_map[(att.user_id, att.schedule_id)] = att.status

    return {
        "subject": {"id": subject.id, "name": subject.name},
        "group": {"id": group.id, "name": group.name},
        "dates": [
            {
                "schedule_id": sch.id,
                "date": sch.date.isoformat(),
                "time": sch.start_time.strftime("%H:%M") if sch.start_time else None,
            }
            for sch in schedules
        ],
        "students": [
            {
                "id": st.id,
                "full_name": st.full_name,
                "is_monitor": bool(st.is_monitor),
                "attendance": {
                    str(sch.id): status_map.get((st.id, sch.id)) for sch in schedules
                },
            }
            for st in students
        ],
    }


@app.post("/attendance/subject/{subject_id}/sessions")
def add_subject_session(
    subject_id: int,
    group_id: int = Query(..., description="Group ID"),
    session_date: date = Query(..., description="Session date"),
    session_time: str | None = Query(None, description="Session time HH:MM"),
    current_user: models.User = Depends(get_current_user_role),
    db: Session = Depends(database.get_db),
):
    if not can_manage_subject_attendance(current_user, group_id):
        raise HTTPException(status_code=403, detail="Access denied")

    if is_monitor_actor(current_user) and session_date < date.today():
        raise HTTPException(status_code=403, detail="Monitor cannot add past sessions")

    parsed_time = None
    if session_time:
        try:
            parsed_time = datetime.strptime(session_time, "%H:%M").time()
        except ValueError:
            raise HTTPException(status_code=400, detail="session_time must be in HH:MM format")

    template_schedule = (
        db.query(models.Schedule)
        .filter(models.Schedule.subject_id == subject_id, models.Schedule.group_id == group_id)
        .order_by(models.Schedule.date.desc())
        .first()
    )

    default_start = template_schedule.start_time if template_schedule and template_schedule.start_time else time(9, 0)
    default_end = template_schedule.end_time if template_schedule and template_schedule.end_time else time(10, 30)
    default_teacher_id = template_schedule.teacher_id if template_schedule else None

    effective_start = parsed_time or default_start

    exists = (
        db.query(models.Schedule)
        .filter(
            models.Schedule.subject_id == subject_id,
            models.Schedule.group_id == group_id,
            models.Schedule.date == session_date,
            models.Schedule.start_time == effective_start,
        )
        .first()
    )
    if exists:
        return {"message": "Session already exists", "schedule_id": exists.id}

    schedule = models.Schedule(
        subject_id=subject_id,
        group_id=group_id,
        date=session_date,
        start_time=effective_start,
        end_time=default_end,
        teacher_id=default_teacher_id,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return {"message": "Session created", "schedule_id": schedule.id}


@app.put("/attendance/subject/{subject_id}/mark")
def mark_subject_attendance(
    subject_id: int,
    group_id: int = Query(..., description="Group ID"),
    schedule_id: int = Query(..., description="Schedule ID"),
    user_id: int = Query(..., description="Student user ID"),
    status_value: str = Query(..., description="present|absent"),
    current_user: models.User = Depends(get_current_user_role),
    db: Session = Depends(database.get_db),
):
    if status_value not in {"present", "absent"}:
        raise HTTPException(status_code=400, detail="status_value must be present or absent")

    if not can_manage_subject_attendance(current_user, group_id):
        raise HTTPException(status_code=403, detail="Access denied")

    schedule = db.query(models.Schedule).filter(models.Schedule.id == schedule_id).first()
    if not schedule or schedule.subject_id != subject_id or schedule.group_id != group_id:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if is_monitor_actor(current_user) and schedule.date < date.today():
        raise HTTPException(status_code=403, detail="Monitor cannot edit past attendance")

    student = db.query(models.User).filter(models.User.id == user_id).first()
    if not student or student.group_id != group_id:
        raise HTTPException(status_code=404, detail="Student not found in group")

    att = db.query(models.Attendance).filter(
        models.Attendance.schedule_id == schedule_id,
        models.Attendance.user_id == user_id,
    ).first()

    if att:
        att.status = status_value
    else:
        att = models.Attendance(schedule_id=schedule_id, user_id=user_id, status=status_value)
        db.add(att)

    db.commit()
    db.refresh(att)
    return {"message": "Attendance updated", "status": att.status}


@app.get("/my-attendance")
def get_my_attendance(current_user: models.User = Depends(get_current_user_role), db: Session = Depends(database.get_db)):
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Only students can access this endpoint")
    
    attendances = db.query(models.Attendance).filter(models.Attendance.user_id == current_user.id).all()
    
    return [
        {
            "id": att.id,
            "schedule_id": att.schedule_id,
            "user_id": att.user_id,
            "status": att.status,
            "updated_at": att.updated_at
        } for att in attendances
    ]


@app.post("/sync-schedule")
def sync_schedule(current_user: models.User = Depends(get_current_user_role), db: Session = Depends(database.get_db)):
    check_role_access(current_user, ["admin"])
    
    try:
        google_sheets_sync.sync_schedule_with_db(db)
        return {"message": "Schedule successfully synced from Google Sheets"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error syncing schedule: {str(e)}")


# @app.get("/app", response_class=HTMLResponse)
# def app_home(request: Request):
#     """Main application page after login"""
#     return templates.TemplateResponse("app_home.html", {"request": request})


@app.put("/users/me/profile", response_model=schemas.User)
def update_my_profile(
    profile_update: schemas.UserProfileUpdate,
    current_user: models.User = Depends(get_current_user_role),
    db: Session = Depends(database.get_db)
):
    current_user.birth_date = profile_update.birth_date
    db.commit()
    db.refresh(current_user)
    return serialize_user(current_user)


@app.get("/profile", response_class=HTMLResponse)
def profile(request: Request):
    """User profile page"""
    return templates.TemplateResponse("profile.html", {"request": request})


@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})




@app.get("/app", response_class=HTMLResponse)
def app_home(request: Request):
    return templates.TemplateResponse("app_home.html", {"request": request})


@app.get("/schedule-page", response_class=HTMLResponse)
def schedule_page(request: Request):
    source_url = GOOGLE_SHEET_URL
    embed_url = source_url.replace("/edit?", "/pubhtml?") + "&single=true&widget=true&headers=false"
    return templates.TemplateResponse(
        "schedule_page.html",
        {
            "request": request,
            "source_url": source_url,
            "embed_url": embed_url,
        },
    )


@app.get("/attendance/mark", response_class=HTMLResponse)
def attendance_mark_page(request: Request):
    return templates.TemplateResponse("attendance_mark.html", {"request": request})


@app.get("/attendance/subject/{subject_id}", response_class=HTMLResponse)
def attendance_subject_page(subject_id: int, request: Request, group_id: int = Query(...)):
    return templates.TemplateResponse("attendance_subject.html", {"request": request, "subject_id": subject_id, "group_id": group_id})


@app.get("/admin/groups/manage", response_class=HTMLResponse)
def admin_groups_manage_page(request: Request):
    return templates.TemplateResponse("admin_users.html", {"request": request})


@app.get("/admin/users", response_class=HTMLResponse)
def admin_users_page(request: Request):
    return templates.TemplateResponse("admin_users.html", {"request": request})
