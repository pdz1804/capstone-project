import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import { auth } from '../firebase';

const BASE_URL = (import.meta as any).env.VITE_API_BASE_URL || '/api';
const LOCAL_AUTH_TOKEN_KEY = 'bk_local_auth_token';
const LOCAL_AUTH_UID_KEY = 'bk_local_auth_uid';

const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor: Firebase ID token + per-user storage (must match backend X-User-Id / workspace)
apiClient.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    const user = auth.currentUser;
    if (user) {
      const token = await user.getIdToken();
      config.headers.Authorization = `Bearer ${token}`;
      config.headers['X-User-Id'] = user.uid;
    } else {
      const localToken = localStorage.getItem(LOCAL_AUTH_TOKEN_KEY);
      const localUid = localStorage.getItem(LOCAL_AUTH_UID_KEY);
      if (localToken) {
        config.headers.Authorization = `Bearer ${localToken}`;
      }
      if (localUid) {
        config.headers['X-User-Id'] = localUid;
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

export default apiClient;
