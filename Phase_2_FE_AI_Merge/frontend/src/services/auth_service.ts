import { userRepo } from '../repositories/user_repository';
import type { UserEntity, UserUpdateDTO } from '../database/types';
import type { Auth } from 'firebase/auth';

export interface AuthUser {
  uid: string;
  email: string | null;
  username?: string | null;
  displayName: string | null;
  photoURL: string | null;
  role?: string | null;
  isActive?: boolean;
  persona?: string | null;
  educationDescription?: string | null;
}

const LOCAL_AUTH_TOKEN_KEY = 'bk_local_auth_token';
const LOCAL_AUTH_UID_KEY = 'bk_local_auth_uid';
const LOCAL_AUTH_USER_KEY = 'bk_local_auth_user';
const GOOGLE_AUTH_HINT_KEY = 'bk_google_auth_hint';
const LOCAL_AUTH_EVENT = 'bk_local_auth_changed';

type FirebaseDeps = {
  auth: Auth;
  signInWithGoogle: () => Promise<any>;
  logoutFirebase: () => Promise<void>;
  onAuthStateChanged: (auth: Auth, next: (user: unknown) => void) => () => void;
};

let firebaseDepsPromise: Promise<FirebaseDeps> | null = null;

const loadFirebaseDeps = async (): Promise<FirebaseDeps> => {
  if (!firebaseDepsPromise) {
    firebaseDepsPromise = Promise.all([
      import('../firebase'),
      import('firebase/auth'),
    ]).then(([firebaseMod, authMod]) => ({
      auth: firebaseMod.auth,
      signInWithGoogle: firebaseMod.signInWithGoogle,
      logoutFirebase: firebaseMod.logOut,
      onAuthStateChanged: authMod.onAuthStateChanged,
    }));
  }
  return firebaseDepsPromise;
};

class AuthService {
  private transientUser: AuthUser | null = null;

  private getCurrentUnifiedUser(): AuthUser | null {
    return this.transientUser || this.getLocalUser();
  }

  private hasGoogleAuthHint(): boolean {
    return localStorage.getItem(GOOGLE_AUTH_HINT_KEY) === '1';
  }

  private setGoogleAuthHint(enabled: boolean) {
    if (enabled) {
      localStorage.setItem(GOOGLE_AUTH_HINT_KEY, '1');
    } else {
      localStorage.removeItem(GOOGLE_AUTH_HINT_KEY);
    }
  }

  private toAuthUser(user: UserEntity): AuthUser {
    return {
      uid: user.uid,
      email: user.email,
      username: user.username || null,
      displayName: user.displayName,
      photoURL: user.photoURL,
      role: user.role,
      isActive: user.isActive ?? true,
      persona: user.persona,
      educationDescription: user.educationDescription,
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
    this.setGoogleAuthHint(false);
    window.dispatchEvent(new Event(LOCAL_AUTH_EVENT));
  }

  private clearLocalSession() {
    localStorage.removeItem(LOCAL_AUTH_TOKEN_KEY);
    localStorage.removeItem(LOCAL_AUTH_UID_KEY);
    localStorage.removeItem(LOCAL_AUTH_USER_KEY);
    window.dispatchEvent(new Event(LOCAL_AUTH_EVENT));
  }

  async login(): Promise<UserEntity> {
    const { signInWithGoogle } = await loadFirebaseDeps();

    // Set the hint early so that if onAuthStateChanged fires immediately,
    // the API client knows to use Firebase auth.
    this.setGoogleAuthHint(true);

    try {
      // 1. Sign in with Google (Firebase)
      const firebaseUser = await signInWithGoogle();
      const idToken = await firebaseUser.getIdToken(true);
      
      // 2. Call backend to sync user
      const backendUser = await userRepo.loginWithGoogleToken(idToken, firebaseUser.uid);
      this.transientUser = this.toAuthUser(backendUser);
      // Google sign-in uses Firebase for auth; we don't persist an app-token session.
      // Dispatch an event so listeners (like App.tsx) can update immediately without
      // relying on timing of Firebase's onAuthStateChanged emissions.
      window.dispatchEvent(new Event(LOCAL_AUTH_EVENT));
      this.clearLocalSession();
      return backendUser;
    } catch (error) {
      // If login fails/is cancelled, clear the hint
      this.setGoogleAuthHint(false);
      throw error;
    }
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
    if (this.hasGoogleAuthHint()) {
      try {
        const { auth, logoutFirebase } = await loadFirebaseDeps();
        if (auth.currentUser) {
          await logoutFirebase();
        }
      } catch (error) {
        console.error('Failed to clear Google auth session', error);
      }
    }
    this.setGoogleAuthHint(false);
    this.transientUser = null;
    this.clearLocalSession();
  }

  onAuthStateChanged(callback: (user: AuthUser | null) => void) {
    const localHandler = () => callback(this.getCurrentUnifiedUser());
    let disposed = false;
    let unsubFirebase: (() => void) | null = null;

    if (this.hasGoogleAuthHint()) {
      void loadFirebaseDeps()
        .then(({ auth, onAuthStateChanged }) => {
          if (disposed) return;
          unsubFirebase = onAuthStateChanged(auth, (firebaseUser) => {
            if (firebaseUser) {
              callback(firebaseUser as AuthUser);
            } else {
              // Firebase can emit `null` transiently during initialization. If we have
              // a unified user (transient Google user or local session), prefer that
              // over immediately downgrading to guest.
              callback(this.getCurrentUnifiedUser());
            }
          });
        })
        .catch((error) => {
          console.error('Failed to subscribe Firebase auth state', error);
          callback(this.getLocalUser());
        });
    }

    window.addEventListener(LOCAL_AUTH_EVENT, localHandler);
    callback(this.getCurrentUnifiedUser());

    return () => {
      disposed = true;
      if (unsubFirebase) {
        unsubFirebase();
      }
      window.removeEventListener(LOCAL_AUTH_EVENT, localHandler);
    };
  }

  async getInitialUser(): Promise<AuthUser | null> {
    const local = this.getLocalUser();
    if (local) {
      return local;
    }

    if (!this.hasGoogleAuthHint()) {
      return null;
    }

    try {
      const { auth } = await loadFirebaseDeps();
      const readyFn = (auth as any).authStateReady;
      if (typeof readyFn === 'function') {
        // Firebase can occasionally hang here (especially in dev/offline/misconfigured envs).
        // Never block the whole app boot indefinitely: fall back after a short timeout.
        await Promise.race([
          Promise.resolve(readyFn.call(auth)),
          new Promise<void>((resolve) => setTimeout(resolve, 1500)),
        ]);
      }
      return auth.currentUser ? (auth.currentUser as AuthUser) : null;
    } catch (error) {
      console.error('Failed to resolve initial Firebase user', error);
      return null;
    }
  }

  async getMe(): Promise<UserEntity> {
    return userRepo.getMe();
  }

  async updateProfile(data: UserUpdateDTO): Promise<UserEntity> {
    const updated = await userRepo.updateMe(data);
    const hasLocalToken = !!localStorage.getItem(LOCAL_AUTH_TOKEN_KEY);
    if (hasLocalToken) {
      localStorage.setItem(LOCAL_AUTH_USER_KEY, JSON.stringify(this.toAuthUser(updated)));
      window.dispatchEvent(new Event(LOCAL_AUTH_EVENT));
    }
    return updated;
  }
}

export const authService = new AuthService();

class UserService {
  async getProfile(uid: string): Promise<UserEntity> {
    return userRepo.getById(uid);
  }
}

export const userService = new UserService();
