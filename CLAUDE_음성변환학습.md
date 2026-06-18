# 절대 규칙: 작업 중 사용자에게 절대 묻지 않음. Yes/No 질문 금지. 확인 요청 금지. 처음부터 끝까지 자동 진행. 오류 발생 시에도 스스로 해결하고 계속 진행.

# 멀티미디어 → 기획서 자동 생성 시스템
# Claude Code 터미널 전용 CLAUDE.md
# 지원: 음성(mp3/mp4/m4a) + 이미지(jpg/png) + zip + txt/pdf

---

<auto_trigger>
## 자동 실행 규칙

### 트리거 패턴
- `변환해줘` / `시작` → 전체 파일 자동 처리 후 기획서 바로 생성
- `기획서 만들어줘` → 이미 변환된 파일 기반으로 기획서 생성
- `PRD 만들어줘` → 최종 기획서 기반 PRD 생성 (기획서 완성 후에만)

### 자동 처리 순서
```
STEP 1: 패키지 자동 설치
  → openai-whisper, python-docx, Pillow, anthropic
  → ffmpeg (미설치 시 winget install ffmpeg)

STEP 2: zip 자동 압축 해제

STEP 3: 파일 종류별 자동 처리
  음성 (mp3/mp4/m4a/wav/ogg)  → Whisper로 txt 변환
  이미지 (jpg/png/gif/webp)   → Claude Vision으로 내용 추출
  문서 (txt/pdf/md/csv)       → 직접 읽기

STEP 4: 전체 내용 통합 → 기획서 Word 자동 생성
```
</auto_trigger>

---

<installation_setup>
## 패키지 자동 설치

```python
import subprocess, sys, shutil

packages = ['openai-whisper', 'python-docx', 'Pillow', 'anthropic']
for pkg in packages:
    subprocess.run([sys.executable, '-m', 'pip', 'install', pkg, '--quiet'])

if not shutil.which('ffmpeg'):
    subprocess.run(['winget', 'install', 'ffmpeg', '--silent'])

print("준비 완료")
```
</installation_setup>

---

<zip_handler>
## zip 자동 압축 해제

```python
import zipfile
from pathlib import Path

def extract_zips():
    for zip_path in Path('.').glob('*.zip'):
        extract_dir = Path(zip_path.stem)
        extract_dir.mkdir(exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for member in zf.infolist():
                try:
                    member.filename = member.filename.encode('cp437').decode('euc-kr')
                except:
                    pass
            zf.extractall(extract_dir)
        print(f"압축 해제 완료: {extract_dir}/")

extract_zips()
```
</zip_handler>

---

<image_handler>
## 이미지 내용 추출 (Claude Vision)

```python
import anthropic, base64
from pathlib import Path

IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}

def process_all_images():
    client = anthropic.Anthropic()
    image_files = [f for f in Path('.').rglob('*') if f.suffix.lower() in IMAGE_EXT]
    if not image_files:
        return

    print(f"이미지 {len(image_files)}개 처리 중")

    for img in sorted(image_files):
        output = img.parent / (img.stem + '_extracted.txt')
        if output.exists():
            print(f"스킵: {output.name}")
            continue

        with open(img, 'rb') as f:
            data = base64.standard_b64encode(f.read()).decode('utf-8')

        media_map = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                     '.png': 'image/png', '.gif': 'image/gif', '.webp': 'image/webp'}
        media_type = media_map.get(img.suffix.lower(), 'image/png')

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}},
                {"type": "text", "text": "이미지의 모든 내용을 빠짐없이 텍스트로 추출해줘. 텍스트, 표, 차트, 슬라이드 내용 전부 구조화해서 정리해줘."}
            ]}]
        )

        with open(output, 'w', encoding='utf-8') as f:
            f.write(f"# {img.stem} 이미지 추출\n\n")
            f.write(response.content[0].text)
        print(f"완료: {output.name}")

process_all_images()
```
</image_handler>

---

<whisper_handler>
## 음성 파일 변환 (Whisper)

```python
import whisper
from pathlib import Path

AUDIO_EXT = {'.mp3', '.mp4', '.m4a', '.wav', '.ogg', '.webm'}
MODEL_SIZE = "base"  # base / small / medium / large

def transcribe_all():
    audio_files = [f for f in Path('.').rglob('*') if f.suffix.lower() in AUDIO_EXT]
    if not audio_files:
        return

    print(f"음성 {len(audio_files)}개 변환 중")
    model = whisper.load_model(MODEL_SIZE)

    for audio in sorted(audio_files):
        output = audio.parent / (audio.stem + '_transcript.txt')
        if output.exists():
            print(f"스킵: {output.name}")
            continue
        print(f"변환 중: {audio.name}")
        result = model.transcribe(str(audio), language="ko")
        with open(output, 'w', encoding='utf-8') as f:
            f.write(f"# {audio.stem} 녹취록\n\n{result['text']}")
        print(f"완료: {output.name}")

transcribe_all()
```

