import React, { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import type { UserResponse } from '../services/api';
import { authApi } from '../services/auth';

interface AuthContextType {
  user: UserResponse | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password?: string) => Promise<void>;
  register: (email: string, password?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Load token and user profile on application startup
  useEffect(() => {
    const initializeAuth = async () => {
      const storedToken = localStorage.getItem('cf_token') || sessionStorage.getItem('access_token');
      if (storedToken) {
        try {
          const profile = await authApi.getMe(storedToken);
          setToken(storedToken);
          setUser(profile);
        } catch (error) {
          console.warn('Invalid or expired token on load. Clearing credentials.', error);
          logout();
        }
      }
      setIsLoading(false);
    };

    initializeAuth();
  }, []);

  const login = async (email: string, password?: string) => {
    setIsLoading(true);
    try {
      const data = await authApi.login({ email, password });
      localStorage.setItem('cf_token', data.access_token);
      sessionStorage.setItem('access_token', data.access_token);
      if (data.session_token) sessionStorage.setItem('session_token', data.session_token);
      if (data.refresh_token) sessionStorage.setItem('refresh_token', data.refresh_token);
      setToken(data.access_token);
      
      const profile = await authApi.getMe(data.access_token);
      setUser(profile);
    } catch (error) {
      logout();
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (email: string, password?: string) => {
    setIsLoading(true);
    try {
      await authApi.register({ email, password });
      // Proactively login the user after successful registration
      await login(email, password);
    } catch (error) {
      logout();
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    // Clear storage cache and memory references
    localStorage.removeItem('cf_token');
    sessionStorage.removeItem('access_token');
    sessionStorage.removeItem('session_token');
    sessionStorage.removeItem('refresh_token');
    setToken(null);
    setUser(null);
  };


  const isAuthenticated = !!token && !!user;

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated,
        isLoading,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
