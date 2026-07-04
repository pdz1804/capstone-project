import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios';

const BASE_URL = (import.meta as any).env.VITE_API_BASE_URL || '/api';
const LOCAL_AUTH_TOKEN_KEY = 'bk_local_auth_token';
const LOCAL_AUTH_UID_KEY = 'bk_local_auth_uid';
const GOOGLE_AUTH_HINT_KEY = 'bk_google_auth_hint';

let firebaseAuthPromise: Promise<any | null> | null = null;

const getFirebaseAuthIfNeeded = async (): Promise<any | null> => {
  if (localStorage.getItem(GOOGLE_AUTH_HINT_KEY) !== '1') {
    return null;
  }
  if (!firebaseAuthPromise) {
    firebaseAuthPromise = import('../firebase')
      .then((mod) => mod.auth)
      .catch(() => null);
  }
  return firebaseAuthPromise;
};

// Export this function so ChatAssistantView can use the same auth logic
export const getConsistentAuthHeaders = async (): Promise<Record<string, string>> => {
  const auth = await getFirebaseAuthIfNeeded();
  const user = auth?.currentUser;
  const headers: Record<string, string> = {};

  if (user) {
    const token = await user.getIdToken();
    headers['Authorization'] = `Bearer ${token}`;
    headers['X-User-Id'] = user.uid;
  } else {
    const localToken = localStorage.getItem(LOCAL_AUTH_TOKEN_KEY);
    const localUid = localStorage.getItem(LOCAL_AUTH_UID_KEY);
    if (localToken) {
      headers['Authorization'] = `Bearer ${localToken}`;
    }
    if (localUid) {
      headers['X-User-Id'] = localUid;
    }
  }

  return headers;
};

const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor: Firebase ID token + per-user storage (must match backend X-User-Id / workspace)
apiClient.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    const auth = await getFirebaseAuthIfNeeded();
    const user = auth?.currentUser;
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
