"""
YouTube 업로드 모듈
YouTube Data API v3를 사용해 MP4 영상을 업로드합니다.

사전 준비:
1. Google Cloud Console → 프로젝트 생성
2. YouTube Data API v3 활성화
3. OAuth 2.0 클라이언트 ID 생성 → client_secrets.json 다운로드
4. 이 파일과 같은 폴더에 client_secrets.json 저장
"""

import asyncio
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

BASE_DIR     = Path(__file__).parent
SECRETS_FILE = BASE_DIR / "client_secrets.json"
TOKEN_FILE   = BASE_DIR / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

CATEGORY_MUSIC = "10"


class YouTubeUploader:

    def __init__(self):
        self.youtube = None

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

    def _upload_sync(self, video_path, title, description, tags, playlist_id, privacy) -> dict:
        self.youtube = self._authenticate()

        body = {
            "snippet": {
                "title": title,
                "description": description or f"AI로 생성한 음악입니다.\n\n🎵 {title}",
                "tags": tags or ["AI music", "Suno", "K-pop"],
                "categoryId": CATEGORY_MUSIC,
                "defaultLanguage": "ko",
            },
            "status": {
                "privacyStatus": privacy,
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
                pct = int(status.progress() * 100)
                print(f"[YouTube] 업로드 진행률: {pct}%")

        video_id = response["id"]
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        print(f"[YouTube] 업로드 완료: {video_url}")

        if playlist_id:
            self._add_to_playlist(video_id, playlist_id)

        return {
            "success": True,
            "video_id": video_id,
            "video_url": video_url,
            "title": title,
        }

    def _add_to_playlist(self, video_id: str, playlist_id: str):
        self.youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": video_id,
                    },
                }
            },
        ).execute()
        print(f"[YouTube] 재생목록({playlist_id})에 추가 완료.")

    def _authenticate(self):
        creds = None

        if TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not SECRETS_FILE.exists():
                    raise FileNotFoundError(
                        "client_secrets.json 파일이 없습니다.\n"
                        "Google Cloud Console에서 OAuth 클라이언트 ID를 생성해 이 폴더에 저장하세요."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(str(SECRETS_FILE), SCOPES)
                creds = flow.run_local_server(port=0)

            TOKEN_FILE.write_text(creds.to_json())

        return build("youtube", "v3", credentials=creds)
