import React, { useEffect, useState } from 'react';
import { onAuthStateChanged, signOut } from 'firebase/auth';
import { auth } from '../firebase';
import Login from './Login';

function AuthWrapper({ children }) {
  const [user, setUser]       = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Firebase Auth 상태 구독 — 로그인/로그아웃 시 자동 감지
    const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      setUser(currentUser);
      setLoading(false);
    });
    return unsubscribe; // 컴포넌트 언마운트 시 구독 해제
  }, []);

  const handleSignOut = () => signOut(auth);

  if (loading) {
    return (
      <div className="auth-loading">
        <span className="login-spinner" />
      </div>
    );
  }

  if (!user) {
    return <Login />;
  }

  return (
    <>
      {/* 로그인된 사용자 정보 바 */}
      <div className="user-bar">
        <div className="user-info">
          {user.photoURL && (
            <img className="user-avatar" src={user.photoURL} alt={user.displayName} referrerPolicy="no-referrer" />
          )}
          <span className="user-name">{user.displayName}</span>
        </div>
        <button className="signout-btn" onClick={handleSignOut}>
          로그아웃
        </button>
      </div>
      {children}
    </>
  );
}

export default AuthWrapper;
