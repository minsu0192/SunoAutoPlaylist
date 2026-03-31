import React, { useState, useEffect } from 'react';
import CopyButton from './CopyButton';
import { generateSong, pollJob } from '../api';

// ─── 타임스탬프 계산 유틸 ───────────────────────────────────
function parseTotalSeconds(duration) {
  const parts = duration.split(':').map((p) => parseInt(p, 10) || 0);
  return parts.length === 2 ? parts[0] * 60 + parts[1] : 0;
}

function formatTimestamp(totalSeconds) {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function buildTracklist(tracks) {
  let cumulative = 0;
  return tracks
    .map((t) => {
      const ts = formatTimestamp(cumulative);
      cumulative += parseTotalSeconds(t.duration);
      return `${ts} ${t.title || '(제목 없음)'}`;
    })
    .join('\n');
}

// ─── YouTube 설명 빌더 ([규칙 #2] 고정 템플릿) ─────────────
function buildYouTubeDescription(mood, tracks) {
  return `${mood.emoji} ${mood.korName} | ${mood.engName} | Seoul Diary Playlist

${mood.descriptionBody}

📌 Tracklist & Timeline
${buildTracklist(tracks)}

❤️ If you enjoyed the vibe, please like & subscribe!
🎁 All tracks are original creations for this channel`;
}

// ─── 결과 섹션 컴포넌트 ────────────────────────────────────
function OutputSection({ label, icon, content, mono = true }) {
  return (
    <div className="output-section">
      <div className="output-section-header">
        <span className="output-label">
          {icon} {label}
        </span>
        <CopyButton text={content} />
      </div>
      <pre className={`output-content${mono ? '' : ' output-content--normal'}`}>
        {content}
      </pre>
    </div>
  );
}

// ─── 메인 컴포넌트 ─────────────────────────────────────────
function ResultPanel({ mood }) {
  const [tracks, setTracks] = useState([
    { id: 1, title: 'Track 1', duration: '3:30' },
    { id: 2, title: 'Track 2', duration: '3:15' },
    { id: 3, title: 'Track 3', duration: '4:00' },
  ]);

  // ── 실행 상태 ──
  const [jobState, setJobState]     = useState(null);
  const [isRunning, setIsRunning]   = useState(false);
  const [cancelPoll, setCancelPoll] = useState(null);

  useEffect(() => {
    return () => { if (cancelPoll) cancelPoll(); };
  }, [cancelPoll]);

  const ytTitle = `${mood.emoji} ${mood.korName} | ${mood.engName} | Seoul Diary Playlist`;
  const ytDescription = buildYouTubeDescription(mood, tracks);
  const ytTags = mood.tags.join(' ');

  const addTrack = () => {
    setTracks((prev) => [
      ...prev,
      { id: Date.now(), title: `Track ${prev.length + 1}`, duration: '3:30' },
    ]);
  };

  const removeTrack = (id) => {
    setTracks((prev) => prev.filter((t) => t.id !== id));
  };

  const updateTrack = (id, field, value) => {
    setTracks((prev) =>
      prev.map((t) => (t.id === id ? { ...t, [field]: value } : t))
    );
  };

  const handleGenerate = async () => {
    if (isRunning) return;
    setIsRunning(true);
    setJobState(null);
    try {
      const { job_id } = await generateSong({
        title: mood.korName,
        prompt: mood.sunoPrompt,
        style: mood.engName,
        count: 2,
      });
      const p = pollJob(job_id, { onUpdate: setJobState });
      setCancelPoll(() => p.cancel);
      await p;
    } catch (err) {
      setJobState((prev) => ({ ...prev, status: 'error', error: err.message }));
    } finally {
      setIsRunning(false);
      setCancelPoll(null);
    }
  };

  return (
    <section className="result-panel" style={{ '--accent': mood.color }}>
      <h2 className="result-title">
        {mood.emoji} {mood.korName} 결과물
      </h2>

      {/* 1. Suno 프롬프트 */}
      <OutputSection
        label="Suno 음악 프롬프트"
        icon="🎵"
        content={mood.sunoPrompt}
      />

      {/* 2. 이미지 프롬프트 */}
      <OutputSection
        label="AI 이미지 프롬프트"
        icon="🖼"
        content={mood.imagePrompt}
      />

      {/* 3. YouTube 메타데이터 */}
      <div className="output-section">
        <div className="output-section-header">
          <span className="output-label">📺 YouTube 제목</span>
          <CopyButton text={ytTitle} />
        </div>
        <pre className="output-content">{ytTitle}</pre>
      </div>

      {/* 트랙리스트 에디터 */}
      <div className="tracklist-editor">
        <div className="tracklist-editor-header">
          <span className="output-label">📌 Tracklist 편집</span>
          <button className="add-track-btn" onClick={addTrack}>
            + 트랙 추가
          </button>
        </div>
        <div className="track-list">
          {tracks.map((track, idx) => {
            let cumulative = 0;
            for (let i = 0; i < idx; i++) {
              cumulative += parseTotalSeconds(tracks[i].duration);
            }
            return (
              <div key={track.id} className="track-row">
                <span className="track-ts">{formatTimestamp(cumulative)}</span>
                <input
                  className="track-input track-title"
                  value={track.title}
                  placeholder="트랙 제목"
                  onChange={(e) => updateTrack(track.id, 'title', e.target.value)}
                />
                <input
                  className="track-input track-duration"
                  value={track.duration}
                  placeholder="3:30"
                  onChange={(e) => updateTrack(track.id, 'duration', e.target.value)}
                />
                <button
                  className="remove-track-btn"
                  onClick={() => removeTrack(track.id)}
                  aria-label="삭제"
                >
                  ×
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── 실행 패널 ── */}
      <div className="execution-panel">
        <button
          className={`execute-btn${isRunning ? ' execute-btn--running' : ''}`}
          onClick={handleGenerate}
          disabled={isRunning}
        >
          {isRunning ? '⏳ 생성 중...' : '▶ 실행 (Suno 음악 생성)'}
        </button>

        {isRunning && cancelPoll && (
          <button
            className="cancel-btn"
            onClick={() => { cancelPoll(); setIsRunning(false); }}
          >
            취소
          </button>
        )}

        {jobState && (
          <div className={`job-status job-status--${jobState.status}`}>
            <span className="job-status-label">
              {jobState.status === 'pending' && '⏳ 대기 중...'}
              {jobState.status === 'running' && '🎵 Suno에서 생성 중... (2~3분 소요)'}
              {jobState.status === 'done'    && '✅ 생성 완료!'}
              {jobState.status === 'error'   && `❌ 오류: ${jobState.error}`}
            </span>
            {jobState.status === 'done' && jobState.result?.downloaded_files && (
              <ul className="job-result-list">
                {jobState.result.downloaded_files.map((f) => (
                  <li key={f}>🎵 {f}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {/* YouTube 설명 (트랙리스트 포함) */}
      <div className="output-section">
        <div className="output-section-header">
          <span className="output-label">📝 YouTube 설명</span>
          <CopyButton text={ytDescription} />
        </div>
        <pre className="output-content">{ytDescription}</pre>
      </div>

      {/* YouTube 태그 */}
      <OutputSection label="YouTube 태그" icon="🏷" content={ytTags} />

      {/* 4. Shorts 훅 & 고정 댓글 [제미나이 트렌드 반영] */}
      <div className="output-section output-section--highlight">
        <div className="output-section-header">
          <span className="output-label">📱 YouTube Shorts 훅</span>
          <CopyButton text={mood.shortsHook} />
        </div>
        <pre className="output-content">{mood.shortsHook}</pre>
        <p className="trend-note">
          💡 Shorts 업로드 → 본 채널 유입 전략 (제미나이 트렌드 반영)
        </p>
      </div>

      <div className="output-section output-section--highlight">
        <div className="output-section-header">
          <span className="output-label">📌 고정 댓글 템플릿</span>
          <CopyButton text={mood.pinnedComment} />
        </div>
        <pre className="output-content">{mood.pinnedComment}</pre>
        <p className="trend-note">
          💡 업로드 직후 고정 댓글로 커뮤니티 참여 유도 (제미나이 트렌드 반영)
        </p>
      </div>
    </section>
  );
}

export default ResultPanel;
