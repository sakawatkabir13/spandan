import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { ApiResponse, AuthTokens } from '../types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 35000,
});

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: any) => void;
}> = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else if (token) {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

// Request Interceptor: Attach access token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('spandan_access_token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response Interceptor: Automatic Refresh Token Handling
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiResponse<any>>) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // If error is 401 and request hasn't been retried yet and not auth endpoint itself
    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/auth/login') &&
      !originalRequest.url?.includes('/auth/refresh')
    ) {
      originalRequest._retry = true;
      if (isRefreshing) {
        return new Promise<string>((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${token}`;
            }
            return apiClient(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      isRefreshing = true;

      const refreshToken = localStorage.getItem('spandan_refresh_token');
      if (!refreshToken) {
        isRefreshing = false;
        localStorage.removeItem('spandan_access_token');
        localStorage.removeItem('spandan_refresh_token');
        localStorage.removeItem('spandan_user');
        window.location.href = '/login';
        return Promise.reject(error);
      }

      try {
        const rotate = async () => {
          // A second tab may already have rotated this token while we waited for its lock.
          const latest = localStorage.getItem('spandan_refresh_token');
          const access = localStorage.getItem('spandan_access_token');
          if (latest && latest !== refreshToken && access) return access;
          const refreshResp = await axios.post<ApiResponse<AuthTokens>>(
            `${BASE_URL}/auth/refresh`,
            { refresh_token: latest || refreshToken },
            { headers: { 'Content-Type': 'application/json' }, timeout: 15000 }
          );
          const tokens = refreshResp.data.data;
          localStorage.setItem('spandan_access_token', tokens.access_token);
          localStorage.setItem('spandan_refresh_token', tokens.refresh_token);
          return tokens.access_token;
        };
        const newAccess = navigator.locks ? await navigator.locks.request('spandan-token-refresh', rotate) : await rotate();

        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${newAccess}`;
        }
        processQueue(null, newAccess);
        return apiClient(originalRequest);
      } catch (refreshErr) {
        processQueue(refreshErr, null);
        localStorage.removeItem('spandan_access_token');
        localStorage.removeItem('spandan_refresh_token');
        localStorage.removeItem('spandan_user');
        window.location.href = '/login';
        return Promise.reject(refreshErr);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);
