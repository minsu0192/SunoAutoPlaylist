"""
yt_upload.py — YouTube Data API v3로 동영상 업로드

OAuth 토큰 저장 위치: ~/.suno_yt_token.json
"""

from __future__ import annotations

import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload


class YouTubeUploader:
    TOKEN_FILE = Path.home() / ".suno_yt_token.json"
    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube",
    ]

    def __init__(self) -> None:
        self._credentials: Credentials | None = None
        self._service = None

    # ------------------------------------------------------------------ #
    # 인증                                                                  #
    # ------------------------------------------------------------------ #

    def authenticate(self, client_secrets_path: str) -> None:
        """
        OAuth 2.0 인증 흐름을 실행한다.
        성공 시 토큰을 TOKEN_FILE에 저장한다.

        Args:
            client_secrets_path: Google Cloud Console에서 내려받은
                                  client_secrets.json 파일 경로
        """
        secrets_path = Path(client_secrets_path)
        if not secrets_path.exists():
            raise FileNotFoundError(
                f"client_secrets.json 파일을 찾을 수 없습니다: {secrets_path}"
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            str(secrets_path),
            scopes=self.SCOPES,
        )
        credentials = flow.run_local_server(port=0, open_browser=True)
        self._credentials = credentials
        self._save_token(credentials)

    def _save_token(self, credentials: Credentials) -> None:
        """토큰을 JSON 파일에 저장한다."""
        token_data = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": list(credentials.scopes) if credentials.scopes else self.SCOPES,
        }
        with self.TOKEN_FILE.open("w", encoding="utf-8") as f:
            json.dump(token_data, f, indent=2)

    def _load_token(self) -> Credentials | None:
        """저장된 토큰을 로드한다. 없으면 None."""
        if not self.TOKEN_FILE.exists():
            return None
        try:
            with self.TOKEN_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
            creds = Credentials(
                token=data.get("token"),
                refresh_token=data.get("refresh_token"),
                token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=data.get("client_id"),
                client_secret=data.get("client_secret"),
                scopes=data.get("scopes", self.SCOPES),
            )
            return creds
        except Exception:
            return None

    def _ensure_authenticated(self) -> None:
        """인증 상태를 확인하고, 만료된 경우 갱신한다."""
        if self._credentials is None:
            self._credentials = self._load_token()

        if self._credentials is None:
            raise RuntimeError(
                "YouTube 인증 정보가 없습니다.\n"
                "설정 창에서 'Google 인증' 버튼을 클릭해 인증하세요."
            )

        if self._credentials.expired and self._credentials.refresh_token:
            try:
                self._credentials.refresh(Request())
                self._save_token(self._credentials)
            except Exception as e:
                raise RuntimeError(f"토큰 갱신 실패: {e}") from e

        if self._service is None:
            self._service = build("youtube", "v3", credentials=self._credentials)

    # ------------------------------------------------------------------ #
    # 업로드                                                               #
    # ------------------------------------------------------------------ #

    def upload(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str],
        playlist_id: str,
        privacy: str = "public",
    ) -> str:
        """
        YouTube에 동영상을 업로드하고, playlist_id가 있으면 플레이리스트에 추가한다.

        Args:
            video_path:  업로드할 MP4 파일 경로
            title:       동영상 제목
            description: 동영상 설명
            tags:        태그 목록
            playlist_id: YouTube 플레이리스트 ID (빈 문자열이면 추가 안 함)
            privacy:     "public" | "unlisted" | "private"

        Returns:
            YouTube 동영상 URL (https://youtu.be/{video_id})

        Raises:
            FileNotFoundError: 동영상 파일 없음
            RuntimeError: 인증 실패 또는 업로드 오류
        """
        if not video_path.exists():
            raise FileNotFoundError(f"동영상 파일이 없습니다: {video_path}")

        self._ensure_authenticated()

        # ── 동영상 업로드 ──────────────────────────────────────────
        body = {
            "snippet": {
                "title": title[:100],         # YouTube 제목 최대 100자
                "description": description,
                "tags": tags[:500],            # 태그 개수 제한 (여유있게)
                "categoryId": "10",           # Music 카테고리
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            resumable=True,
            chunksize=256 * 1024,  # 256 KB 청크
        )

        try:
            request = self._service.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )

            response = None
            while response is None:
                status, response = request.next_chunk()

            video_id = response.get("id")
            if not video_id:
                raise RuntimeError(f"업로드 응답에 video ID가 없습니다: {response}")

        except HttpError as e:
            raise RuntimeError(f"YouTube 업로드 HTTP 오류: {e}") from e

        # ── 플레이리스트 추가 ─────────────────────────────────────
        if playlist_id:
            try:
                self._service.playlistItems().insert(
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
            except HttpError as e:
                # 플레이리스트 추가 실패는 경고만 (업로드 자체는 성공)
                print(f"[yt_upload] 플레이리스트 추가 실패 (무시): {e}")

        return f"https://youtu.be/{video_id}"
