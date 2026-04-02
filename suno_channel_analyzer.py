"""
YouTube 채널 스타일 분석기
채널 URL → yt-dlp로 최근 영상 제목/설명 수집 → Claude 1회 분석 → 스타일 템플릿 반환.

저장은 suno_settings.py에서 ~/.suno_config.json 에 직접 저장.

실행: python suno_channel_analyzer.py --url https://www.youtube.com/@channelname
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import anthropic


def _fetch_videos_yt_dlp(channel_url: str, max_videos: int = 10) -> list[dict]:
    """yt-dlp로 채널 최근 영상 제목 목록 가져오기."""
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--flat-playlist",
                "--print", "%(title)s",
                "--playlist-end", str(max_videos),
                "--no-warnings",
                "--quiet",
                channel_url,
            ],
            capture_output=True, text=True, timeout=40,
        )
        titles = [t.strip() for t in result.stdout.strip().splitlines() if t.strip()]
        return [{"title": t} for t in titles[:max_videos]]
    except FileNotFoundError:
        raise RuntimeError(
            "yt-dlp가 설치되지 않았습니다.\n"
            "터미널에서: pip install yt-dlp"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("채널 정보 가져오기 시간 초과 (40s). URL을 확인하세요.")
    except Exception as e:
        raise RuntimeError(f"채널 정보를 가져오지 못했습니다: {e}")


def analyze_channel_style(channel_url: str, api_key: str,
                           max_videos: int = 10) -> dict:
    """
    채널 URL → Claude 1회 분석 → 스타일 템플릿 dict 반환.

    Returns:
        {
            "title_template":       "제목 패턴 (예: '🎵 {keyword} — {style} | AI Music')",
            "description_template": "설명 패턴 ({keyword}, {lyrics_preview}, {tags} 사용)",
            "style_notes":          "채널 특징 설명",
            "sample_title":         "예시 제목",
            "sample_description":   "예시 설명"
        }
    """
    print(f"[채널 분석] 영상 목록 수집 중... ({channel_url})")
    videos = _fetch_videos_yt_dlp(channel_url, max_videos)

    if not videos:
        raise ValueError("채널에서 영상 제목을 찾지 못했습니다. URL을 확인하세요.")

    print(f"[채널 분석] {len(videos)}개 영상 수집 완료. Claude 분석 중...")

    title_list = "\n".join(f"- {v['title']}" for v in videos)

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=800,
        messages=[{
            "role": "user",
            "content": f"""다음은 YouTube 채널의 최근 영상 제목 목록입니다:

{title_list}

이 채널의 제목 스타일을 분석해서, AI 음악 업로드 시 사용할 수 있는 제목/설명 템플릿을 만들어 주세요.
템플릿에는 다음 플레이스홀더를 사용하세요:
  {{keyword}}         — 곡 키워드/주제
  {{song_title}}      — 곡 제목
  {{style}}           — 음악 스타일
  {{lyrics_preview}}  — 가사 첫 줄
  {{tags}}            — 해시태그들

JSON으로만 응답하세요:
{{
  "title_template":       "제목 패턴 문자열",
  "description_template": "설명 패턴 문자열 (여러 줄 가능, \\n 사용)",
  "style_notes":          "이 채널의 제목/설명 특징 (2~3줄)",
  "sample_title":         "예시 제목",
  "sample_description":   "예시 설명"
}}""",
        }],
    )

    raw = resp.content[0].text.strip()

    # ```json ... ``` 처리
    if "```" in raw:
        for part in raw.split("```")[1::2]:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            try:
                result = json.loads(part)
                print("[채널 분석] 완료!")
                return result
            except json.JSONDecodeError:
                continue

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude 응답을 JSON으로 파싱할 수 없습니다: {e}\n응답: {raw[:200]}")
    print("[채널 분석] 완료!")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="YouTube 채널 스타일 분석 (1회)")
    parser.add_argument("--url",     required=True, help="YouTube 채널 URL")
    parser.add_argument("--api-key", default="",    help="Anthropic API 키")
    parser.add_argument("--save",    action="store_true",
                        help="결과를 ~/.suno_config.json 에 저장")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        cfg_file = Path.home() / ".suno_config.json"
        if cfg_file.exists():
            try:
                api_key = json.loads(cfg_file.read_text())["anthropic_api_key"]
            except Exception:
                pass
    if not api_key:
        print("❌ Anthropic API 키가 없습니다.")
        sys.exit(1)

    try:
        style = analyze_channel_style(args.url, api_key)
        print("\n분석 결과:")
        print(json.dumps(style, ensure_ascii=False, indent=2))

        if args.save:
            cfg_file = Path.home() / ".suno_config.json"
            cfg = {}
            if cfg_file.exists():
                try:
                    cfg = json.loads(cfg_file.read_text())
                except Exception:
                    pass
            cfg["youtube_channel_url"]   = args.url
            cfg["youtube_channel_style"] = style
            cfg_file.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
            print(f"\n✅ ~/.suno_config.json 에 저장됨")

    except Exception as e:
        print(f"❌ 분석 실패: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
