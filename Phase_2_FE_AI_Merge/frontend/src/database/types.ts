export type Role = 'student' | 'admin' | 'instructor';

export interface UserEntity {
  uid: string;
  email: string;
  displayName: string | null;
  role: Role;
  photoURL: string | null;
  persona: string | null;
  educationDescription: string | null;
  authProvider?: string | null;
  createdAt: string;
  lastLogin: string | null;
}

export interface UserUpdateDTO {
  displayName?: string;
  role?: Role;
  photoURL?: string;
  persona?: string;
  educationDescription?: string;
}

export type AuthToken = string;
