import { userRepo } from '../repositories/user_repository';
import { UserEntity, UserUpdateDTO } from '../database/types';
import { auth, signInWithGoogle, logOut as logoutFirebase } from '../firebase';
import { onAuthStateChanged, User as FirebaseUser } from 'firebase/auth';

class AuthService {
  private isInitializing = true;

  async login(): Promise<UserEntity> {
    // 1. Sign in with Google (Firebase)
    await signInWithGoogle();
    
    // 2. Call backend to sync user
    const backendUser = await userRepo.login();
    return backendUser;
  }

  async logout(): Promise<void> {
    await logoutFirebase();
  }

  onAuthStateChanged(callback: (user: FirebaseUser | null) => void) {
    return onAuthStateChanged(auth, callback);
  }

  async getMe(): Promise<UserEntity> {
    return userRepo.getMe();
  }

  async updateProfile(data: UserUpdateDTO): Promise<UserEntity> {
    return userRepo.updateMe(data);
  }
}

export const authService = new AuthService();

class UserService {
  async getProfile(uid: string): Promise<UserEntity> {
    return userRepo.getById(uid);
  }
}

export const userService = new UserService();
