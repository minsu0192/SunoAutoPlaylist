"""
YouTube 성과 분석 모듈 — 피드백 루프
업로드된 영상의 조회수/좋아요 데이터를 수집하고,
상위/하위 패턴을 분석해 다음 곡 생성에 반영합니다.

사용법:
  python youtube_analytics.py                  # 전체 분석 실행
  python youtube_analytics.py --collect-only   # 데이터 수집만
  python youtube_analytics.py --analyze-only   # 분석만 (수집 건너뜀)
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

BASE_DIR = Path(__file__).parent
TOKEN_FILE = BASE_DIR / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube",
]

CONFIG_FILE = Path.home() / ".suno_config.json"


def _load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _get_youtube_client():
    """인증된 YouTube API 클라이언트 반환."""
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(
            "token.json이 없습니다. 먼저 YouTube 인증을 실행하세요.\n"
            "  python youtube_upload.py --auth-only"
        )
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds)


class YouTubeAnalytics:
    """YouTube 영상 성과 수집 및 분석."""

    def __init__(self, projects_root: str = "~/SunoProjects"):
        self.projects_root = Path(projects_root).expanduser()
        self.history_file = self.projects_root / "upload_history.json"
        self.performance_file = self.projects_root / "performance_data.json"

    def collect_stats(self) -> list[dict]:
        """업로드 히스토리의 모든 영상 통계를 YouTube API로 수집."""
        if not self.history_file.exists():
            print("업로드 히스토리가 없습니다.")
            return []

        history = json.loads(self.history_file.read_text(encoding="utf-8"))
        if not history:
            print("업로드 기록이 비어 있습니다.")
            return []

        video_ids = [h["video_id"] for h in history if h.get("video_id")]
        if not video_ids:
            print("수집할 영상 ID가 없습니다.")
            return []

        youtube = _get_youtube_client()
        stats = []

        # YouTube API는 한 번에 50개까지 조회 가능
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i:i+50]
            response = youtube.videos().list(
                part="statistics,snippet",
                id=",".join(batch),
            ).execute()

            for item in response.get("items", []):
                vid = item["id"]
                snippet = item["snippet"]
                statistics = item["statistics"]

                # 히스토리에서 매칭되는 기록 찾기
                matching = next(
                    (h for h in history if h.get("video_id") == vid), {}
                )

                stats.append({
                    "video_id": vid,
                    "title": snippet.get("title", ""),
                    "published_at": snippet.get("publishedAt", ""),
                    "views": int(statistics.get("viewCount", 0)),
                    "likes": int(statistics.get("likeCount", 0)),
                    "comments": int(statistics.get("commentCount", 0)),
                    "keyword": matching.get("keyword", ""),
                    "style": matching.get("style", ""),
                    "tags": matching.get("tags", []),
                    "collected_at": datetime.now().isoformat(),
                })

        print(f"[분석] {len(stats)}개 영상 통계 수집 완료")
        return stats

    def analyze(self, stats: list[dict] = None) -> dict:
        """
        수집된 통계를 분석해 상위/하위 패턴을 추출.
        performance_data.json에 저장.
        """
        if stats is None:
            stats = self.collect_stats()

        if not stats:
            return {"top_performers": [], "low_performers": [], "insights": {}}

        # 조회수 기준 정렬
        sorted_by_views = sorted(stats, key=lambda x: x["views"], reverse=True)

        # 상위 30% / 하위 30%
        n = len(sorted_by_views)
        top_n = max(1, n * 30 // 100)
        low_n = max(1, n * 30 // 100)

        top = sorted_by_views[:top_n]
        low = sorted_by_views[-low_n:]

        # 스타일별 평균 성과
        style_stats = {}
        for s in stats:
            style = s.get("style", "unknown")
            if style not in style_stats:
                style_stats[style] = {"total_views": 0, "total_likes": 0, "count": 0}
            style_stats[style]["total_views"] += s["views"]
            style_stats[style]["total_likes"] += s["likes"]
            style_stats[style]["count"] += 1

        style_avg = {}
        for style, data in style_stats.items():
            cnt = data["count"]
            style_avg[style] = {
                "avg_views": data["total_views"] // cnt,
                "avg_likes": data["total_likes"] // cnt,
                "count": cnt,
            }

        # 태그별 성과
        tag_views = {}
        for s in stats:
            for tag in s.get("tags", []):
                if tag not in tag_views:
                    tag_views[tag] = {"total_views": 0, "count": 0}
                tag_views[tag]["total_views"] += s["views"]
                tag_views[tag]["count"] += 1

        top_tags = sorted(
            tag_views.items(),
            key=lambda x: x[1]["total_views"] / max(x[1]["count"], 1),
            reverse=True,
        )[:10]

        result = {
            "updated_at": datetime.now().isoformat(),
            "total_videos": n,
            "top_performers": [
                {
                    "video_id": t["video_id"],
                    "keyword": t["keyword"],
                    "style": t["style"],
                    "views": t["views"],
                    "likes": t["likes"],
                    "title": t["title"],
                }
                for t in top
            ],
            "low_performers": [
                {
                    "video_id": l["video_id"],
                    "keyword": l["keyword"],
                    "style": l["style"],
                    "views": l["views"],
                    "likes": l["likes"],
                    "title": l["title"],
                }
                for l in low
            ],
            "insights": {
                "style_performance": style_avg,
                "top_tags": [
                    {"tag": t[0], "avg_views": t[1]["total_views"] // t[1]["count"]}
                    for t in top_tags
                ],
                "avg_views": sum(s["views"] for s in stats) // n,
                "avg_likes": sum(s["likes"] for s in stats) // n,
            },
        }

        # 저장
        self.performance_file.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[분석] 성과 데이터 저장: {self.performance_file}")
        self._print_summary(result)
        return result

    def _print_summary(self, result: dict):
        insights = result.get("insights", {})
        print(f"\n{'='*50}")
        print(f"YouTube 성과 분석 ({result['total_videos']}개 영상)")
        print(f"{'='*50}")
        print(f"평균 조회수: {insights.get('avg_views', 0):,}")
        print(f"평균 좋아요: {insights.get('avg_likes', 0):,}")

        top = result.get("top_performers", [])
        if top:
            print(f"\n--- 상위 곡 ---")
            for t in top[:5]:
                print(f"  {t['keyword']} ({t['style'][:30]}) "
                      f"→ 조회수 {t['views']:,}, 좋아요 {t['likes']:,}")

        low = result.get("low_performers", [])
        if low:
            print(f"\n--- 하위 곡 ---")
            for l in low[:3]:
                print(f"  {l['keyword']} ({l['style'][:30]}) "
                      f"→ 조회수 {l['views']:,}")

        style_perf = insights.get("style_performance", {})
        if style_perf:
            print(f"\n--- 스타일별 성과 ---")
            sorted_styles = sorted(
                style_perf.items(),
                key=lambda x: x[1]["avg_views"],
                reverse=True,
            )
            for style, data in sorted_styles[:5]:
                print(f"  {style[:40]} → 평균 {data['avg_views']:,}회 ({data['count']}곡)")

        print(f"{'='*50}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="YouTube 성과 분석 (피드백 루프)")
    parser.add_argument("--collect-only", action="store_true",
                        help="통계 수집만 실행")
    parser.add_argument("--analyze-only", action="store_true",
                        help="분석만 실행 (이전 수집 데이터 사용)")
    parser.add_argument("--projects-root", default="",
                        help="프로젝트 루트 경로")
    args = parser.parse_args()

    config = _load_config()
    root = args.projects_root or config.get("projects_root", "~/SunoProjects")

    analytics = YouTubeAnalytics(projects_root=root)

    if args.collect_only:
        stats = analytics.collect_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    elif args.analyze_only:
        analytics.analyze(stats=None)
    else:
        stats = analytics.collect_stats()
        analytics.analyze(stats)


if __name__ == "__main__":
    main()
