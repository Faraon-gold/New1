from fastapi import FastAPI, Depends, HTTPException, status, Query, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from . import models, schemas, auth, database
from .google_sheets import GoogleSheetsSync
from datetime import timedelta, date
from typing import List
import os

# Initialize templates
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "../../templates"))

app = FastAPI(title="University Attendance System")

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
    # Sync schedule from Google Sheets on startup
    if google_sheets_sync:
        db = next(database.get_db())
        try:
            google_sheets_sync.sync_schedule_with_db(db)
        except Exception as e:
            print(f"Error syncing schedule from Google Sheets: {e}")
        finally:
            db.close()
    else:
        print("Skipping Google Sheets sync due to missing credentials")


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
    # Check if user already exists
    existing_user = db.query(models.User).filter(models.User.login == user.login).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Login already registered")
    
    # Hash the password
    hashed_password = auth.hash_password(user.password)
    
    # Create new user
    db_user = models.User(
        full_name=user.full_name,
        login=user.login,
        password_hash=hashed_password,
        role=user.role,
        group_id=user.group_id,
        is_monitor=user.is_monitor
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


from fastapi import Form
from pydantic import BaseModel

class LoginRequest(BaseModel):
    login: str
    password: str

@app.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.login == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid credentials")
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
        raise HTTPException(status_code=400, detail="Invalid credentials")
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.login, "role": user.role}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.put("/users/{user_id}/password")
def change_password(
    user_update: schemas.PasswordChange,
    current_user: models.User = Depends(get_current_user_role),
    db: Session = Depends(database.get_db)
):
    # Check if user is updating their own password or is admin
    if current_user.id != user_update.user_id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Verify old password
    if not auth.verify_password(user_update.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect old password")
    
    # Update password
    current_user.password_hash = auth.hash_password(user_update.new_password)
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
        raise HTTPException(status_code=400, detail="Incorrect old password")
    
    # Update password
    current_user.password_hash = auth.hash_password(password_change.new_password)
    db.commit()
    
    return {"message": "Password updated successfully"}


@app.get("/users/me", response_model=schemas.User)
def read_users_me(current_user: models.User = Depends(get_current_user_role)):
    return schemas.User(
        id=current_user.id,
        full_name=current_user.full_name,
        login=current_user.login,
        role=current_user.role,
        group_id=current_user.group_id,
        is_monitor=current_user.is_monitor,
    )


@app.get("/api/users/me", response_model=schemas.User)
def read_api_users_me(current_user: models.User = Depends(get_current_user_role)):
    return read_users_me(current_user)


@app.get("/users/{user_id}", response_model=schemas.User)
def get_user(user_id: int, current_user: models.User = Depends(get_current_user_role), db: Session = Depends(database.get_db)):
    check_role_access(current_user, ["admin", "dean"])
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return schemas.User(
        id=user.id,
        full_name=user.full_name,
        login=user.login,
        role=user.role,
        group_id=user.group_id,
        is_monitor=user.is_monitor
    )


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
    return [
        schemas.User(
            id=user.id,
            full_name=user.full_name,
            login=user.login,
            role=user.role,
            group_id=user.group_id,
            is_monitor=user.is_monitor,
        ) for user in users
    ]


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
    
    # Update fields if provided
    if user_update.full_name is not None:
        db_user.full_name = user_update.full_name
    if user_update.login is not None:
        # Check if new login is already taken
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
    if user_update.password is not None:
        db_user.password_hash = auth.hash_password(user_update.password)

    db.commit()
    db.refresh(db_user)
    return schemas.User(
        id=db_user.id,
        full_name=db_user.full_name,
        login=db_user.login,
        role=db_user.role,
        group_id=db_user.group_id,
        is_monitor=db_user.is_monitor,
    )


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
    
    db_group = models.Group(name=group.name)
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return schemas.Group(id=db_group.id, name=db_group.name)


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
    return templates.TemplateResponse("schedule_page.html", {"request": request})


@app.get("/attendance/mark", response_class=HTMLResponse)
def attendance_mark_page(request: Request):
    return templates.TemplateResponse("attendance_mark.html", {"request": request})


@app.get("/admin/users", response_class=HTMLResponse)
def admin_users_page(request: Request):
    return templates.TemplateResponse("admin_users.html", {"request": request})
