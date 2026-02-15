"""Module for Google Sheets integration to sync schedule data."""

from __future__ import annotations

import csv
import io
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import gspread
import requests
from google.oauth2.service_account import Credentials
from sqlalchemy.orm import Session

from .models import Group, Schedule, Subject, User


class GoogleSheetsSync:
    def __init__(self, spreadsheet_url: str, credentials_path: str | None = None):
        self.spreadsheet_url = spreadsheet_url
        self.sheet = None
        self.gid = self._extract_gid(spreadsheet_url)

        # Try authenticated API first; if unavailable, we'll use public CSV export.
        try:
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets.readonly",
                "https://www.googleapis.com/auth/drive.readonly",
            ]

            if credentials_path:
                credentials = Credentials.from_service_account_file(credentials_path, scopes=scopes)
            else:
                credentials = Credentials.from_service_account_info(
                    info=self._get_credentials_dict(), scopes=scopes
                )

            gc = gspread.authorize(credentials)
            self.sheet = gc.open_by_url(spreadsheet_url).sheet1
        except Exception as exc:
            print(f"Google API auth unavailable, fallback to public CSV: {exc}")

    def _get_credentials_dict(self) -> Dict[str, Any]:
        import json

        creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON", "{}")
        return json.loads(creds_json)

    @staticmethod
    def _extract_gid(spreadsheet_url: str) -> str:
        parsed = urlparse(spreadsheet_url)
        query_gid = parse_qs(parsed.query).get("gid", [None])[0]
        if query_gid:
            return query_gid

        if "#gid=" in spreadsheet_url:
            return spreadsheet_url.split("#gid=")[-1]
        return "0"

    @staticmethod
    def _parse_date(date_str: str):
        date_str = date_str.strip()
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_time(value: str):
        value = value.strip()
        if not value:
            return None
        for fmt in ("%H:%M", "%H:%M:%S"):
            try:
                return datetime.strptime(value, fmt).time()
            except ValueError:
                continue
        return None

    def _parse_rows(self, rows: List[List[str]]) -> List[Dict[str, Any]]:
        if len(rows) <= 1:
            return []

        data_rows = rows[1:]
        schedule_data: List[Dict[str, Any]] = []

        for row in data_rows:
            if len(row) < 5:
                continue

            date_obj = self._parse_date(row[0])
            if not date_obj:
                continue

            start_time_obj = self._parse_time(row[1]) if len(row) > 1 else None
            end_time_obj = self._parse_time(row[2]) if len(row) > 2 else None
            subject_name = row[3].strip() if len(row) > 3 else ""
            group_name = row[4].strip() if len(row) > 4 else ""
            teacher_login = row[5].strip() if len(row) > 5 and row[5].strip() else None

            if not subject_name or not group_name:
                continue

            schedule_data.append(
                {
                    "date": date_obj,
                    "start_time": start_time_obj,
                    "end_time": end_time_obj,
                    "subject_name": subject_name,
                    "group_name": group_name,
                    "teacher_login": teacher_login,
                }
            )

        return schedule_data

    def _fetch_via_api(self) -> List[Dict[str, Any]]:
        if not self.sheet:
            return []
        rows = self.sheet.get_all_values()
        return self._parse_rows(rows)

    def _fetch_via_public_csv(self) -> List[Dict[str, Any]]:
        csv_url = self.spreadsheet_url.split("/edit")[0] + f"/export?format=csv&gid={self.gid}"
        response = requests.get(csv_url, timeout=20)
        response.raise_for_status()
        rows = list(csv.reader(io.StringIO(response.text)))
        return self._parse_rows(rows)

    def fetch_schedule_data(self) -> List[Dict[str, Any]]:
        try:
            data = self._fetch_via_api()
            if data:
                return data
        except Exception as exc:
            print(f"Error fetching schedule via Google API: {exc}")

        try:
            return self._fetch_via_public_csv()
        except Exception as exc:
            print(f"Error fetching schedule via public CSV: {exc}")
            return []

    def sync_schedule_with_db(self, db: Session) -> int:
        schedule_data = self.fetch_schedule_data()

        for item in schedule_data:
            group = db.query(Group).filter(Group.name == item["group_name"]).first()
            if not group:
                group = Group(name=item["group_name"])
                db.add(group)
                db.flush()

            subject = db.query(Subject).filter(Subject.name == item["subject_name"]).first()
            if not subject:
                teacher = None
                if item["teacher_login"]:
                    teacher = db.query(User).filter(User.login == item["teacher_login"]).first()

                subject = Subject(name=item["subject_name"], teacher_id=teacher.id if teacher else None)
                db.add(subject)
                db.flush()

            teacher = None
            if item["teacher_login"]:
                teacher = db.query(User).filter(User.login == item["teacher_login"]).first()

            existing_schedule = (
                db.query(Schedule)
                .filter(
                    Schedule.date == item["date"],
                    Schedule.subject_id == subject.id,
                    Schedule.group_id == group.id,
                    Schedule.start_time == item["start_time"],
                )
                .first()
            )

            if not existing_schedule:
                db.add(
                    Schedule(
                        date=item["date"],
                        start_time=item["start_time"],
                        end_time=item["end_time"],
                        subject_id=subject.id,
                        group_id=group.id,
                        teacher_id=teacher.id if teacher else None,
                    )
                )

        db.commit()
        print(f"Successfully synced {len(schedule_data)} schedule entries from Google Sheets")
        return len(schedule_data)
