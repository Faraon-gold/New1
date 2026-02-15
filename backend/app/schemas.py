from pydantic import BaseModel
from typing import Optional, List
from datetime import date, time


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class UserBase(BaseModel):
    full_name: str
    login: str
    role: str
    group_id: Optional[int] = None


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    login: Optional[str] = None
    role: Optional[str] = None
    group_id: Optional[int] = None
    password: Optional[str] = None


class User(BaseModel):
    id: int
    full_name: str
    login: str
    role: str
    group_id: Optional[int] = None

    class Config:
        orm_mode = True


class GroupBase(BaseModel):
    name: str


class GroupCreate(GroupBase):
    pass


class Group(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class SubjectBase(BaseModel):
    name: str
    teacher_id: int


class SubjectCreate(SubjectBase):
    pass


class Subject(BaseModel):
    id: int
    name: str
    teacher_id: int

    class Config:
        orm_mode = True


class ScheduleBase(BaseModel):
    subject_id: int
    group_id: int
    date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    teacher_id: Optional[int] = None


class ScheduleCreate(ScheduleBase):
    pass


class Schedule(BaseModel):
    id: int
    subject_id: int
    group_id: int
    date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    teacher_id: Optional[int] = None

    class Config:
        orm_mode = True


class AttendanceBase(BaseModel):
    schedule_id: int
    user_id: int
    status: str


class AttendanceCreate(AttendanceBase):
    pass


class AttendanceUpdate(AttendanceBase):
    pass


class Attendance(BaseModel):
    id: int
    schedule_id: int
    user_id: int
    status: str

    class Config:
        orm_mode = True


class PasswordChange(BaseModel):
    user_id: int
    old_password: str
    new_password: str


class OwnPasswordChange(BaseModel):
    old_password: str
    new_password: str