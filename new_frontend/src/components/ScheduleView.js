import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import './ScheduleView.css';

const ScheduleView = () => {
  const { user } = useAuth();
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchSchedule();
  }, []);

  const fetchSchedule = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('access_token');
      
      let url = '/api/schedule';
      
      // For students, fetch their own schedule
      if (user && user.role === 'student') {
        url = `/api/student-schedule/${user.id}`;
      }
      // For monitors, fetch schedule for their group
      else if (user && user.role === 'monitor') {
        url = `/api/schedule?group_id=${user.group_id}`;
      }
      
      const response = await axios.get(url, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      setSchedules(response.data);
      setError('');
    } catch (err) {
      console.error('Error fetching schedule:', err);
      setError('Ошибка при загрузке расписания');
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'long',
      year: 'numeric'
    });
  };

  if (loading) {
    return (
      <div className="schedule-view">
        <div className="loading">Загрузка расписания...</div>
      </div>
    );
  }

  return (
    <div className="schedule-view">
      <header className="schedule-header">
        <div className="header-content">
          <h1>Расписание занятий</h1>
        </div>
      </header>

      <main className="schedule-main">
        {error && <div className="error-message">{error}</div>}
        
        {schedules.length === 0 ? (
          <div className="no-schedule">
            <p>Расписание пока не составлено или недоступно</p>
          </div>
        ) : (
          <div className="schedule-list">
            {schedules.map((schedule) => (
              <div key={schedule.id} className="schedule-item">
                <div className="schedule-date">
                  <strong>Дата:</strong> {formatDate(schedule.date)}
                </div>
                <div className="schedule-time">
                  <strong>Время:</strong> {schedule.start_time || 'Нет данных'} - {schedule.end_time || 'Нет данных'}
                </div>
                <div className="schedule-subject">
                  <strong>Предмет:</strong> {schedule.subject_id}
                </div>
                <div className="schedule-group">
                  <strong>Группа:</strong> {schedule.group_id}
                </div>
                <div className="schedule-teacher">
                  <strong>Преподаватель:</strong> {schedule.teacher_id}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
};

export default ScheduleView;