import { userRepo } from '../repositories/user_repository';
import { UserEntity, UserUpdateDTO } from '../database/types';
import { auth, signInWithGoogle, logOut as logoutFirebase } from '../firebase';
import { onAuthStateChanged } from 'firebase/auth';

export interface AuthUser {
  uid: string;
  email: string | null;
  displayName: string | null;
  photoURL: string | null;
}

const LOCAL_AUTH_TOKEN_KEY = 'bk_local_auth_token';
const LOCAL_AUTH_UID_KEY = 'bk_local_auth_uid';
const LOCAL_AUTH_USER_KEY = 'bk_local_auth_user';
const LOCAL_AUTH_EVENT = 'bk_local_auth_changed';

class AuthService {
  private getCurrentUnifiedUser(): AuthUser | null {
    return auth.currentUser ? (auth.currentUser as AuthUser) : this.getLocalUser();
  }

  private toAuthUser(user: UserEntity): AuthUser {
    return {
      uid: user.uid,
      email: user.email,
      displayName: user.displayName,
      photoURL: user.photoURL,
    };
  }

  private getLocalUser(): AuthUser | null {
    const raw = localStorage.getItem(LOCAL_AUTH_USER_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as AuthUser;
    } catch {
      return null;
    }
  }

  private saveLocalSession(token: string, user: UserEntity) {
    localStorage.setItem(LOCAL_AUTH_TOKEN_KEY, token);
    localStorage.setItem(LOCAL_AUTH_UID_KEY, user.uid);
    localStorage.setItem(LOCAL_AUTH_USER_KEY, JSON.stringify(this.toAuthUser(user)));
    window.dispatchEvent(new Event(LOCAL_AUTH_EVENT));
  }

  private clearLocalSession() {
    localStorage.removeItem(LOCAL_AUTH_TOKEN_KEY);
    localStorage.removeItem(LOCAL_AUTH_UID_KEY);
    localStorage.removeItem(LOCAL_AUTH_USER_KEY);
    window.dispatchEvent(new Event(LOCAL_AUTH_EVENT));
  }

  async login(): Promise<UserEntity> {
    // 1. Sign in with Google (Firebase)
    const firebaseUser = await signInWithGoogle();
    const idToken = await firebaseUser.getIdToken(true);
    
    // 2. Call backend to sync user
    const backendUser = await userRepo.loginWithGoogleToken(idToken, firebaseUser.uid);
    this.clearLocalSession();
    return backendUser;
  }

  async registerWithAppAccount(email: string, password: string, displayName?: string): Promise<UserEntity> {
    const resp = await userRepo.registerLocal({ email, password, displayName });
    this.saveLocalSession(resp.access_token, resp.user);
    return resp.user;
  }

  async loginWithAppAccount(email: string, password: string): Promise<UserEntity> {
    const resp = await userRepo.loginLocal({ email, password });
    this.saveLocalSession(resp.access_token, resp.user);
    return resp.user;
  }

  async logout(): Promise<void> {
    if (auth.currentUser) {
      await logoutFirebase();
    }
    this.clearLocalSession();
  }

  onAuthStateChanged(callback: (user: AuthUser | null) => void) {
    const localHandler = () => callback(this.getCurrentUnifiedUser());
    const unsubFirebase = onAuthStateChanged(auth, (firebaseUser) => {
      if (firebaseUser) {
        callback(firebaseUser as AuthUser);
      } else {
        callback(this.getLocalUser());
      }
    });
    window.addEventListener(LOCAL_AUTH_EVENT, localHandler);
    callback(this.getCurrentUnifiedUser());
    return () => {
      unsubFirebase();
      window.removeEventListener(LOCAL_AUTH_EVENT, localHandler);
    };
  }

  async getInitialUser(): Promise<AuthUser | null> {
    const readyFn = (auth as any).authStateReady;
    if (typeof readyFn === 'function') {
      await readyFn.call(auth);
    }
    return this.getCurrentUnifiedUser();
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
