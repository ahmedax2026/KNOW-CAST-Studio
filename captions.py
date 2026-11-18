"""Editable subtitle cues and speaker-aware ASS export."""
import re
from pathlib import Path

TIME = re.compile(r'(\d{2}):(\d{2}):(\d{2})[,\.](\d{3})')


def parse_srt(path):
    content = Path(path).read_text(encoding='utf-8-sig').replace('\r\n', '\n')
    cues = []
    for block in re.split(r'\n\s*\n', content.strip()):
        lines = block.splitlines()
        timing = next((i for i, line in enumerate(lines) if '-->' in line), -1)
        if timing < 0:
            continue
        start, end = (part.strip() for part in lines[timing].split('-->', 1))
        if not TIME.fullmatch(start) or not TIME.fullmatch(end):
            continue
        cues.append({'start': start, 'end': end, 'text': '\n'.join(lines[timing + 1:]).strip(), 'speaker': 'المذيع'})
    return cues


def ass_time(srt_time):
    h, m, s, ms = map(int, TIME.fullmatch(srt_time).groups())
    return f'{h}:{m:02}:{s:02}.{ms // 10:02}'


def ass_escape(text):
    return text.replace('\\', r'\\').replace('{', r'\{').replace('}', r'\}').replace('\n', r'\N')


def save_ass(cues, path, host, guest):
    header = '''[Script Info]
Title: KNOW CAST captions
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Host,Arial,52,&H00FFFFFF,&H00FFFFFF,&H00152A24,&H7F000000,-1,0,0,0,100,100,0,0,1,3,0,2,90,90,90,1
Style: Guest,Arial,52,&H006BB8E8,&H006BB8E8,&H00152A24,&H7F000000,-1,0,0,0,100,100,0,0,1,3,0,2,90,90,90,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    lines = [header]
    for cue in cues:
        role = cue['speaker']
        style = 'Guest' if role == 'الخبير' else 'Host'
        name = guest if style == 'Guest' else host
        label = ass_escape(name).replace(',', '،')
        speech = ass_escape(cue['text'])
        lines.append(f"Dialogue: 0,{ass_time(cue['start'])},{ass_time(cue['end'])},{style},,0,0,0,,{{\\b1}}{label}{{\\b0}}: {speech}\n")
    Path(path).write_text(''.join(lines), encoding='utf-8-sig')
