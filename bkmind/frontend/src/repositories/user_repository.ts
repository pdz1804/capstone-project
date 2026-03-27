import apiClient from '../api/client';
import { UserEntity, UserUpdateDTO } from '../database/types';

export class UserRepository {
  async login(): Promise<UserEntity> {
    const response = await apiClient.post<UserEntity>('/auth/login');
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
}

export const userRepo = new UserRepository();
