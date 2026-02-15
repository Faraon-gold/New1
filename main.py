from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Date, Time, ForeignKey, Enum, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from passlib.context import CryptContext
from datetime import datetime, date, timedelta
import enum
import jwt
from typing import Optional, List
from pydantic import BaseModel
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dateutil import parser
import os

# Настройка приложения FastAPI
app = FastAPI(title="Система учёта посещаемости студентов", version="1.0.0")

# Подключение статических файлов и шаблонов
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Настройка безопасности
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"

# Конфигурация базы данных
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./attendance.db")
if DATABASE_URL.startswith("postgres"):
    engine = create_engine(DATABASE_URL)
else:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Определение перечислимого типа для ролей пользователей
class UserRole(str, enum.Enum):
    student = "student"
    monitor = "monitor"
    teacher = "teacher"
    dean = "dean"
    admin = "admin"

# Определение перечислимого типа для статуса посещения
class AttendanceStatus(str, enum.Enum):
    present = "present"
    absent = "absent"
    late = "late"

# Модель пользователя
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)  # ФИО пользователя
    login = Column(String, unique=True, nullable=False)  # Логин для входа
    password_hash = Column(String, nullable=False)  # Хэш пароля
    role = Column(Enum(UserRole), nullable=False)  # Роль пользователя
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)  # Идентификатор группы
    
    # Связи
    group = relationship("Group", back_populates="students")
    attendances = relationship("Attendance", primaryjoin="User.id==Attendance.user_id", back_populates="user")
    scheduled_classes = relationship("Schedule", back_populates="teacher")

# Модель группы
class Group(Base):
    __tablename__ = "groups"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # Название группы (например, "ИС-201")
    
    # Связи
    students = relationship("User", back_populates="group")
    schedules = relationship("Schedule", back_populates="group")
    teachers = relationship("TeacherGroup", back_populates="group")

# Модель предмета
class Subject(Base):
    __tablename__ = "subjects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # Название предмета
    
    # Связи
    schedules = relationship("Schedule", back_populates="subject")

# Модель расписания
class Schedule(Base):
    __tablename__ = "schedule"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False)  # Дата занятия
    start_time = Column(Time, nullable=False)  # Время начала
    end_time = Column(Time, nullable=False)  # Время окончания
    subject_id = Column(Integer, ForeignKey("subjects.id"))  # ID предмета
    group_id = Column(Integer, ForeignKey("groups.id"))  # ID группы
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # ID преподавателя (опционально)
    
    # Связи
    subject = relationship("Subject", back_populates="schedules")
    group = relationship("Group", back_populates="schedules")
    teacher = relationship("User", back_populates="scheduled_classes")
    attendances = relationship("Attendance", back_populates="schedule")

# Модель посещаемости
class Attendance(Base):
    __tablename__ = "attendance"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))  # ID пользователя
    schedule_id = Column(Integer, ForeignKey("schedule.id"))  # ID расписания
    status = Column(Enum(AttendanceStatus), nullable=False)  # Статус посещения
    updated_at = Column(DateTime, default=datetime.utcnow)  # Время последнего обновления
    updated_by = Column(Integer, ForeignKey("users.id"))  # Кто обновил статус
    
    # Связи
    user = relationship("User", foreign_keys=[user_id], back_populates="attendances")
    schedule = relationship("Schedule", back_populates="attendances")
    updater = relationship("User", foreign_keys=[updated_by])

# Модель связи преподавателей и групп
class TeacherGroup(Base):
    __tablename__ = "teacher_groups"
    
    teacher_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id"), primary_key=True)
    
    # Связи
    teacher = relationship("User")
    group = relationship("Group", back_populates="teachers")

# Pydantic-схемы для валидации данных
class UserCreate(BaseModel):
    full_name: str
    login: str
    password: str
    role: UserRole
    group_id: Optional[int] = None

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    login: Optional[str] = None
    password: Optional[str] = None
    role: Optional[UserRole] = None
    group_id: Optional[int] = None

class LoginRequest(BaseModel):
    login: str
    password: str

