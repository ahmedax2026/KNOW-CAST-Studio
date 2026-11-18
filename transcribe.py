"""Local speech recognition; first run downloads the selected model."""
import argparse
import sys
from pathlib import Path


def timestamp(seconds):
    millis = max(0, int(round(seconds * 1000)))
    h, rem = divmod(millis, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'


def transcribe(audio, output, model_name='small', language=None):
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError('ثبّت حزمة التفريغ: python -m pip install faster-whisper') from exc
    try:
        import ctranslate2
        use_gpu = ctranslate2.get_cuda_device_count() > 0
        model = WhisperModel(model_name, device='cuda' if use_gpu else 'cpu', compute_type='int8_float16' if use_gpu else 'int8')
    except Exception:
        model = WhisperModel(model_name, device='cpu', compute_type='int8')
    segments, _ = model.transcribe(audio, language=language, beam_size=5, vad_filter=True)
    with open(output, 'w', encoding='utf-8-sig') as stream:
        for index, segment in enumerate(segments, 1):
            stream.write(f'{index}\n{timestamp(segment.start)} --> {timestamp(segment.end)}\n{segment.text.strip()}\n\n')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('audio')
    parser.add_argument('output')
    parser.add_argument('--model', default='small')
    parser.add_argument('--language', default='auto')
    args = parser.parse_args()
    try:
        print(transcribe(args.audio, args.output, args.model, None if args.language == 'auto' else args.language))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
