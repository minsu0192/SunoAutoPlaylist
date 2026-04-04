# 영상 생성 (media_proc.py)

## make_video(mp3_path, image_path, output_path)

FFmpeg로 MP3 + 이미지 → MP4 영상 생성.

### 출력 스펙

- 해상도: 1920 x 1080
- 비디오: H.264 (libx264), preset fast, CRF 23
- 오디오: AAC 192kbps
- 이미지: 원본 비율 유지, 검정 레터박스 패딩
- 최적화: `-movflags +faststart` (YouTube 스트리밍)
- 타임아웃: 10분

### FFmpeg 필터

```
scale=1920:1080:force_original_aspect_ratio=decrease,
pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black
```

이미지를 1920x1080에 맞춰 축소하고 남는 부분은 검정색으로 채움.

### 출력 경로

`{output_dir}/{키워드}/{키워드}_01.mp4`, `_02.mp4`, ...