class AttendanceUpdate(BaseModel):
    status: AttendanceStatus

# Утилиты для работы с базой данных
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Функции для хэширования и проверки паролей
def verify_password(plain_password, hashed_password):
    # Обрезаем пароль до 72 байт, если он длиннее
    if len(plain_password.encode('utf-8')) > 72:
        plain_password = plain_password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except (ValueError, TypeError):
        # Обрабатываем ошибку bcrypt, если пароль все равно слишком длинный или возникают другие ошибки
        return False

def get_password_hash(password):
    # Обрезаем пароль до 72 байт, если он длиннее
    if len(password.encode('utf-8')) > 72:
        password = password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
    try:
        return pwd_context.hash(password)
    except ValueError:
        # Если пароль не удается хешировать из-за ограничений bcrypt, обрезаем дополнительно
        truncated_pwd = password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
        return pwd_context.hash(truncated_pwd)

# Создание и получение токенов JWT
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=30)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.JWTError:
        return None

# Получение текущего пользователя из токена
async def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return None
    
    payload = decode_access_token(token)
    if not payload or "user_id" not in payload:
        return None
    
    user_id = payload["user_id"]
    user = db.query(User).filter(User.id == user_id).first()
    return user

# Проверка прав доступа
def check_permission(user: User, required_role: UserRole) -> bool:
    """Проверяет, имеет ли пользователь достаточные права"""
    role_hierarchy = {
        "student": 1,
        "monitor": 2,
        "teacher": 3,
        "dean": 4,
        "admin": 5
    }
    
    return role_hierarchy.get(user.role.value, 0) >= role_hierarchy.get(required_role.value, 0)

# Синхронизация с Google Таблицами
def sync_google_sheet():
    """Синхронизирует расписание из Google Таблицы"""
    try:
        # Настройка доступа к Google Таблице
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds_file = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE', 'credentials.json')
        
        if not os.path.exists(creds_file):
            print("Файл учетных данных Google не найден. Пропускаем синхронизацию.")
            return
        
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_file, scope)
        client = gspread.authorize(creds)
        
        # Открытие таблицы
        sheet_url = "https://docs.google.com/spreadsheets/d/1nJ7-eGB-gYJNgm5CTqodenKnUSQlhMeFs2gVLuyxEsM/edit?gid=1653075363#gid=1653075363"
        sheet = client.open_by_url(sheet_url).sheet1
        
        # Получение данных
        records = sheet.get_all_records()
        
        db = SessionLocal()
        try:
            # Очистка существующих записей (по желанию)
            # db.query(Schedule).delete()
            
            # Обработка данных из таблицы
            for record in records:
                # Преобразование даты
                class_date = parser.parse(record.get('date', '')).date()
                
                # Поиск или создание группы
                group_name = record.get('group', '')
                group = db.query(Group).filter(Group.name == group_name).first()
                if not group:
                    group = Group(name=group_name)
                    db.add(group)
                    db.commit()
                    db.refresh(group)
                
                # Поиск или создание предмета
                subject_name = record.get('subject', '')
                subject = db.query(Subject).filter(Subject.name == subject_name).first()
                if not subject:
                    subject = Subject(name=subject_name)
                    db.add(subject)
                    db.commit()
                    db.refresh(subject)
                
                # Поиск или создание преподавателя
                teacher_login = record.get('teacher_login', '')
                teacher = None
                if teacher_login:
                    teacher = db.query(User).filter(
                        User.login == teacher_login,
                        User.role == UserRole.teacher
                    ).first()
                
                # Создание записи расписания
                schedule_entry = Schedule(
                    date=class_date,
                    start_time=parser.parse(record.get('start_time', '00:00')).time(),
                    end_time=parser.parse(record.get('end_time', '00:00')).time(),
                    subject_id=subject.id,
                    group_id=group.id,
                    teacher_id=teacher.id if teacher else None
                )
                
                existing_schedule = db.query(Schedule).filter(
                    Schedule.date == schedule_entry.date,
                    Schedule.start_time == schedule_entry.start_time,
                    Schedule.subject_id == schedule_entry.subject_id,
                    Schedule.group_id == schedule_entry.group_id
                ).first()
                
                if not existing_schedule:
                    db.add(schedule_entry)
            
            db.commit()
            print("Синхронизация с Google Таблицей завершена успешно.")
        except Exception as e:
            print(f"Ошибка при синхронизации с Google Таблицей: {e}")
            db.rollback()
        finally:
            db.close()
    except Exception as e:
        print(f"Ошибка при доступе к Google Таблице: {e}")

