import { useEffect, useRef, useState } from 'react';
import { startUiCheck, pollJob } from '../api';

/**
 * 앱 마운트 시 자동으로 Suno UI 변경 감지를 실행하는 배너 컴포넌트.
 * - API 키 없으면 조용히 skip (배너 미표시)
 * - 완료 후 3초 뒤 자동 dismissed
 */
export default function UiCheckProgress() {
  const [state, setState] = useState('idle'); // idle | checking | done | error
  const [progress, setProgress] = useState({ pct: 0, message: '수노의 UI 변경사항을 확인하는 중입니다...' });
  const [result, setResult] = useState(null);
  const pollRef = useRef(null);

  useEffect(() => {
    const apiKey = localStorage.getItem('anthropic_api_key');
    if (!apiKey) return; // API 키 없으면 skip

    let dismissed = false;

    const run = async () => {
      setState('checking');
      try {
        const { job_id } = await startUiCheck({ force: false });
        pollRef.current = pollJob(job_id, {
          intervalMs: 1000,
          onUpdate: (job) => {
            if (job.progress) {
              setProgress(job.progress);
            }
          },
        });
        const job = await pollRef.current;
        if (!dismissed) {
          setResult(job.result);
          setState('done');
          setTimeout(() => {
            if (!dismissed) setState('idle');
          }, 4000);
        }
      } catch (err) {
        if (!dismissed) {
          setProgress({ pct: 100, message: err.message });
          setState('error');
          setTimeout(() => {
            if (!dismissed) setState('idle');
          }, 5000);
        }
      }
    };

    run();

    return () => {
      dismissed = true;
      if (pollRef.current?.cancel) pollRef.current.cancel();
    };
  }, []);

  if (state === 'idle') return null;

  const isChecking = state === 'checking';
  const isDone = state === 'done';
  const isError = state === 'error';

  const bannerClass = `ui-check-banner ${isDone ? 'ui-check-done' : ''} ${isError ? 'ui-check-error' : ''}`;

  const icon = isChecking ? '🔍' : isDone ? (result?.changed ? '⚠️' : '✅') : '❌';
  const label = isChecking
    ? progress.message
    : isDone
    ? result?.message || '완료'
    : progress.message;

  return (
    <div className={bannerClass}>
      <span className="ui-check-icon">{icon}</span>
      <div className="ui-check-content">
        <span className="ui-check-label">{label}</span>
        {isChecking && (
          <div className="ui-check-bar-wrap">
            <div
              className="ui-check-bar-fill"
              style={{ width: `${progress.pct || 0}%` }}
            />
          </div>
        )}
      </div>
      {isChecking && (
        <span className="ui-check-pct">{progress.pct || 0}%</span>
      )}
      <button
        className="ui-check-dismiss"
        onClick={() => setState('idle')}
        aria-label="닫기"
      >
        ×
      </button>
    </div>
  );
}
