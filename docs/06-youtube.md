# YouTube 업로드 (yt_upload.py)

## 인증

- OAuth 2.0 (Google API v3)
- 인증 파일: `client_secrets.json` (설정에서 경로 지정)
- 토큰 저장: `~/.suno_yt_token.json` (자동 갱신)
- 첫 인증: 브라우저 열려서 Google 로그인

## 업로드

### YouTubeUploader.upload()

| 파라미터 | 설명 |
|---------|------|
| `video_path` | MP4 파일 경로 |
| `title` | 영상 제목 (Claude 생성) |
| `description` | 영상 설명 (해시태그 포함) |
| `tags` | 태그 목록 (최소 8개) |
| `playlist_id` | 플레이리스트 ID (선택) |
| `privacy` | public / unlisted / private |

### 제목 형식

```
{YouTube 제목} [1/6]
{YouTube 제목} [2/6]
...
```

## 플레이리스트

`youtube_playlist_id`가 설정되어 있으면 업로드 후 자동으로 추가.

## 공개범위

| 값 | 설명 |
|----|------|
| `public` | 전체 공개 |
| `unlisted` | 링크 있는 사람만 |
| `private` | 비공개 |
