import { initializeApp } from 'firebase/app';
import { getAuth, GoogleAuthProvider } from 'firebase/auth';
import { getAnalytics } from 'firebase/analytics';

const firebaseConfig = {
  apiKey: "AIzaSyA06AlFu5Lq0dOFRTfXN8TnqtiaY44iKBY",
  authDomain: "suno-playlist-auto-maker.firebaseapp.com",
  projectId: "suno-playlist-auto-maker",
  storageBucket: "suno-playlist-auto-maker.firebasestorage.app",
  messagingSenderId: "179974514957",
  appId: "1:179974514957:web:ba7a135093a20aa3a62844",
  measurementId: "G-EXPCGQ5L7L",
};

const app = initializeApp(firebaseConfig);

export const auth     = getAuth(app);
export const provider = new GoogleAuthProvider();
export const analytics = getAnalytics(app);
