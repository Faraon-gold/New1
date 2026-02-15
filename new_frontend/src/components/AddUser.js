import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import './AddUser.css';

const AddUser = () => {
  const { user } = useAuth();
  const [formData, setFormData] = useState({
    full_name: '',
    login: '',
    password: '',
    role: 'student',
    group_id: '',
    is_monitor: false
  });
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    try {
      const token = localStorage.getItem('access_token');
      
      const userData = {
        full_name: formData.full_name,
        login: formData.login,
        password: formData.password,
        role: formData.is_monitor ? 'monitor' : formData.role,
        group_id: formData.group_id ? parseInt(formData.group_id) : null
      };
      
      const response = await axios.post('/api/register', userData, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      setMessage('Пользователь успешно добавлен');
      setError('');
      
      // Reset form
      setFormData({
        full_name: '',
        login: '',
        password: '',
        role: 'student',
        group_id: '',
        is_monitor: false
      });
    } catch (err) {
      console.error('Error adding user:', err);
      setError(err.response?.data?.detail || 'Ошибка при добавлении пользователя');
      setMessage('');
    }
  };

  if (!user || user.role !== 'admin') {
    return (
      <div className="add-user">
        <div className="error-container">
          <h2>Доступ запрещен</h2>
          <p>Только администраторы могут добавлять пользователей</p>
        </div>
      </div>
    );
  }

  return (
    <div className="add-user">
      <header className="add-user-header">
        <div className="header-content">
          <h1>Добавить пользователя</h1>
        </div>
      </header>

      <main className="add-user-main">
        <div className="form-container">
          <h2>Форма добавления пользователя</h2>
          
          {message && <div className="success-message">{message}</div>}
          {error && <div className="error-message">{error}</div>}
          
          <form onSubmit={handleSubmit} className="add-user-form">
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="full_name">ФИО:</label>
                <input
                  type="text"
                  id="full_name"
                  name="full_name"
                  value={formData.full_name}
                  onChange={handleChange}
                  required
                />
              </div>
              
              <div className="form-group">
                <label htmlFor="login">Логин:</label>
                <input
                  type="text"
                  id="login"
                  name="login"
                  value={formData.login}
                  onChange={handleChange}
                  required
                />
              </div>
            </div>
            
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="password">Пароль:</label>
                <input
                  type="password"
                  id="password"
                  name="password"
                  value={formData.password}
                  onChange={handleChange}
                  required
                />
              </div>
              
              <div className="form-group">
                <label htmlFor="role">Роль:</label>
                <select
                  id="role"
                  name="role"
                  value={formData.role}
                  onChange={handleChange}
                  disabled={formData.is_monitor}
                >
                  <option value="admin">Администратор</option>
                  <option value="dean">Декан</option>
                  <option value="teacher">Преподаватель</option>
                  <option value="student">Студент</option>
                </select>
              </div>
            </div>
            
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="group_id">Группа (ID):</label>
                <input
                  type="number"
                  id="group_id"
                  name="group_id"
                  value={formData.group_id}
                  onChange={handleChange}
                  placeholder="Введите ID группы"
                />
              </div>
              
              <div className="form-group checkbox-group">
                <label>
                  <input
                    type="checkbox"
                    name="is_monitor"
                    checked={formData.is_monitor}
                    onChange={handleChange}
                  />
                  Назначить старостой
                </label>
              </div>
            </div>
            
            <button type="submit" className="submit-button">
              Добавить пользователя
            </button>
          </form>
        </div>
      </main>
    </div>
  );
};

export default AddUser;