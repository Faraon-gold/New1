import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import LandingPage from './components/LandingPage';
import LoginPage from './components/LoginPage';
import Dashboard from './components/Dashboard';
import Profile from './components/Profile';
import AddUser from './components/AddUser';
import ScheduleView from './components/ScheduleView';
import AttendanceMark from './components/AttendanceMark';
import PrivateRoute from './components/PrivateRoute';
import './App.css';

function AppContent() {
  const { isAuthenticated } = useAuth();

  return (
    <Routes>
      {/* Public routes */}
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      
      {/* Protected routes */}
      <Route 
        path="/dashboard" 
        element={
          <PrivateRoute>
            <Dashboard />
          </PrivateRoute>
        } 
      />
      <Route 
        path="/profile" 
        element={
          <PrivateRoute>
            <Profile />
          </PrivateRoute>
        } 
      />
      <Route 
        path="/add-user" 
        element={
          <PrivateRoute>
            <AddUser />
          </PrivateRoute>
        } 
      />
      <Route 
        path="/schedule" 
        element={
          <PrivateRoute>
            <ScheduleView />
          </PrivateRoute>
        } 
      />
      <Route 
        path="/attendance-mark" 
        element={
          <PrivateRoute>
            <AttendanceMark />
          </PrivateRoute>
        } 
      />
      
      {/* Redirect to appropriate page based on authentication status */}
      <Route 
        path="*" 
        element={
          isAuthenticated ? <Navigate to="/dashboard" /> : <Navigate to="/" />
        } 
      />
    </Routes>
  );
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <div className="App">
          <AppContent />
        </div>
      </Router>
    </AuthProvider>
  );
}

export default App;