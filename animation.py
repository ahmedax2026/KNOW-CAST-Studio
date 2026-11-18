"""Prepare speaker-specific clips for an installed SadTalker engine.

The original recording is never modified. Cue audio is extracted to temporary WAV
files and the generated talking-head clips are silent during final composition.
"""
import argparse
import hashlib
import shutil
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from face_blend import detect_face, create_mask, crop_box


def seconds(value):
    h, m, rest = value.split(':')
    s, ms = rest.replace('.', ',').split(',')
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def build_jobs(cues, max_seconds=30):
    jobs = []
    for cue in cues:
        speaker = cue['speaker']
        if speaker not in ('المذيع', 'الخبير'):
            raise ValueError('اسم المتحدث غير معروف في الجدول')
        start, end = seconds(cue['start']), seconds(cue['end'])
        if jobs and start < jobs[-1]['end'] - 0.05:
            raise ValueError('يوجد تداخل في توقيت المتحدثين؛ راجع الجدول قبل التحريك')
        if end <= start:
            raise ValueError('توقيت نهاية الكلام يجب أن يلي بدايته')
        if jobs and jobs[-1]['speaker'] == speaker and start - jobs[-1]['end'] <= 0.35 and end - jobs[-1]['start'] <= max_seconds:
            jobs[-1]['end'] = end
        else:
            jobs.append({'start': start, 'end': end, 'speaker': speaker})
    return jobs