def init_sample_data(db: Session):
    """Инициализация начальными данными"""
    try:
        # Создание групп
        if not db.query(Group).count():
            group1 = Group(name="ИС-201")
            group2 = Group(name="ИС-202")
            db.add(group1)
            db.add(group2)
            db.commit()
            db.refresh(group1)
            db.refresh(group2)
            print("Созданы группы: ИС-201, ИС-202")
        
        # Создание предметов
        if not db.query(Subject).count():
            subject1 = Subject(name="Математический анализ")
            subject2 = Subject(name="Программирование")
            subject3 = Subject(name="Физика")
            db.add(subject1)
            db.add(subject2)
            db.add(subject3)
            db.commit()
            db.refresh(subject1)
            db.refresh(subject2)
            db.refresh(subject3)
            print("Созданы предметы: Математический анализ, Программирование, Физика")
        
        # Создание пользователей
        if not db.query(User).count():
            # Получаем ID групп
            group1 = db.query(Group).filter(Group.name == "ИС-201").first()
            group2 = db.query(Group).filter(Group.name == "ИС-202").first()
            
            # Администратор
            admin_user = User(
                full_name="Админ Администратов",
                login="admin",
                password_hash=get_password_hash("admin123"),
                role=UserRole.admin
            )
            
            # Преподаватель
            teacher_user = User(
                full_name="Петр Петров",
                login="teacher",
                password_hash=get_password_hash("teacher123"),
                role=UserRole.teacher
            )
            
            # Староста
            monitor_user = User(
                full_name="Иван Иванов",
                login="monitor",
                password_hash=get_password_hash("monitor123"),
                role=UserRole.monitor,
                group_id=group1.id
            )
            
            # Студент
            student_user = User(
                full_name="Сидор Сидоров",
                login="student",
                password_hash=get_password_hash("student123"),
                role=UserRole.student,
                group_id=group1.id
            )
            
            # Деканат
            dean_user = User(
                full_name="Елена Дмитриева",
                login="dean",
                password_hash=get_password_hash("dean123"),
                role=UserRole.dean
            )
            
            db.add(admin_user)
            db.add(teacher_user)
            db.add(monitor_user)
            db.add(student_user)
            db.add(dean_user)
            db.commit()
            db.refresh(admin_user)
            db.refresh(teacher_user)
            db.refresh(monitor_user)
            db.refresh(student_user)
            db.refresh(dean_user)
            print("Созданы пользователи: админ, преподаватель, староста, студент, деканат")
    
    except Exception as e:
        print(f"Ошибка при инициализации начальных данных: {e}")
        db.rollback()

# Инициализация базы данных при запуске
@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)
    sync_google_sheet()
    # Создаем сессию и вызываем инициализацию начальных данных
    db = SessionLocal()
    try:
        init_sample_data(db)
    finally:
        db.close()

# Маршрут главной страницы (форма входа)
@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# Маршрут аутентификации
@app.post("/login")
async def login(login_request: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.login == login_request.login).first()
    if not user or not verify_password(login_request.password, user.password_hash):
        return JSONResponse(
            status_code=401,
            content={"detail": "Неверный логин или пароль"}
        )
    
    token = create_access_token(data={"user_id": user.id})
    response.set_cookie(key="access_token", value=token, httponly=True)
    return {"success": True, "redirect_url": f"/dashboard/{user.role.value}"}

