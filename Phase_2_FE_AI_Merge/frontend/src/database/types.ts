export type Role = 'student' | 'admin' | 'instructor';

export interface UserEntity {
  uid: string;
  email: string;
  username?: string | null;
  displayName: string | null;
  role: Role;
  isActive?: boolean;
  photoURL: string | null;
  persona: string | null;
  educationDescription: string | null;
  authProvider?: string | null;
  createdAt: string;
  lastLogin: string | null;
}

export interface UserUpdateDTO {
  username?: string;
  displayName?: string;
  role?: Role;
  isActive?: boolean;
  photoURL?: string;
  persona?: string;
  educationDescription?: string;
}

export type AuthToken = string;
