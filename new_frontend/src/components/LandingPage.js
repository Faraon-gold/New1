import React from 'react';
import { Link } from 'react-router-dom';
import './LandingPage.css';

const LandingPage = () => {
  return (
    <div className="landing-page">
      <div className="landing-container">
        <div className="logo-section">
          <div className="logo-icon">🎓</div>
          <h1>Система учёта посещаемости</h1>
          <p className="subtitle">Современное решение для эффективного управления посещаемостью студентов</p>
        </div>
        
        <div className="features-section">
          <div className="feature-card">
            <div className="feature-icon">📊</div>
            <h3>Отслеживание посещаемости</h3>
            <p>Удобный интерфейс для отметки и анализа посещений</p>
          </div>
          
          <div className="feature-card">
            <div className="feature-icon">📅</div>
            <h3>Расписание занятий</h3>
            <p>Все занятия в одном месте, доступные в любое время</p>
          </div>
          
          <div className="feature-card">
            <div className="feature-icon">👥</div>
            <h3>Управление пользователями</h3>
            <p>Гибкая система ролей и прав доступа</p>
          </div>
        </div>
        
        <div className="login-button-container">
          <Link to="/login" className="login-button">
            Войти в систему
          </Link>
        </div>
        
        <div className="info-section">
          <p>Для получения доступа обратитесь к администратору системы</p>
        </div>
      </div>
    </div>
  );
};

export default LandingPage;