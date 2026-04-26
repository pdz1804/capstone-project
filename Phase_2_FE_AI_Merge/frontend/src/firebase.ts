import { initializeApp } from 'firebase/app';
import { getAuth, GoogleAuthProvider, signInWithPopup, signOut, Auth } from 'firebase/auth';
import { getFirestore, doc, setDoc, getDoc, serverTimestamp } from 'firebase/firestore';
import firebaseConfig from '../firebase-applet-config.json';

export enum OperationType {
  CREATE = 'create',
  UPDATE = 'update',
  DELETE = 'delete',
  LIST = 'list',
  GET = 'get',
  WRITE = 'write',
}

interface FirestoreErrorInfo {
  error: string;
  operationType: OperationType;
  path: string | null;
  authInfo: {
    userId: string | undefined;
    email: string | null | undefined;
    emailVerified: boolean | undefined;
    isAnonymous: boolean | undefined;
    tenantId: string | null | undefined;
    providerInfo: {
      providerId: string;
      displayName: string | null;
      email: string | null;
      photoUrl: string | null;
    }[];
  }
}

export function handleFirestoreError(error: unknown, operationType: OperationType, path: string | null, auth: Auth) {
  const errInfo: FirestoreErrorInfo = {
    error: error instanceof Error ? error.message : String(error),
    authInfo: {
      userId: auth.currentUser?.uid,
      email: auth.currentUser?.email,
      emailVerified: auth.currentUser?.emailVerified,
      isAnonymous: auth.currentUser?.isAnonymous,
      tenantId: auth.currentUser?.tenantId,
      providerInfo: auth.currentUser?.providerData.map(provider => ({
        providerId: provider.providerId,
        displayName: provider.displayName,
        email: provider.email,
        photoUrl: provider.photoURL
      })) || []
    },
    operationType,
    path
  }
  console.error('Firestore Error: ', JSON.stringify(errInfo));
  throw new Error(JSON.stringify(errInfo));
}

type FirebaseAuthLikeError = {
  code?: string;
  message?: string;
};

function formatGoogleAuthError(error: unknown): Error {
  const firebaseError = error as FirebaseAuthLikeError | null;
  const code = firebaseError?.code;
  const fallbackMessage = firebaseError?.message || 'Failed to sign in with Google. Please try again.';

  if (code === 'auth/unauthorized-domain') {
    const currentOrigin = typeof window !== 'undefined' ? window.location.origin : 'the current origin';
    const currentHost = typeof window !== 'undefined' ? window.location.hostname : 'the current host';

    return new Error(
      `Google sign-in is blocked for ${currentOrigin}. Add "${currentHost}" to Firebase Console > Authentication > Settings > Authorized domains for project "${firebaseConfig.projectId}", then reload and try again.`
    );
  }

  if (code === 'auth/popup-blocked') {
    return new Error('The Google sign-in popup was blocked by your browser. Allow popups for this site and try again.');
  }

  if (code === 'auth/popup-closed-by-user') {
    return new Error('The Google sign-in popup was closed before the login finished. Please try again.');
  }

  return new Error(fallbackMessage);
}

// Initialize Firebase
const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const db = getFirestore(app, firebaseConfig.firestoreDatabaseId);

// Google Auth Provider
export const googleProvider = new GoogleAuthProvider();

async function syncGoogleUserProfile(user: { uid: string; email: string | null; displayName: string | null }) {
  const userRef = doc(db, 'users', user.uid);

  try {
    const userDoc = await getDoc(userRef);

    if (!userDoc.exists()) {
      await setDoc(userRef, {
        uid: user.uid,
        email: user.email,
        displayName: user.displayName,
        role: 'student',
        createdAt: serverTimestamp(),
        lastLogin: serverTimestamp()
      });
      return;
    }

    await setDoc(userRef, {
      lastLogin: serverTimestamp()
    }, { merge: true });
  } catch (error) {
    console.warn(
      'Skipping Firestore user profile sync after Google login. Backend auth can continue without it.',
      error
    );
  }
}

export const signInWithGoogle = async () => {
  try {
    const result = await signInWithPopup(auth, googleProvider);
    const user = result.user;

    await syncGoogleUserProfile(user);

    return user;
  } catch (error) {
    const formattedError = formatGoogleAuthError(error);
    console.error("Error signing in with Google", error);
    throw formattedError;
  }
};

export const logOut = async () => {
  try {
    await signOut(auth);
  } catch (error) {
    console.error("Error signing out", error);
    throw error;
  }
};
