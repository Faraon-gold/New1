import React, { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      // Verify token and get user info
      verifyTokenAndFetchUser(token);
    } else {
      setLoading(false);
    }
  }, []);

  const verifyTokenAndFetchUser = async (token) => {
    try {
      const response = await axios.get('/api/users/me', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      setUser(response.data);
      setIsAuthenticated(true);
    } catch (error) {
      console.error('Token verification failed:', error);
      localStorage.removeItem('access_token');
      setIsAuthenticated(false);
    } finally {
      setLoading(false);
    }
  };

  const login = async (login, password) => {
    try {
      const response = await axios.post('/api/login', {
        username: login,
        password: password
      });

      if (response.data && response.data.access_token) {
        localStorage.setItem('access_token', response.data.access_token);
        
        // Fetch user info after successful login
        await verifyTokenAndFetchUser(response.data.access_token);
        
        return { success: true };
      }
    } catch (error) {
      console.error('Login failed:', error);
      return { 
        success: false, 
        message: error.response?.data?.detail || 'Login failed' 
      };
    }
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    setUser(null);
    setIsAuthenticated(false);
  };

  const changePassword = async (oldPassword, newPassword) => {
    try {
      // We'll need to implement this endpoint in the backend
      // For now, we'll just update the password through the user update endpoint
      const token = localStorage.getItem('access_token');
      const response = await axios.put('/api/users/me/password', {
        old_password: oldPassword,
        new_password: newPassword
      }, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      return { success: true };
    } catch (error) {
      console.error('Password change failed:', error);
      return { 
        success: false, 
        message: error.response?.data?.detail || 'Password change failed' 
      };
    }
  };

  const value = {
    user,
    login,
    logout,
    changePassword,
    isAuthenticated,
    loading
  };

  return (
    <AuthContext.Provider value={value}>
      {!loading && children}
    </AuthContext.Provider>
  );
};