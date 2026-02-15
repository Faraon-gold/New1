from datetime import date, time
from typing import List, Optional

from pydantic import BaseModel


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
    is_monitor: bool = False
    email: Optional[str] = None


class UserCreate(UserBase):
    password: str
    personal_id: Optional[str] = None
    teacher_group_ids: List[int] = []


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    login: Optional[str] = None
    role: Optional[str] = None
    group_id: Optional[int] = None
    is_monitor: Optional[bool] = None
    password: Optional[str] = None
    email: Optional[str] = None
    personal_id: Optional[str] = None
    teacher_group_ids: Optional[List[int]] = None


class UserProfileUpdate(BaseModel):
    email: Optional[str] = None


class User(BaseModel):
    id: int
    personal_id: str
    full_name: str
    login: str
    role: str
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    is_monitor: bool = False
    email: Optional[str] = None
    teacher_group_ids: List[int] = []

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
    teacher_id: Optional[int] = None


class SubjectCreate(SubjectBase):
    pass


class Subject(BaseModel):
    id: int
    name: str
    teacher_id: Optional[int] = None

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
