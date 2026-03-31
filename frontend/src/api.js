// ─────────────────────────────────────────────────────────────
// SunoAutoPlaylist API 클라이언트
// 모든 fetch 호출과 폴링 헬퍼를 중앙화합니다.
// ─────────────────────────────────────────────────────────────

const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// ── 공통 fetch 래퍼 ──────────────────────────────────────────
async function apiFetch(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'API 오류');
  return data;
}

// ── POST 엔드포인트 (즉시 job_id 반환) ──────────────────────
export function generateSong({ title, prompt, style = '', count = 2 }) {
  return apiFetch('/generate', {
    method: 'POST',
    body: JSON.stringify({ title, prompt, style, count }),
  });
}

export function convertToVideo({ song_filename, cover_image = null }) {
  return apiFetch('/convert', {
    method: 'POST',
    body: JSON.stringify({ song_filename, cover_image }),
  });
}

export function createPlaylist({ name, songs = [] }) {
  return apiFetch('/playlist', {
    method: 'POST',
    body: JSON.stringify({ name, songs }),
  });
}

export function uploadToYouTube({
  video_path, title, description = '',
  tags = [], playlist_id = null, privacy = 'public',
}) {
  return apiFetch('/upload', {
    method: 'POST',
    body: JSON.stringify({ video_path, title, description, tags, playlist_id, privacy }),
  });
}

export function runPipeline({ title, prompt, style = '', yt_playlist = null }) {
  return apiFetch('/pipeline', {
    method: 'POST',
    body: JSON.stringify({ title, prompt, style, yt_playlist }),
  });
}

// ── GET 엔드포인트 ───────────────────────────────────────────
export function getJob(jobId) {
  return apiFetch(`/jobs/${jobId}`);
}

export function listSongs() {
  return apiFetch('/songs');
}

// ── 폴링 헬퍼 ────────────────────────────────────────────────
// 3초마다 job 상태를 확인합니다.
// done   → promise resolve
// error  → promise reject
// 반환된 promise에 .cancel() 메서드가 첨부됩니다.
export function pollJob(jobId, { onUpdate, intervalMs = 3000 } = {}) {
  let timerId = null;
  let cancelled = false;

  const promise = new Promise((resolve, reject) => {
    const tick = async () => {
      if (cancelled) return;
      try {
        const job = await getJob(jobId);
        if (onUpdate) onUpdate(job);
        if (job.status === 'done')  return resolve(job);
        if (job.status === 'error') return reject(new Error(job.error || '알 수 없는 오류'));
        timerId = setTimeout(tick, intervalMs);
      } catch (err) {
        reject(err);
      }
    };
    tick();
  });

  promise.cancel = () => {
    cancelled = true;
    if (timerId) clearTimeout(timerId);
  };

  return promise;
}
