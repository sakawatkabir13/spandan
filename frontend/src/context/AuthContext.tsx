import React, { createContext, useContext, useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import { ApiResponse, LoginResponse, User } from '../types';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<User>;
  registerPatient: (data: any) => Promise<User>;
  registerDoctor: (data: any) => Promise<User>;
  logout: (revokeServerSession?: boolean) => Promise<void>;
  updateUser: (user: User) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const normalizeUser = (u: any): User | null => {
  if (!u) return null;
  const full_name =
    u.full_name ||
    u.patient_profile?.full_name ||
    u.doctor_profile?.full_name ||
    u.email?.split('@')[0] ||
    'Spandan User';
  return {
    ...u,
    full_name,
  };
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => {
    const savedUser = localStorage.getItem('spandan_user');
    const token = localStorage.getItem('spandan_access_token');
    if (savedUser && token) {
      try {
        return normalizeUser(JSON.parse(savedUser));
      } catch (e) {
        return null;
      }
    }
    return null;
  });
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const verifyToken = async () => {
      const token = localStorage.getItem('spandan_access_token');
      if (!token) {
        setIsLoading(false);
        return;
      }
      try {
        const resp = await apiClient.get<ApiResponse<User>>('/auth/me');
        if (resp.data.success && resp.data.data) {
          const normalized = normalizeUser(resp.data.data);
          setUser(normalized);
          localStorage.setItem('spandan_user', JSON.stringify(normalized));
        }
      } catch (err) {
        // Token invalid or expired without refresh
        setUser(null);
        localStorage.removeItem('spandan_access_token');
        localStorage.removeItem('spandan_refresh_token');
        localStorage.removeItem('spandan_user');
      } finally {
        setIsLoading(false);
      }
    };

    verifyToken();
  }, []);

  const login = async (email: string, password: string): Promise<User> => {
    const resp = await apiClient.post<ApiResponse<LoginResponse>>('/auth/login', {
      email,
      password,
    });
    const data = resp.data.data;
    const normalized = normalizeUser(data.user) as User;
    localStorage.setItem('spandan_access_token', data.access_token);
    localStorage.setItem('spandan_refresh_token', data.refresh_token);
    localStorage.setItem('spandan_user', JSON.stringify(normalized));
    setUser(normalized);
    return normalized;
  };

  const registerPatient = async (data: any): Promise<User> => {
    const resp = await apiClient.post<ApiResponse<LoginResponse>>('/auth/register/patient', data);
    const authData = resp.data.data;
    const normalized = normalizeUser(authData.user) as User;
    localStorage.setItem('spandan_access_token', authData.access_token);
    localStorage.setItem('spandan_refresh_token', authData.refresh_token);
    localStorage.setItem('spandan_user', JSON.stringify(normalized));
    setUser(normalized);
    return normalized;
  };

  const registerDoctor = async (data: any): Promise<User> => {
    const resp = await apiClient.post<ApiResponse<LoginResponse>>('/auth/register/doctor', data);
    const authData = resp.data.data;
    const normalized = normalizeUser(authData.user) as User;
    localStorage.setItem('spandan_access_token', authData.access_token);
    localStorage.setItem('spandan_refresh_token', authData.refresh_token);
    localStorage.setItem('spandan_user', JSON.stringify(normalized));
    setUser(normalized);
    return normalized;
  };

  const logout = async (revokeServerSession = true) => {
    try {
      if (revokeServerSession && localStorage.getItem('spandan_access_token')) {
        await apiClient.post('/auth/logout');
      }
    } finally {
      localStorage.removeItem('spandan_access_token');
      localStorage.removeItem('spandan_refresh_token');
      localStorage.removeItem('spandan_user');
      setUser(null);
    }
  };

  const updateUser = (updated: User) => {
    const normalized = normalizeUser(updated) as User;
    setUser(normalized);
    localStorage.setItem('spandan_user', JSON.stringify(normalized));
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        registerPatient,
        registerDoctor,
        logout,
        updateUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