def run(args):
    project = json.loads(Path(args.project).read_text(encoding='utf-8'))
    cues = json.loads(Path(args.timeline).read_text(encoding='utf-8'))
    root = Path(args.sadtalker).resolve()
    inference = root / 'inference.py'
    if args.backend == 'SadTalker':
        needed = ('mapping_00109-model.pth.tar', 'mapping_00229-model.pth.tar', f'SadTalker_V0.0.2_{args.size}.safetensors')
        missing = [name for name in needed if not (root / 'checkpoints' / name).is_file()]
    else:
        needed = ('ditto_cfg/v0.4_hubert_cfg_pytorch.pkl', 'ditto_pytorch/models/decoder.pth')
        missing = [name for name in needed if not (root / 'checkpoints' / name).is_file()]
    if not inference.is_file() or missing:
        raise RuntimeError('محرك ' + args.backend + ' أو نماذجه ناقصة: ' + ', '.join(missing))
    audio = Path(project['audio']).resolve()
    if not audio.is_file():
        raise RuntimeError('ملف البودكاست غير موجود')
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    jobs = build_jobs(cues)
    if args.preview_seconds:
        jobs = [dict(job, end=min(job['end'], args.preview_seconds)) for job in jobs if job['start'] < args.preview_seconds]
        jobs = [job for job in jobs if job['end'] > job['start']]
    manifest = []
    def fingerprint(path):
        with open(path, 'rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()
    audio_hash = fingerprint(audio)
    clip_dir = output / 'clips' / args.backend.lower()
    clip_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='knowcast_animate_') as folder:
        folder = Path(folder)
        for index, job in enumerate(jobs, 1):
            portrait = Path(project['host_image'] if job['speaker'] == 'المذيع' else project['guest_image']).resolve()
            if not portrait.is_file():
                raise RuntimeError(f'الصورة غير موجودة: {portrait}')
            key_data = {'job': job, 'audio': audio_hash, 'portrait': fingerprint(portrait),
                        'backend': args.backend, 'size': args.size, 'cpu': args.cpu,
                        'engine': str(root), 'engine_modified': inference.stat().st_mtime_ns}
            key = hashlib.sha256(json.dumps(key_data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            target = clip_dir / key[:24]
            clip_file = target.with_suffix('.mp4')
            meta_file = target.with_suffix('.json')
            cached = clip_file.is_file() and clip_file.stat().st_size > 1000 and meta_file.is_file() and meta_file.read_text() == key
            if not cached:
                wav = folder / f'{index:04}.wav'
                subprocess.run([args.ffmpeg, '-y', '-v', 'error', '-ss', str(job['start']), '-i', str(audio), '-t', str(job['end']-job['start']), '-ac', '1', '-ar', '16000', str(wav)], check=True)
                if args.backend == 'SadTalker':
                    command = [args.python, str(inference), '--driven_audio', str(wav), '--source_image', str(portrait), '--result_dir', str(target), '--still', '--preprocess', 'full', '--size', str(args.size)]
                    if args.cpu:
                        command.append('--cpu')
                else:
                    command = [args.python, str(inference), '--data_root', str(root / 'checkpoints' / 'ditto_pytorch'), '--cfg_pkl', str(root / 'checkpoints' / 'ditto_cfg' / 'v0.4_hubert_cfg_pytorch.pkl'), '--audio_path', str(wav), '--source_path', str(portrait), '--output_path', str(clip_file)]
                environment = {**os.environ, 'OMP_NUM_THREADS': str(args.threads), 'MKL_NUM_THREADS': str(args.threads)} if args.threads else None
                subprocess.run(command, cwd=root, env=environment, check=True)
                candidates = sorted(target.parent.glob(target.name + '*.mp4'), key=lambda p: p.stat().st_mtime, reverse=True)
                if not candidates and target.is_dir():
                    candidates = sorted(target.rglob('*.mp4'), key=lambda p: p.stat().st_mtime, reverse=True)
                if not candidates or candidates[0].stat().st_size <= 1000:
                    raise RuntimeError(f'{args.backend} لم ينتج فيديو صالحًا للمقطع {index}')
                if candidates[0] != clip_file:
                    shutil.copy2(candidates[0], clip_file)
                meta_file.write_text(key)
            else:
                print(f'مقطع محفوظ {index}/{len(jobs)}', flush=True)
            manifest.append({**job, 'video': str(clip_file)})
            (output / 'animation_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f'{index}/{len(jobs)}: {job["speaker"]}', flush=True)
    # Render each shot separately to keep FFmpeg's filter graph small and allow resume.
    from PySide6.QtWidgets import QApplication
    from app import make_background
    qt = QApplication.instance() or QApplication([])
    background = output / 'studio_background.png'
    make_background(project, background)
    seated = bool(project.get('composed_scene'))
    target_faces = {}
    if seated:
        import cv2
        backdrop = cv2.imread(str(background))
        target_faces = {role: crop_box(detect_face(background, side), backdrop.shape[1], backdrop.shape[0], 1.4) for role, side in [('المذيع', 'left'), ('الخبير', 'right')]}
    sequence = []
    cursor = 0.0
    for index, job in enumerate(manifest, 1):
        if job['start'] > cursor + 0.02:
            sequence.append((cursor, job['start'], None, None))
        sequence.append((job['start'], job['end'], job['video'], job['speaker']))
        cursor = max(cursor, job['end'])
    duration = float(subprocess.check_output([str(Path(args.ffmpeg).with_name('ffprobe.exe' if Path(args.ffmpeg).suffix == '.exe' else 'ffprobe')), '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(audio)], text=True).strip())
    duration = min(duration, args.preview_seconds) if args.preview_seconds else duration
    if duration > cursor + 0.02:
        sequence.append((cursor, duration, None, None))
    shots = []
    background_hash = fingerprint(background)
    for index, (start, end, face, speaker) in enumerate(sequence, 1):
        shot = output / f'shot_{index:04}.mp4'
        length = end - start
        face_info = (str(face), Path(face).stat().st_size, Path(face).stat().st_mtime_ns) if face else None
        shot_key = hashlib.sha256(json.dumps([start, end, face_info, speaker, seated, background_hash]).encode()).hexdigest()
        shot_meta = output / f'shot_{index:04}.sha256'
        if shot.is_file() and shot.stat().st_size > 1000 and shot_meta.is_file() and shot_meta.read_text() == shot_key:
            shots.append(shot)
            continue
        if face:
            cmd = [args.ffmpeg, '-y', '-v', 'error', '-loop', '1', '-framerate', '30', '-i', str(background), '-i', face]
            if seated:
                import cv2
                frame = output / f'face_frame_{index:04}.png'
                subprocess.run([args.ffmpeg, '-y', '-v', 'error', '-i', face, '-frames:v', '1', str(frame)], check=True)
                source = cv2.imread(str(frame))
                sx, sy, sw, sh = crop_box(detect_face(frame), source.shape[1], source.shape[0], 1.4)
                tx, ty, tw, th = target_faces[speaker]
                mask = output / f'face_mask_{speaker}.png'
                if not mask.is_file():
                    create_mask(tw, th, mask)
                cmd += ['-loop', '1', '-i', str(mask)]
                graph = f'[1:v]crop={sw}:{sh}:{sx}:{sy},scale={tw}:{th},format=rgba[face];[2:v]scale={tw}:{th},format=gray[mask];[face][mask]alphamerge[patch];[0:v][patch]overlay={tx}:{ty}:eof_action=repeat:shortest=0[out]'
            else:
                x = 175 if speaker == 'المذيع' else 1365
                graph = f'[1:v]scale=380:360:force_original_aspect_ratio=increase,crop=380:360[face];[0:v][face]overlay={x}:445:eof_action=repeat:shortest=0[out]'
            cmd += ['-filter_complex', graph, '-map', '[out]']
        else:
            cmd = [args.ffmpeg, '-y', '-v', 'error', '-loop', '1', '-framerate', '30', '-i', str(background)]
        cmd += ['-t', str(length), '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', str(shot)]
        subprocess.run(cmd, check=True)
        shot_meta.write_text(shot_key)
        shots.append(shot)
    concat = output / 'shots.txt'
    concat.write_text(''.join("file '" + str(p).replace("'", "'\\''") + "'\n" for p in shots), encoding='utf-8')
    silent = output / 'silent.mp4'
    subprocess.run([args.ffmpeg, '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(concat), '-c', 'copy', str(silent)], check=True)
    final = output / ('KNOW_CAST_preview.mp4' if args.preview_seconds else 'KNOW_CAST_animated.mp4')
    cmd = [args.ffmpeg, '-y', '-v', 'error', '-i', str(silent), '-i', str(audio), '-map', '0:v:0', '-map', '1:a:0']
    subtitle = project.get('subtitles')
    if subtitle and Path(subtitle).is_file():
        escaped = str(Path(subtitle).resolve()).replace('\\', '/').replace(':', '\\:').replace("'", "\\'")
        cmd += ['-vf', f"subtitles='{escaped}'", '-c:v', 'libx264', '-preset', 'medium', '-crf', '20']
    else:
        cmd += ['-c:v', 'copy']
    cmd += ['-c:a', 'aac', '-b:a', '192k', '-t', str(duration), '-movflags', '+faststart', str(final)]
    subprocess.run(cmd, check=True)
    print(f'تم إنشاء الفيديو: {final}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--timeline', required=True)
    parser.add_argument('--sadtalker', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--preview-seconds', type=float, default=0)
    parser.add_argument('--backend', choices=('SadTalker', 'Ditto'), default='SadTalker')
    parser.add_argument('--size', type=int, choices=(256, 512), default=256)
    parser.add_argument('--cpu', action='store_true')
    parser.add_argument('--threads', type=int, default=0)
    args = parser.parse_args()
    run(args)
