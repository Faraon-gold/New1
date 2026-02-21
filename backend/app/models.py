from datetime import datetime
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


teacher_groups = Table(
    "teacher_groups",
    Base.metadata,
    Column("teacher_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("group_id", Integer, ForeignKey("groups.id"), primary_key=True),
)


group_subjects = Table(
    "group_subjects",
    Base.metadata,
    Column("group_id", Integer, ForeignKey("groups.id"), primary_key=True),
    Column("subject_id", Integer, ForeignKey("subjects.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    login = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(
        String(20),
        CheckConstraint("role IN ('student', 'monitor', 'teacher', 'dean', 'admin')"),
        nullable=False,
    )
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    is_monitor = Column(Boolean, nullable=False, default=False, server_default="false")
    personal_id = Column(String(64), index=True, nullable=False, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), nullable=True)
    birth_date = Column(Date, nullable=True)
    direction_code = Column(String(32), nullable=True)
    direction_name = Column(String(255), nullable=True)
    faculty = Column(String(255), nullable=True)
    study_status = Column(String(20), nullable=False, default="studying", server_default="studying")
    stream_year = Column(String(16), nullable=True)
    education_form = Column(String(64), nullable=True)

    group = relationship("Group", back_populates="students")
    attendances = relationship("Attendance", back_populates="student")
    taught_groups = relationship("Group", secondary="teacher_groups", back_populates="teachers")
    scheduled_classes = relationship("Schedule", back_populates="teacher")


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)

    students = relationship("User", back_populates="group")
    teachers = relationship("User", secondary=teacher_groups, back_populates="taught_groups")
    schedules = relationship("Schedule", back_populates="group")
    subjects = relationship("Subject", secondary=group_subjects, back_populates="groups")


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    schedules = relationship("Schedule", back_populates="subject")
    groups = relationship("Group", secondary=group_subjects, back_populates="subjects")


class Schedule(Base):
    __tablename__ = "schedule"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    subject = relationship("Subject", back_populates="schedules")
    group = relationship("Group", back_populates="schedules")
    attendances = relationship("Attendance", back_populates="schedule_item")
    teacher = relationship("User", back_populates="scheduled_classes")


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(Integer, ForeignKey("schedule.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(
        String(10),
        CheckConstraint("status IN ('present', 'absent', 'late')"),
        nullable=False,
    )
    updated_at = Column(DateTime, default=datetime.utcnow)

    schedule_item = relationship("Schedule", back_populates="attendances")
    student = relationship("User", back_populates="attendances")

    __table_args__ = (
        CheckConstraint("status IN ('present', 'absent', 'late')", name="valid_status"),
        UniqueConstraint("schedule_id", "user_id", name="uq_attendance_schedule_user"),
    )
