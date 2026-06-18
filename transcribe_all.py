import whisper
from pathlib import Path
import sys

AUDIO_EXT = {'.mp3', '.mp4', '.m4a', '.wav', '.ogg', '.webm'}
MODEL_SIZE = "base"
BASE_DIR = Path(r"G:\내 드라이브\Antigravity_Projects\기술적분석 강의\2301_진욱형님_비공개")

def transcribe_all():
    audio_files = sorted([f for f in BASE_DIR.rglob('*') if f.suffix.lower() in AUDIO_EXT])
    if not audio_files:
        print("음성 파일 없음")
        return

    total = len(audio_files)
    print(f"음성 {total}개 변환 시작 (모델: {MODEL_SIZE})")
    sys.stdout.flush()

    model = whisper.load_model(MODEL_SIZE)
    print("모델 로드 완료")
    sys.stdout.flush()

    for i, audio in enumerate(audio_files, 1):
        output = audio.parent / (audio.stem + '_transcript.txt')
        if output.exists():
            print(f"[{i}/{total}] 스킵: {audio.name}")
            sys.stdout.flush()
            continue

        print(f"[{i}/{total}] 변환 중: {audio.name}")
        sys.stdout.flush()

        try:
            result = model.transcribe(str(audio), language="ko")
            with open(output, 'w', encoding='utf-8') as f:
                f.write(f"# {audio.stem} 녹취록\n\n{result['text']}")
            print(f"[{i}/{total}] 완료: {output.name}")
        except Exception as e:
            print(f"[{i}/{total}] 실패 ({audio.name}): {e} — 스킵")
        sys.stdout.flush()

    print("\n전체 변환 완료")

transcribe_all()