### Whisper 모델 선택
```
base   → 빠름 (기본값)
small  → 균형
medium → 한국어 우수
large  → 최고 품질 (긴 강의, 전문 용어)
```
</whisper_handler>

---

<document_spec>
## 기획서 구조 (프로젝트 성격에 맞게 자동 조정)

### 공통 목차
```
1. 기획 개요
   - 프로젝트명 및 목적
   - 기획 배경 및 문제 정의
   - 핵심 가치 제안

2. 현황 분析
   - 시장·환경 현황
   - 기회 및 위협 요인

3. 타겟 및 수요 분析
   - 핵심 타겟 정의
   - 니즈 및 페인포인트

4. 프로그램·서비스 구성
   - 핵심 구성 요소
   - 단계별 로드맵
   - 차별화 포인트

5. 전략 및 방법론
   - 핵심 전략 프레임워크
   - 실행 방법론

6. 실행 계획
   - 일정 및 마일스톤
   - 필요 자원
   - 리스크 및 대응

7. 기대 성과 및 KPI
```

### PRD 구조 (별도 요청 시에만)
```
1. Product Overview
2. 목표 사용자 (Persona)
3. 핵심 기능 요구사항
4. 비기능 요구사항
5. 사용자 스토리
6. 기능 명세 (Feature Spec)
7. 제약 조건 및 가정
8. 성공 지표
9. 미결 이슈
```
</document_spec>

---

<word_format>
## Word 포맷 규칙 (절대 변경 불가)

```
폰트: 굴림(Gulim) 고정
  제목: 16pt Bold / 섹션: 14pt Bold / 본문: 11pt / 표: 10pt

색상: 파란색 계열 단색
  제목 배경: Navy #003366 (흰글씨)
  섹션 제목: Blue #0070C0
  표 헤더: #1F3864 (흰글씨)
  표 짝수행: #D6E4F0
  강조: 빨간색 #FF0000만 허용
  금지: 주황·금색·보라·녹색 절대 금지

머리말·꼬리말: 완전 제거
문체: 명사형 종결 ("~한 구조", "~로 구성됨")
여백: 상하좌우 2.5cm / 줄간격 1.3배
```

### 파일명 규칙
```
기획서: [프로젝트명]_기획서_v1_YYYYMMDD.docx
수정본: [프로젝트명]_기획서_v2_YYYYMMDD.docx
최종본: [프로젝트명]_기획서_최종_YYYYMMDD.docx
PRD:   [프로젝트명]_PRD_v1_YYYYMMDD.docx
```
</word_format>

---

<revision_protocol>
## 수정 피드백 처리

수정 요청 시:
1. 해당 섹션만 수정
2. 새 버전 Word 파일 생성
3. 출력:
   ```
   수정 완료 (v2)
   변경 섹션: [섹션명]
   변경 내용: [한 줄 요약]
   ```
- 이전 버전 파일 삭제하지 않음
</revision_protocol>

---

<folder_template>
## 폴더 구조

```
[프로젝트명]/
  ├── CLAUDE.md              ← 이 파일 (어떤 프로젝트든 재사용)
  ├── 강의1.mp3              ← 음성
  ├── 슬라이드.zip           ← 화면캡처 묶음
  ├── 참고자료.pdf           ← 문서
  │
  ├── (자동 생성)
  ├── 강의1_transcript.txt
  ├── 슬라이드/01_extracted.txt
  └── [프로젝트명]_기획서_v1.docx
```

지원 형식: mp3/mp4/m4a/wav + jpg/png/gif/webp + zip + txt/pdf/md/csv
</folder_template>

---

<forbidden>
## 금지 사항
- 이미 변환된 파일 재변환
- PRD를 기획서 완성 전에 생성
- "~합니다", "~입니다" 경어 문체
- 머리말·꼬리말 삽입
- 주황·금색·보라·녹색 색상 사용
</forbidden>

---

<no_ask_rules>
## 절대 금지 — 진행 중 질문 일체 금지

### 절대 하지 말 것
- "진행할까요?" 금지
- "계속할까요?" 금지
- "맞나요?" 금지
- "어떻게 할까요?" 금지
- "확인해주세요" 금지
- Yes/No 선택 요청 금지
- 중간 승인 요청 금지

### 오류 발생 시
- 스스로 해결 후 계속 진행
- 패키지 없으면 → 자동 설치 후 진행
- 파일 읽기 실패 → 스킵하고 다음 파일 진행
- 변환 실패 → 재시도 1회 후 스킵하고 계속

### 작업 완료 시에만 출력
```
완료
생성 파일: [파일명].docx
```

### 사용자가 할 것은 딱 2가지
1. 트리거 명령 입력 (`변환해줘` / `기획서 만들어줘`)
2. 기획서 수정 피드백 입력
그 외 모든 과정은 100% 자동
</no_ask_rules>
