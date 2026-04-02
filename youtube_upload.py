"""
YouTube 업로드 모듈
YouTube Data API v3를 사용해 MP4 영상을 업로드합니다.

사전 준비:
1. Google Cloud Console → 프로젝트 생성
2. YouTube Data API v3 활성화
3. OAuth 2.0 클라이언트 ID 생성 → client_secrets.json 다운로드
4. suno_settings.py 에서 파일 경로 설정
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

BASE_DIR     = Path(__file__).parent
TOKEN_FILE   = BASE_DIR / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

CATEGORY_MUSIC = "10"


def _resolve_secrets(secrets_path: str = "") -> Path:
    """client_secrets.json 경로 결정 (설정 > 기본 위치)."""
    if secrets_path and Path(secrets_path).exists():
        return Path(secrets_path)
    # 설정 파일에서 읽기
    cfg_file = Path.home() / ".suno_config.json"
    if cfg_file.exists():
        try:
            import json
            cfg = json.loads(cfg_file.read_text())
            p = cfg.get("youtube_client_secrets", "")
            if p and Path(p).exists():
                return Path(p)
        except Exception:
            pass
    # 기본 위치
    default = BASE_DIR / "client_secrets.json"
    if default.exists():
        return default
    raise FileNotFoundError(
        "client_secrets.json 을 찾을 수 없습니다.\n"
        "설정(⚙️) → YouTube 탭에서 파일을 선택하세요."
    )


class YouTubeUploader:

    def __init__(self, secrets_path: str = ""):
        self.youtube      = None
        self.secrets_path = secrets_path

    async def upload(
        self,
        video_path: str,
        title: str,
        description: str = "",
        tags: list[str] = [],
        playlist_id: Optional[str] = None,
        privacy: str = "public",
    ) -> dict:
        if not Path(video_path).exists():
            return {"success": False, "error": f"파일 없음: {video_path}"}

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            self._upload_sync,
            video_path, title, description, tags, playlist_id, privacy,
        )
        return result

    def _upload_sync(self, video_path, title, description,
                     tags, playlist_id, privacy) -> dict:
        self.youtube = self._authenticate()

        body = {
            "snippet": {
                "title":           title,
                "description":     description or f"AI로 생성한 음악입니다.\n\n🎵 {title}",
                "tags":            tags or ["AI music", "Suno", "K-pop"],
                "categoryId":      CATEGORY_MUSIC,
                "defaultLanguage": "ko",
            },
            "status": {
                "privacyStatus":          privacy,
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            resumable=True,
            chunksize=1024 * 1024 * 5,
        )

        print(f"[YouTube] '{title}' 업로드 중...")
        request = self.youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"[YouTube] {int(status.progress() * 100)}%")

        video_id  = response["id"]
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        print(f"[YouTube] 업로드 완료: {video_url}")

        if playlist_id:
            self._add_to_playlist(video_id, playlist_id)

        return {"success": True, "video_id": video_id,
                "video_url": video_url, "title": title}

    def _add_to_playlist(self, video_id: str, playlist_id: str):
        self.youtube.playlistItems().insert(
            part="snippet",
            body={"snippet": {
                "playlistId": playlist_id,
                "resourceId": {"kind": "youtube#video", "videoId": video_id},
            }},
        ).execute()
        print(f"[YouTube] 재생목록({playlist_id}) 추가 완료.")

    def _authenticate(self):
        creds = None
        if TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                secrets = _resolve_secrets(self.secrets_path)
                flow    = InstalledAppFlow.from_client_secrets_file(str(secrets), SCOPES)
                creds   = flow.run_local_server(port=0)
            TOKEN_FILE.write_text(creds.to_json())

        return build("youtube", "v3", credentials=creds)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="YouTube 업로드 / 인증")
    parser.add_argument("--auth-only", action="store_true",
                        help="인증만 실행 (설정 창 버튼에서 호출)")
    parser.add_argument("--secrets",   default="",
                        help="client_secrets.json 경로")
    parser.add_argument("--video",     default="",  help="업로드할 MP4 경로")
    parser.add_argument("--title",     default="AI Music", help="영상 제목")
    parser.add_argument("--desc",      default="",  help="설명")
    parser.add_argument("--privacy",   default="public",
                        choices=["public", "unlisted", "private"])
    args = parser.parse_args()

    uploader = YouTubeUploader(secrets_path=args.secrets)

    if args.auth_only:
        print("[YouTube] 인증 시작...")
        try:
            uploader._authenticate()
            print("[YouTube] 인증 완료! token.json 저장됨.")
        except Exception as e:
            print(f"[YouTube] 인증 실패: {e}")
            sys.exit(1)
        return

    if not args.video:
        parser.error("--video 옵션이 필요합니다.")

    result = asyncio.run(uploader.upload(
        args.video, args.title, args.desc, privacy=args.privacy
    ))
    if result["success"]:
        print(f"✅ 업로드 완료: {result['video_url']}")
    else:
        print(f"❌ 실패: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