# Маршрут для проверки авторизации и перенаправления на панель управления
@app.get("/app", response_class=HTMLResponse)
async def app_redirect(request: Request, current_user: User = Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/")
    
    # Перенаправление на соответствующую панель управления в зависимости от роли
    return RedirectResponse(url=f"/dashboard/{current_user.role.value}")

# Маршрут выхода
@app.post("/logout")
async def logout(response: Response):
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token")
    return response

# Маршруты для администратора
@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user or current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    
    users = db.query(User).all()
    groups = db.query(Group).all()
    return templates.TemplateResponse("admin_users.html", {
        "request": request,
        "current_user": current_user,
        "users": users,
        "groups": groups
    })

@app.post("/admin/users/create")
async def create_user(user_data: UserCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user or current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    
    # Проверяем, существует ли пользователь с таким логином
    existing_user = db.query(User).filter(User.login == user_data.login).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Пользователь с таким логином уже существует")
    
    # Создаем нового пользователя
    new_user = User(
        full_name=user_data.full_name,
        login=user_data.login,
        password_hash=get_password_hash(user_data.password),
        role=user_data.role,
        group_id=user_data.group_id
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {"success": True, "message": "Пользователь успешно создан"}

@app.put("/admin/users/{user_id}")
async def update_user(user_id: int, user_data: UserUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user or current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Обновляем данные пользователя
    if user_data.full_name is not None:
        user.full_name = user_data.full_name
    if user_data.login is not None:
        # Проверяем, не занят ли новый логин другим пользователем
        existing_user = db.query(User).filter(
            User.login == user_data.login,
            User.id != user_id
        ).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Пользователь с таким логином уже существует")
        user.login = user_data.login
    if user_data.password is not None:
        user.password_hash = get_password_hash(user_data.password)
    if user_data.role is not None:
        user.role = user_data.role
    if user_data.group_id is not None:
        user.group_id = user_data.group_id
    
    db.commit()
    return {"success": True, "message": "Пользователь успешно обновлён"}

@app.get("/admin/users/{user_id}")
async def get_user(user_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user or current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    return {
        "id": user.id,
        "full_name": user.full_name,
        "login": user.login,
        "role": user.role.value,
        "group_id": user.group_id
    }

@app.delete("/admin/users/{user_id}")
async def delete_user(user_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user or current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Не позволяем удалить самого себя
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя удалить собственный аккаунт")
    
    db.delete(user)
    db.commit()
    return {"success": True, "message": "Пользователь успешно удалён"}

# Маршрут для обновления расписания (доступно только администратору)
@app.post("/admin/sync-schedule")
async def sync_schedule(current_user: User = Depends(get_current_user)):
    if not current_user or current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    
    sync_google_sheet()
    return {"success": True, "message": "Расписание успешно обновлено из Google Таблицы"}

# Маршруты для студентов
@app.get("/dashboard/student", response_class=HTMLResponse)
async def student_dashboard(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user or current_user.role != UserRole.student:
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    
    # Получаем расписание для группы студента
    schedule = db.query(Schedule).filter(Schedule.group_id == current_user.group_id).all()
    
    # Получаем посещаемость студента
    attendances = db.query(Attendance).filter(Attendance.user_id == current_user.id).all()
    
    return templates.TemplateResponse("student_dashboard.html", {
        "request": request,
        "current_user": current_user,
        "schedule": schedule,
        "attendances": attendances
    })

# Маршруты для старост
@app.get("/dashboard/monitor", response_class=HTMLResponse)
async def monitor_dashboard(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user or current_user.role != UserRole.monitor:
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    
    # Получаем студентов своей группы
    students = db.query(User).filter(User.group_id == current_user.group_id).all()
    
    # Получаем сегодняшние занятия для своей группы
    today = date.today()
    today_schedule = db.query(Schedule).filter(
        Schedule.group_id == current_user.group_id,
        Schedule.date == today
    ).all()
    
    return templates.TemplateResponse("monitor_dashboard.html", {
        "request": request,
        "current_user": current_user,
        "students": students,
        "today_schedule": today_schedule
    })

# Маршруты для преподавателей
@app.get("/dashboard/teacher", response_class=HTMLResponse)
async def teacher_dashboard(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user or current_user.role != UserRole.teacher:
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    
    # Получаем группы, которые ведёт преподаватель
    teacher_groups = db.query(TeacherGroup).filter(TeacherGroup.teacher_id == current_user.id).all()
    group_ids = [tg.group_id for tg in teacher_groups]
    
    # Получаем расписание для этих групп
    schedule = db.query(Schedule).filter(Schedule.group_id.in_(group_ids)).all()
    
    return templates.TemplateResponse("teacher_dashboard.html", {
        "request": request,
        "current_user": current_user,
        "schedule": schedule,
        "group_ids": group_ids
    })

# Маршруты для деканата
@app.get("/dashboard/dean", response_class=HTMLResponse)
async def dean_dashboard(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user or current_user.role != UserRole.dean:
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    
    # Деканат видит всех студентов и все занятия
    students = db.query(User).filter(User.role == UserRole.student).all()
    schedule = db.query(Schedule).all()
    
    return templates.TemplateResponse("dean_dashboard.html", {
        "request": request,
        "current_user": current_user,
        "students": students,
        "schedule": schedule
    })

# Маршруты для администратора
@app.get("/dashboard/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, current_user: User = Depends(get_current_user)):
    if not current_user or current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "current_user": current_user
    })

# Маршрут для получения посещаемости студента
@app.get("/attendance/{user_id}/{schedule_id}")
async def get_attendance(user_id: int, schedule_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Проверяем права доступа к этой информации
    if current_user.role == UserRole.student and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    
    if current_user.role == UserRole.monitor:
        # Староста может видеть только студентов своей группы
        student = db.query(User).filter(User.id == user_id).first()
        if not student or student.group_id != current_user.group_id:
            raise HTTPException(status_code=403, detail="Доступ запрещён")
    
    attendance = db.query(Attendance).filter(
        Attendance.user_id == user_id,
        Attendance.schedule_id == schedule_id
    ).first()
    
    if not attendance:
        return {"status": None}
    
    return {"status": attendance.status}

# Маршрут для обновления посещаемости
@app.put("/attendance/{user_id}/{schedule_id}")
async def update_attendance(
    user_id: int, 
    schedule_id: int, 
    attendance_data: AttendanceUpdate, 
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    # Проверяем права доступа к изменению посещаемости
    if current_user.role == UserRole.student:
        raise HTTPException(status_code=403, detail="Студенты не могут изменять посещаемость")
    
    # Получаем информацию о занятии
    schedule_item = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule_item:
        raise HTTPException(status_code=404, detail="Занятие не найдено")
    
    if current_user.role == UserRole.monitor:
        # Староста может отмечать только студентов своей группы
        student = db.query(User).filter(User.id == user_id).first()
        if not student or student.group_id != current_user.group_id:
            raise HTTPException(status_code=403, detail="Доступ запрещён")
        
        # Староста может отмечать только на сегодняшние занятия
        if schedule_item.date != date.today():
            raise HTTPException(status_code=403, detail="Староста может отмечать посещаемость только на сегодняшние занятия")
    
    elif current_user.role == UserRole.teacher:
        # Преподаватель может отмечать только студентов своих групп
        teacher_group = db.query(TeacherGroup).filter(
            TeacherGroup.teacher_id == current_user.id,
            TeacherGroup.group_id == schedule_item.group_id
        ).first()
        
        if not teacher_group:
            raise HTTPException(status_code=403, detail="Доступ запрещён")
    
    # Обновляем или создаём запись о посещении
    attendance = db.query(Attendance).filter(
        Attendance.user_id == user_id,
        Attendance.schedule_id == schedule_id
    ).first()
    
    if attendance:
        attendance.status = attendance_data.status
        attendance.updated_at = datetime.utcnow()
        attendance.updated_by = current_user.id
    else:
        attendance = Attendance(
            user_id=user_id,
            schedule_id=schedule_id,
            status=attendance_data.status,
            updated_at=datetime.utcnow(),
            updated_by=current_user.id
        )
        db.add(attendance)
    
    db.commit()
    return {"success": True, "message": "Посещаемость успешно обновлена"}