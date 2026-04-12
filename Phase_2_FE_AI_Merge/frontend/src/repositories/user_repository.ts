import apiClient from '../api/client';
import { UserEntity, UserUpdateDTO } from '../database/types';

export class UserRepository {
  async login(): Promise<UserEntity> {
    const response = await apiClient.post<UserEntity>('/auth/login');
    return response.data;
  }

  async loginWithGoogleToken(idToken: string, uid: string): Promise<UserEntity> {
    const response = await apiClient.post<UserEntity>(
      '/auth/login',
      null,
      {
        headers: {
          Authorization: `Bearer ${idToken}`,
          'X-User-Id': uid,
        },
        timeout: 20000,
      }
    );
    return response.data;
  }

  async getMe(): Promise<UserEntity> {
    const response = await apiClient.get<UserEntity>('/users/me');
    return response.data;
  }

  async updateMe(data: UserUpdateDTO): Promise<UserEntity> {
    const response = await apiClient.patch<UserEntity>('/users/me', data);
    return response.data;
  }

  async getById(uid: string): Promise<UserEntity> {
    const response = await apiClient.get<UserEntity>(`/users/${uid}`);
    return response.data;
  }

  async registerLocal(payload: { email: string; password: string; displayName?: string }): Promise<{
    user: UserEntity;
    access_token: string;
    token_type: string;
    auth_provider: string;
  }> {
    const response = await apiClient.post('/auth/register-local', payload);
    return response.data;
  }

  async loginLocal(payload: { email: string; password: string }): Promise<{
    user: UserEntity;
    access_token: string;
    token_type: string;
    auth_provider: string;
  }> {
    const response = await apiClient.post('/auth/login-local', payload);
    return response.data;
  }

  async listAdminUsers(params?: {
    skip?: number;
    limit?: number;
    query?: string;
    role?: string;
    is_active?: boolean;
    include_usage?: boolean;
    usage_days?: number;
  }): Promise<{ items: UserEntity[]; count: number }> {
    const safeSkip = Math.max(0, Number(params?.skip ?? 0));
    const safeLimit = Math.max(1, Math.min(1000, Number(params?.limit ?? 100)));
    const response = await apiClient.get('/admin/users', {
      params: {
        skip: safeSkip,
        limit: safeLimit,
        ...(params?.query ? { query: params.query } : {}),
        ...(params?.role ? { role: params.role } : {}),
        ...(typeof params?.is_active === 'boolean' ? { is_active: params.is_active } : {}),
        ...(typeof params?.include_usage === 'boolean' ? { include_usage: params.include_usage } : {}),
        ...(params?.usage_days ? { usage_days: params.usage_days } : {}),
      },
    });
    return response.data;
  }

  async createAdminUser(payload: {
    email: string;
    password: string;
    username?: string;
    displayName?: string;
    role?: string;
  }): Promise<UserEntity> {
    const response = await apiClient.post('/admin/users', payload);
    return response.data;
  }

  async getAdminUser(uid: string): Promise<UserEntity & { usage_summary?: Record<string, unknown> }> {
    const response = await apiClient.get(`/admin/users/${encodeURIComponent(uid)}`);
    return response.data;
  }

  async updateAdminUser(uid: string, payload: UserUpdateDTO): Promise<UserEntity> {
    const response = await apiClient.patch(`/admin/users/${encodeURIComponent(uid)}`, payload);
    return response.data;
  }

  async deactivateAdminUser(uid: string): Promise<UserEntity> {
    const response = await apiClient.post(`/admin/users/${encodeURIComponent(uid)}/deactivate`);
    return response.data;
  }

  async activateAdminUser(uid: string): Promise<UserEntity> {
    const response = await apiClient.post(`/admin/users/${encodeURIComponent(uid)}/activate`);
    return response.data;
  }

  async deleteAdminUser(uid: string): Promise<{ deleted: boolean; uid: string }> {
    const response = await apiClient.delete(`/admin/users/${encodeURIComponent(uid)}`);
    return response.data;
  }

  async getAdminUserUsageSummary(uid: string, days = 30): Promise<Record<string, unknown>> {
    const response = await apiClient.get(`/admin/users/${encodeURIComponent(uid)}/usage-summary`, {
      params: { days },
    });
    return response.data;
  }
}

export const userRepo = new UserRepository();
