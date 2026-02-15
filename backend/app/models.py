# backend/app/models.py

from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Date,
    Time,
    Boolean,
    CheckConstraint,
    Table,
    DateTime,
)
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime

# Таблица для связи преподавателей и групп (многие-ко-многим)
teacher_groups = Table(
    "teacher_groups",
    Base.metadata,
    Column("teacher_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("group_id", Integer, ForeignKey("groups.id"), primary_key=True),
)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)  # Обязательное поле ФИО
    login = Column(String(50), unique=True, index=True, nullable=False)  # Уникальный логин
    password_hash = Column(String, nullable=False)  # Хэш пароля
    role = Column(  # Роль пользователя
        String(20),
        CheckConstraint("role IN ('student', 'monitor', 'teacher', 'dean', 'admin')"),
        nullable=False,
    )
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)  # Для студентов и старост

    # Связи
    group = relationship("Group", back_populates="students")  # Для студентов и старост
    attendances = relationship("Attendance", back_populates="student")
    taught_groups = relationship(
        "Group",
        secondary="teacher_groups",
        back_populates="teachers"
    )
    scheduled_classes = relationship("Schedule", back_populates="teacher")


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)  # Например, "ИС-201"

    # Связи
    students = relationship("User", back_populates="group")
    teachers = relationship(
        "User",
        secondary=teacher_groups,
        back_populates="taught_groups"
    )
    schedules = relationship("Schedule", back_populates="group")


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)

    # Связи
    schedules = relationship("Schedule", back_populates="subject")


class Schedule(Base):
    __tablename__ = "schedule"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Преподаватель занятия

    # Связи
    subject = relationship("Subject", back_populates="schedules")
    group = relationship("Group", back_populates="schedules")
    attendances = relationship("Attendance", back_populates="schedule_item")
    teacher = relationship("User")


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(Integer, ForeignKey("schedule.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # ID студента
    status = Column(  # Статус посещения
        String(10),
        CheckConstraint("status IN ('present', 'absent', 'late')"),
        nullable=False,
    )
    updated_at = Column(DateTime, default=datetime.utcnow)  # Время последнего изменения

    # Связи
    schedule_item = relationship("Schedule", back_populates="attendances")
    student = relationship("User", back_populates="attendances")

    # Уникальность: один студент — одна запись на одно занятие
    __table_args__ = (
        CheckConstraint("status IN ('present', 'absent', 'late')", name="valid_status"),
    )