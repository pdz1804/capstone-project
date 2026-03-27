export type Role = 'student' | 'admin' | 'instructor';

export interface UserEntity {
  uid: string;
  email: string;
  displayName: string | null;
  role: Role;
  photoURL: string | null;
  createdAt: string;
  lastLogin: string | null;
}

export interface UserUpdateDTO {
  displayName?: string;
  role?: Role;
  photoURL?: string;
}

export type AuthToken = string;
