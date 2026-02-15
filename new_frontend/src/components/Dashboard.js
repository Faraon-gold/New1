import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import './Dashboard.css';

const Dashboard = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  const canAddUser = user && (user.role === 'admin');

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <div className="header-content">
          <h1>Система учёта посещаемости</h1>
          <div className="user-info">
            <span>Добро пожаловать, {user?.full_name || 'Пользователь'}!</span>
            <button onClick={handleLogout} className="logout-button">
              Выход
            </button>
          </div>
        </div>
      </header>

      <main className="dashboard-main">
        <div className="dashboard-title">
          <h2>Главная</h2>
          <p>Выберите действие для продолжения работы в системе</p>
        </div>

        <div className="dashboard-grid">
          <Link to="/schedule" className="dashboard-card">
            <div className="card-icon">📅</div>
            <h3>Посмотреть расписание</h3>
            <p>Просмотрите актуальное расписание занятий</p>
          </Link>

          <Link to="/attendance-mark" className="dashboard-card">
            <div className="card-icon">✅</div>
            <h3>Отметить посещаемость</h3>
            <p>Отметьте посещаемость студентов</p>
          </Link>

          {canAddUser && (
            <Link to="/add-user" className="dashboard-card">
              <div className="card-icon">👤</div>
              <h3>Добавить пользователя</h3>
              <p>Создайте нового пользователя в системе</p>
            </Link>
          )}

          <Link to="/profile" className="dashboard-card">
            <div className="card-icon">👤</div>
            <h3>Личный кабинет</h3>
            <p>Управляйте своим профилем и настройками</p>
          </Link>
        </div>
      </main>
    </div>
  );
};

export default Dashboard;