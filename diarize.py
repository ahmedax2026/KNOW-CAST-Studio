"""Suggest speakers for SRT captions using a local pyannote pipeline."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from captions import parse_srt
from animation import seconds


def assign_speakers(cues, turns):
    """Assign the speaker with the largest time overlap to each subtitle."""
    ordered = sorted(turns, key=lambda turn: turn[0])
    labels = []
    for _, _, name in ordered:
        if name not in labels:
            labels.append(name)
    mapping = {label: ('المذيع' if index == 0 else 'الخبير') for index, label in enumerate(labels[:2])}
    for cue in cues:
        start, end = seconds(cue['start']), seconds(cue['end'])
        scores = {}
        for left, right, label in ordered:
            overlap = max(0.0, min(end, right) - max(start, left))
            scores[label] = scores.get(label, 0.0) + overlap
        if scores and max(scores.values()) > 0:
            label = max(scores, key=scores.get)
            cue['speaker'] = mapping.get(label, 'المذيع')
        else:
            cue['speaker'] = 'المذيع'
    return cues


def run(audio, subtitles, output, ffmpeg):
    from pyannote.audio import Pipeline
    token = os.environ.get('HF_TOKEN')
    if not token:
        raise RuntimeError('يلزم رمز Hugging Face بعد قبول شروط نموذج pyannote')
    with tempfile.TemporaryDirectory(prefix='knowcast_speakers_') as folder:
        wav = str(Path(folder) / 'audio.wav')
        subprocess.run([ffmpeg, '-y', '-v', 'error', '-i', audio, '-ac', '1', '-ar', '16000', wav], check=True)
        pipeline = Pipeline.from_pretrained('pyannote/speaker-diarization-community-1', token=token)
        result = pipeline(wav, num_speakers=2)
        diarization = result.exclusive_speaker_diarization
        turns = [(span.start, span.end, speaker) for span, speaker in diarization]
    cues = assign_speakers(parse_srt(subtitles), turns)
    Path(output).write_text(json.dumps(cues, ensure_ascii=False, indent=2), encoding='utf-8')
    print(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('audio')
    parser.add_argument('subtitles')
    parser.add_argument('output')
    parser.add_argument('--ffmpeg', default='ffmpeg')
    args = parser.parse_args()
    try:
        run(args.audio, args.subtitles, args.output, args.ffmpeg)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
