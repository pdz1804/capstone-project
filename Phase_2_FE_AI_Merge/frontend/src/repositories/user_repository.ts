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
}

export const userRepo = new UserRepository();
