import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import './Profile.css';

const Profile = () => {
  const { user, changePassword } = useAuth();
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const handlePasswordChange = async (e) => {
    e.preventDefault();
    
    if (newPassword !== confirmPassword) {
      setError('Новые пароли не совпадают');
      return;
    }

    if (newPassword.length < 6) {
      setError('Пароль должен содержать не менее 6 символов');
      return;
    }

    const result = await changePassword(oldPassword, newPassword);
    
    if (result.success) {
      setMessage('Пароль успешно изменен');
      setOldPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setError('');
    } else {
      setError(result.message);
      setMessage('');
    }
  };

  const getUserRoleLabel = (role) => {
    const roles = {
      'admin': 'Администратор',
      'dean': 'Декан',
      'teacher': 'Преподаватель',
      'student': 'Студент',
      'monitor': 'Староста'
    };
    return roles[role] || role;
  };

  return (
    <div className="profile">
      <header className="profile-header">
        <div className="header-content">
          <h1>Личный кабинет</h1>
        </div>
      </header>

      <main className="profile-main">
        <div className="profile-info">
          <h2>Информация о пользователе</h2>
          <div className="info-grid">
            <div className="info-item">
              <label>ФИО:</label>
              <span>{user?.full_name || 'Не указано'}</span>
            </div>
            <div className="info-item">
              <label>Логин:</label>
              <span>{user?.login || 'Не указано'}</span>
            </div>
            <div className="info-item">
              <label>Роль:</label>
              <span>{user?.role ? getUserRoleLabel(user.role) : 'Не указана'}</span>
            </div>
            <div className="info-item">
              <label>Группа:</label>
              <span>{user?.group_id ? `Группа ${user.group_id}` : 'Не указана'}</span>
            </div>
          </div>
        </div>

        <div className="password-change">
          <h2>Смена пароля</h2>
          <form onSubmit={handlePasswordChange} className="password-form">
            {message && <div className="success-message">{message}</div>}
            {error && <div className="error-message">{error}</div>}
            
            <div className="form-group">
              <label htmlFor="oldPassword">Старый пароль:</label>
              <input
                type="password"
                id="oldPassword"
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
                required
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="newPassword">Новый пароль:</label>
              <input
                type="password"
                id="newPassword"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="confirmPassword">Подтвердите новый пароль:</label>
              <input
                type="password"
                id="confirmPassword"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
              />
            </div>
            
            <button type="submit" className="change-password-button">
              Изменить пароль
            </button>
          </form>
        </div>
      </main>
    </div>
  );
};

export default Profile;