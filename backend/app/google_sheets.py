"""
Module for Google Sheets integration to sync schedule data
"""
import gspread
from google.oauth2.service_account import Credentials
from sqlalchemy.orm import Session
from .models import Schedule, Subject, Group, User
from datetime import datetime, time
from typing import List, Dict, Any


class GoogleSheetsSync:
    def __init__(self, spreadsheet_url: str, credentials_path: str = None):
        self.spreadsheet_url = spreadsheet_url
        
        # Setup credentials for Google Sheets API
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly"
        ]
        
        if credentials_path:
            # Use service account credentials from file
            self.credentials = Credentials.from_service_account_file(
                credentials_path, scopes=scopes
            )
        else:
            # Use application default credentials (for deployed apps)
            self.credentials = Credentials.from_service_account_info(
                info=self._get_credentials_dict(), scopes=scopes
            )
        
        # Authenticate and open the Google Sheet
        gc = gspread.authorize(self.credentials)
        self.sheet = gc.open_by_url(spreadsheet_url).sheet1  # Assuming we're reading from the first sheet

    def _get_credentials_dict(self):
        """
        Placeholder for getting credentials dictionary.
        In production, this would come from environment variables or secrets.
        """
        # This is just a placeholder - in real implementation, 
        # credentials should be loaded securely from environment
        import os
        import json
        creds_json = os.getenv('GOOGLE_SHEETS_CREDENTIALS_JSON', '{}')
        return json.loads(creds_json)

    def fetch_schedule_data(self) -> List[Dict[str, Any]]:
        """
        Fetch schedule data from Google Sheets
        Expected format: Date, Start Time, End Time, Subject, Group, Teacher
        """
        try:
            # Get all values from the sheet
            rows = self.sheet.get_all_values()
            
            if len(rows) <= 1:
                return []  # No data
            
            # Assuming first row is header
            headers = rows[0]
            data_rows = rows[1:]
            
            schedule_data = []
            for row in data_rows:
                if len(row) < 6:  # Need at least 6 columns
                    continue
                
                # Parse data assuming the format: Date, Start Time, End Time, Subject, Group, Teacher
                try:
                    date_str = row[0].strip()
                    start_time_str = row[1].strip()
                    end_time_str = row[2].strip()
                    subject_name = row[3].strip()
                    group_name = row[4].strip()
                    teacher_login = row[5].strip() if len(row) > 5 else None
                    
                    # Parse date and times
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                    
                    start_time_obj = None
                    if start_time_str:
                        start_time_obj = datetime.strptime(start_time_str, "%H:%M").time()
                    
                    end_time_obj = None
                    if end_time_str:
                        end_time_obj = datetime.strptime(end_time_str, "%H:%M").time()
                    
                    schedule_data.append({
                        'date': date_obj,
                        'start_time': start_time_obj,
                        'end_time': end_time_obj,
                        'subject_name': subject_name,
                        'group_name': group_name,
                        'teacher_login': teacher_login
                    })
                except ValueError as e:
                    print(f"Error parsing row data: {row}, Error: {e}")
                    continue
            
            return schedule_data
        except Exception as e:
            print(f"Error fetching data from Google Sheets: {e}")
            return []

    def sync_schedule_with_db(self, db: Session):
        """
        Sync schedule data from Google Sheets to database
        """
        schedule_data = self.fetch_schedule_data()
        
        for item in schedule_data:
            # Find or create group
            group = db.query(Group).filter(Group.name == item['group_name']).first()
            if not group:
                group = Group(name=item['group_name'])
                db.add(group)
                db.flush()  # Get the ID without committing
            
            # Find or create subject
            subject = db.query(Subject).filter(Subject.name == item['subject_name']).first()
            if not subject:
                # Find teacher by login
                teacher = None
                if item['teacher_login']:
                    teacher = db.query(User).filter(User.login == item['teacher_login']).first()
                
                subject = Subject(
                    name=item['subject_name'],
                    teacher_id=teacher.id if teacher else None
                )
                db.add(subject)
                db.flush()  # Get the ID without committing
            
            # Find or create teacher
            teacher = None
            if item['teacher_login']:
                teacher = db.query(User).filter(User.login == item['teacher_login']).first()
            
            # Check if schedule entry already exists to avoid duplicates
            existing_schedule = db.query(Schedule).filter(
                Schedule.date == item['date'],
                Schedule.subject_id == subject.id,
                Schedule.group_id == group.id,
                Schedule.start_time == item['start_time']
            ).first()
            
            if not existing_schedule:
                schedule_entry = Schedule(
                    date=item['date'],
                    start_time=item['start_time'],
                    end_time=item['end_time'],
                    subject_id=subject.id,
                    group_id=group.id,
                    teacher_id=teacher.id if teacher else None
                )
                db.add(schedule_entry)
        
        db.commit()
        print(f"Successfully synced {len(schedule_data)} schedule entries from Google Sheets")