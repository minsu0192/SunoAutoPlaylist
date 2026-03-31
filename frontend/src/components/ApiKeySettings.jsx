import React, { useState, useEffect } from 'react';

const STORAGE_KEY = 'anthropic_api_key';

export function useApiKey() {
  return localStorage.getItem(STORAGE_KEY) || '';
}

function ApiKeySettings({ onClose }) {
  const [key, setKey] = useState('');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setKey(localStorage.getItem(STORAGE_KEY) || '');
  }, []);

  const handleSave = () => {
    if (!key.trim()) return;
    localStorage.setItem(STORAGE_KEY, key.trim());
    setSaved(true);
    setTimeout(() => { setSaved(false); if (onClose) onClose(); }, 1000);
  };

  const handleDelete = () => {
    localStorage.removeItem(STORAGE_KEY);
    setKey('');
  };

  return (
    <div className="api-key-overlay" onClick={(e) => e.target === e.currentTarget && onClose?.()}>
      <div className="api-key-modal">
        <h3 className="api-key-title">⚙️ Anthropic API 키 설정</h3>
        <p className="api-key-desc">
          API 키는 <strong>이 브라우저에만</strong> 저장됩니다.<br />
          서버나 외부로 전송되지 않습니다.
        </p>
        <input
          className="api-key-input"
          type="password"
          placeholder="sk-ant-..."
          value={key}
          onChange={(e) => setKey(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSave()}
        />
        <div className="api-key-actions">
          <button className="api-key-save-btn" onClick={handleSave}>
            {saved ? '✅ 저장됨' : '저장'}
          </button>
          {key && (
            <button className="api-key-delete-btn" onClick={handleDelete}>
              삭제
            </button>
          )}
          <button className="api-key-cancel-btn" onClick={onClose}>
            닫기
          </button>
        </div>
        <p className="api-key-help">
          API 키가 없으면 수동 학습 모드로 사용할 수 있습니다.
        </p>
      </div>
    </div>
  );
}

export default ApiKeySettings;
