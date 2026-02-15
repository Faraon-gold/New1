import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import './AttendanceMark.css';

const AttendanceMark = () => {
  const { user } = useAuth();
  const [students, setStudents] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [selectedSchedule, setSelectedSchedule] = useState('');
  const [attendanceData, setAttendanceData] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('access_token');
      
      // Get students based on user role
      let studentsUrl = '/api/users?role=student';
      if (user && user.role === 'monitor') {
        studentsUrl += `&group_id=${user.group_id}`;
      } else if (user && user.role === 'teacher') {
        // Teachers can access students in their groups
        // For now, we'll fetch all students in the teacher's groups
        studentsUrl += `&group_id=${user.taught_groups?.map(g => g.id).join(',') || user.group_id}`;
      }
      
      // Get schedules based on user role
      let schedulesUrl = '/api/schedule';
      if (user && user.role === 'monitor') {
        schedulesUrl += `?group_id=${user.group_id}`;
      } else if (user && user.role === 'teacher') {
        // Teacher schedules would be for their taught groups
      }
      
      const [studentsResponse, schedulesResponse] = await Promise.all([
        axios.get(studentsUrl, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }),
        axios.get(schedulesUrl, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        })
      ]);
      
      setStudents(studentsResponse.data);
      setSchedules(schedulesResponse.data);
      
      // Initialize attendance data
      const initialAttendance = {};
      studentsResponse.data.forEach(student => {
        initialAttendance[student.id] = 'present'; // Default to present
      });
      setAttendanceData(initialAttendance);
      
      setError('');
    } catch (err) {
      console.error('Error fetching data:', err);
      setError('Ошибка при загрузке данных для отметки посещаемости');
    } finally {
      setLoading(false);
    }
  };

  const handleAttendanceChange = (studentId, status) => {
    setAttendanceData(prev => ({
      ...prev,
      [studentId]: status
    }));
  };

  const handleSubmitAttendance = async () => {
    try {
      const token = localStorage.getItem('access_token');
      
      if (!selectedSchedule) {
        setError('Пожалуйста, выберите занятие');
        return;
      }
      
      // Submit attendance for all students
      for (const [studentId, status] of Object.entries(attendanceData)) {
        await axios.post('/api/attendance', {
          schedule_id: parseInt(selectedSchedule),
          user_id: parseInt(studentId),
          status: status
        }, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });
      }
      
      alert('Посещаемость успешно отмечена!');
    } catch (err) {
      console.error('Error submitting attendance:', err);
      setError('Ошибка при сохранении посещаемости');
    }
  };

  if (loading) {
    return (
      <div className="attendance-mark">
        <div className="loading">Загрузка данных...</div>
      </div>
    );
  }

  if (!['admin', 'dean', 'teacher', 'monitor'].includes(user?.role)) {
    return (
      <div className="attendance-mark">
        <div className="error-container">
          <h2>Доступ запрещен</h2>
          <p>Только преподаватели, старосты, деканы и администраторы могут отмечать посещаемость</p>
        </div>
      </div>
    );
  }

  return (
    <div className="attendance-mark">
      <header className="attendance-header">
        <div className="header-content">
          <h1>Отметить посещаемость</h1>
        </div>
      </header>

      <main className="attendance-main">
        {error && <div className="error-message">{error}</div>}
        
        <div className="controls">
          <div className="form-group">
            <label htmlFor="schedule-select">Выберите занятие:</label>
            <select
              id="schedule-select"
              value={selectedSchedule}
              onChange={(e) => setSelectedSchedule(e.target.value)}
            >
              <option value="">-- Выберите занятие --</option>
              {schedules.map(schedule => (
                <option key={schedule.id} value={schedule.id}>
                  {new Date(schedule.date).toLocaleDateString('ru-RU')} - 
                  {schedule.start_time || 'Нет времени'} - {schedule.subject_id}
                </option>
              ))}
            </select>
          </div>
          
          <button 
            onClick={handleSubmitAttendance} 
            className="submit-button"
            disabled={!selectedSchedule}
          >
            Сохранить посещаемость
          </button>
        </div>

        <div className="attendance-table">
          <table>
            <thead>
              <tr>
                <th>ФИО студента</th>
                <th>Логин</th>
                <th>Присутствует</th>
                <th>Отсутствует</th>
                <th>Опоздал</th>
              </tr>
            </thead>
            <tbody>
              {students.map(student => (
                <tr key={student.id}>
                  <td>{student.full_name}</td>
                  <td>{student.login}</td>
                  <td>
                    <label className="radio-label">
                      <input
                        type="radio"
                        name={`attendance-${student.id}`}
                        checked={attendanceData[student.id] === 'present'}
                        onChange={() => handleAttendanceChange(student.id, 'present')}
                      />
                      <span className="checkmark"></span>
                    </label>
                  </td>
                  <td>
                    <label className="radio-label">
                      <input
                        type="radio"
                        name={`attendance-${student.id}`}
                        checked={attendanceData[student.id] === 'absent'}
                        onChange={() => handleAttendanceChange(student.id, 'absent')}
                      />
                      <span className="checkmark"></span>
                    </label>
                  </td>
                  <td>
                    <label className="radio-label">
                      <input
                        type="radio"
                        name={`attendance-${student.id}`}
                        checked={attendanceData[student.id] === 'late'}
                        onChange={() => handleAttendanceChange(student.id, 'late')}
                      />
                      <span className="checkmark"></span>
                    </label>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
};

export default AttendanceMark;