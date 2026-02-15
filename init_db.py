from sqlalchemy import create_engine, Column, Integer, String, DateTime, Date, Time, ForeignKey, Enum
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from passlib.context import CryptContext
from datetime import date, time
import enum

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

# Создание базового класса
Base = declarative_base()

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
    updated_at = Column(DateTime, default=date.today)  # Время последнего обновления
    updated_by = Column(Integer, ForeignKey("users.id"))  # Кто обновил статус
    
    # Связи
    user = relationship("User", foreign_keys=[user_id], back_populates="attendances")
    schedule = relationship("Schedule", back_populates="attendances")
    updater = relationship("User", foreign_keys=[updated_by])

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
    attendances = relationship("Attendance", foreign_keys="[Attendance.user_id]", back_populates="user")
    scheduled_classes = relationship("Schedule", back_populates="teacher")

# Модель связи преподавателей и групп
class TeacherGroup(Base):
    __tablename__ = "teacher_groups"
    
    teacher_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id"), primary_key=True)
    
    # Связи
    teacher = relationship("User")
    group = relationship("Group", back_populates="teachers")

# Настройка базы данных
DATABASE_URL = "sqlite:///./attendance.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Контекст для хэширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    # Усекаем пароль до 72 байтов
    truncated_password = password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
    return pwd_context.hash(truncated_password)

Base.metadata.create_all(bind=engine)

def init_sample_data():
    db = SessionLocal()
    
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
        else:
            group1 = db.query(Group).filter(Group.name == "ИС-201").first()
            group2 = db.query(Group).filter(Group.name == "ИС-202").first()
            print("Группы уже существуют")
        
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
        else:
            subject1 = db.query(Subject).filter(Subject.name == "Математический анализ").first()
            subject2 = db.query(Subject).filter(Subject.name == "Программирование").first()
            subject3 = db.query(Subject).filter(Subject.name == "Физика").first()
            print("Предметы уже существуют")
        
        # Создание пользователей
        if not db.query(User).count():
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
            
            # Создание связи преподаватель-группа
            teacher_group = TeacherGroup(
                teacher_id=teacher_user.id,
                group_id=group1.id
            )
            db.add(teacher_group)
            db.commit()
            print("Создана связь преподаватель-группа")
            
            # Создание расписания
            schedule1 = Schedule(
                date=date.today(),
                start_time=time(9, 0),
                end_time=time(10, 30),
                subject_id=subject1.id,
                group_id=group1.id,
                teacher_id=teacher_user.id
            )
            
            schedule2 = Schedule(
                date=date.today(),
                start_time=time(11, 0),
                end_time=time(12, 30),
                subject_id=subject2.id,
                group_id=group1.id,
                teacher_id=teacher_user.id
            )
            
            db.add(schedule1)
            db.add(schedule2)
            db.commit()
            print("Создано расписание на сегодня")
            
            # Создание посещаемости
            attendance1 = Attendance(
                user_id=student_user.id,
                schedule_id=schedule1.id,
                status=AttendanceStatus.present,
                updated_by=admin_user.id
            )
            
            db.add(attendance1)
            db.commit()
            print("Создана запись посещаемости")
        
        else:
            print("Пользователи уже существуют")
    
    finally:
        db.close()

if __name__ == "__main__":
    init_sample_data()
    print("База данных инициализирована с тестовыми данными")