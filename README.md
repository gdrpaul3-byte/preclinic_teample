# 2026 전임상개론 조 발표 대시보드

`2026-04-18_전임상개론_조별_정리.md`를 바탕으로 10개 조의 조장·조원·발표 주제를 한눈에 보여주는 정적 웹페이지와, fal.ai 기반 주제 소개 GIF 생성 스크립트.

## 디렉터리

```
docs/               단일 페이지 앱 (index.html + styles.css + app.js + data.json)
                    GitHub Pages 배포 경로이기도 함
docs/assets/gifs/   각 조 주제 GIF (group-<n>.gif) + placeholder.gif
scripts/
  build_data.py     md → data.json 파서
  generate_gif.py   fal.ai (nano-banana + kling-video) → ffmpeg 변환
tmp/                중간 산출물 (PNG/MP4, .gitignore됨)
.env                FAL_KEY 보관 (.gitignore로 보호됨)
```

GitHub Pages: Settings → Pages → Source: Deploy from a branch → Branch: `main` / `/docs`
배포 URL: `https://<사용자>.github.io/preclinic_teample/`

## 빠른 시작

### 1) 데이터 생성 (마크다운 → JSON)

```bash
python scripts/build_data.py
# Wrote docs/data.json: 10 groups, 52 members, 5 leaders set, 1 topics confirmed
```

마크다운 원본이 갱신될 때마다 다시 실행하면 `docs/data.json`이 덮어써집니다.

### 2) 웹페이지 실행

로컬 HTTP 서버로 열어야 `fetch('data.json')`이 동작합니다 (file:// 은 CORS로 차단).

```bash
cd docs
python -m http.server 8000
# 브라우저에서 http://localhost:8000
```

### 3) 발표 주제 GIF 생성

Python 의존성과 ffmpeg가 필요합니다.

```bash
pip install -r requirements.txt
# Windows: winget install Gyan.FFmpeg
# macOS:   brew install ffmpeg
# Linux:   apt-get install ffmpeg
```

프롬프트 확인(과금 없음):

```bash
python scripts/generate_gif.py --group 5 --dry-run
```

실제 생성 (fal.ai 호출, 분당 몇 센트):

```bash
python scripts/generate_gif.py --group 5         # 5조 BBB GIF
python scripts/generate_gif.py --placeholder     # 미정 조용 공용 플레이스홀더
python scripts/generate_gif.py --all             # 주제 확정된 모든 조
```

산출물은 `docs/assets/gifs/group-<n>.gif`로 저장되어 페이지가 자동으로 이를 보여줍니다.

## 새 조의 주제가 들어오면

1. `2026-04-18_전임상개론_조별_정리.md`의 해당 조 `발표주제:` 갱신
2. `python scripts/build_data.py`
3. `scripts/generate_gif.py`의 `IMAGE_PROMPTS` 딕셔너리에 해당 조 프롬프트 추가
4. `python scripts/generate_gif.py --group <n>`

## 보안

`.env`는 `.gitignore`에 이미 등록되어 있어 커밋/푸시로 유출될 수 없습니다. 실수 방지를 위해 커밋 전에 한 번씩 확인:

```bash
git status --ignored | grep -E "\.env$"   # ignored 목록에 있어야 정상
```
