import json
import os
import tempfile
import shutil
import subprocess
import sys
from pathlib import Path
from captions import parse_srt, save_ass

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar,
    QPushButton, QVBoxLayout, QWidget, QDialog, QTableWidget, QTableWidgetItem, QSpinBox, QScrollArea)

ROOT = Path(__file__).resolve().parent


def find_ffmpeg():
    bundled = ROOT / 'tools' / 'ffmpeg' / 'bin' / 'ffmpeg.exe'
    return str(bundled) if bundled.exists() else shutil.which('ffmpeg')


class ExportThread(QThread):
    progress = Signal(int)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, settings, output):
        super().__init__()
        self.settings, self.output = settings, output

    def run(self):
        try:
            ffmpeg = find_ffmpeg()
            if not ffmpeg:
                raise RuntimeError('FFmpeg غير موجود. ضع ffmpeg.exe داخل tools/ffmpeg/bin أو ثبّته في PATH.')
            workdir = tempfile.TemporaryDirectory(prefix='knowcast_')
            temp = Path(workdir.name) / 'background.png'
            make_background(self.settings, temp)
            audio = self.settings['audio']
            duration = subprocess.check_output([ffmpeg.replace('ffmpeg.exe', 'ffprobe.exe') if ffmpeg.endswith('ffmpeg.exe') else 'ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio], text=True).strip()
            logo = self.settings.get('logo')
            subtitles = self.settings.get('subtitles')
            inputs = [ffmpeg, '-y', '-loop', '1', '-framerate', '30', '-i', str(temp), '-i', audio]
            if logo:
                inputs += ['-loop', '1', '-i', logo]
            color = '0xE8B86B' if self.settings['theme'] == 'زمردي وذهبي' else '0x65C7F7'
            graph = f'[1:a]aformat=channel_layouts=mono,showwaves=s=1500x95:mode=line:colors={color}:rate=30,format=rgba[w];[0:v][w]overlay=(W-w)/2:840[v]'
            if logo:
                graph += ';[2:v]scale=180:-1[logo];[v][logo]overlay=60:55[out]'
            else:
                graph += ';[v]null[out]'
            if subtitles:
                escaped = str(Path(subtitles).resolve()).replace('\\', '/').replace(':', '\\:').replace("'", "\\'")
                style = '' if subtitles.lower().endswith('.ass') else ":force_style='FontName=Arial,FontSize=22,Outline=2,Alignment=2,MarginV=160'"
                graph += f";[out]subtitles='{escaped}'{style}[final]"
                video_map = '[final]'
            else:
                video_map = '[out]'
            encoder = 'h264_nvenc' if self.settings.get('encoder') == 'NVIDIA' else 'libx264'
            if encoder == 'h264_nvenc':
                available = subprocess.run([ffmpeg, '-hide_banner', '-encoders'], capture_output=True, text=True).stdout
                if 'h264_nvenc' not in available:
                    raise RuntimeError('تسريع NVIDIA غير متاح في نسخة FFmpeg الحالية. اختر CPU.')
            cmd = inputs + ['-filter_complex', graph, '-map', video_map, '-map', '1:a:0', '-t', duration, '-c:v', encoder, '-preset', 'medium' if encoder == 'libx264' else 'p4', '-crf' if encoder == 'libx264' else '-cq', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-progress', 'pipe:1', '-nostats', self.output]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
            total = float(duration)
            for line in process.stdout:
                if line.startswith('out_time_ms='):
                    try:
                        self.progress.emit(min(99, round(float(line.split('=', 1)[1]) / 1_000_000 / total * 100)))
                    except ValueError:
                        pass
            error = process.stderr.read()
            if process.wait():
                raise RuntimeError(error[-1800:])
            self.progress.emit(100)
            workdir.cleanup()
            self.finished_ok.emit(self.output)
        except Exception as exc:
            self.failed.emit(str(exc))


def make_background(settings, target):
    image = QPixmap(1920, 1080)
    dark = settings['theme'] == 'زمردي وذهبي'
    composed = settings.get('composed_scene')
    stage = composed or settings.get('studio') or str(ROOT / 'assets' / 'know_cast_studio.png')
    studio = QPixmap(stage)
    if studio.isNull():
        image.fill(QColor('#073b32' if dark else '#102943'))
    else:
        image = studio.scaled(1920, 1080, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QColor('#e8b86b' if dark else '#65c7f7'))
    painter.setFont(QFont('Segoe UI', 62, QFont.Bold))
    if studio.isNull():
        painter.drawText(410, 35, 1100, 125, Qt.AlignHCenter | Qt.TextWordWrap, settings['title'])
    painter.setPen(QColor('#e8eee9'))
    painter.setFont(QFont('Segoe UI', 32))
    if studio.isNull():
        painter.drawText(140, 380, 1640, 100, Qt.AlignHCenter, settings['subtitle'])
    for key, x, label in ([] if composed else [('host_image', 175, settings.get('host', 'المذيع')), ('guest_image', 1365, settings.get('guest', 'الخبير'))]):
        portrait_path = settings.get(key)
        if portrait_path:
            portrait = QPixmap(portrait_path)
            if not portrait.isNull():
                # Portrait cards keep the two sources replaceable without assuming transparency.
                painter.fillRect(x-7, 438, 394, 420, QColor('#cda65b'))
                portrait = portrait.scaled(380, 360, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                painter.save()
                painter.setClipRect(x, 445, 380, 360)
                painter.drawPixmap(x, 445, portrait)
                painter.restore()
                painter.fillRect(x, 805, 380, 46, QColor(5, 37, 29, 230))
                painter.setPen(QColor('#f6d49a'))
                painter.setFont(QFont('Segoe UI', 25, QFont.Bold))
                painter.drawText(x, 805, 380, 46, Qt.AlignCenter, label)
    painter.setPen(QColor('#ffffff'))
    painter.setFont(QFont('Segoe UI', 25))
    painter.drawText(100, 960, 1720, 65, Qt.AlignHCenter, settings['footer'])
    painter.end()
    if not image.save(str(target)):
        raise RuntimeError('تعذر إنشاء الخلفية')


class TranscriptionThread(QThread):
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, audio, output, language):
        super().__init__()
        self.audio, self.output, self.language = audio, output, language

    def run(self):
        process = subprocess.run([sys.executable, str(ROOT / 'transcribe.py'), self.audio, self.output, '--language', self.language], capture_output=True, text=True)
        if process.returncode:
            self.failed.emit(process.stderr[-1200:])
        else:
            self.finished_ok.emit(self.output)


class CutoutThread(QThread):
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, source, output):
        super().__init__()
        self.source, self.output = source, output

    def run(self):
        try:
            from PIL import Image
            from rembg import remove, new_session
            result = remove(Image.open(self.source).convert('RGB'), session=new_session('isnet-general-use'))
            result.save(self.output)
            self.finished_ok.emit(self.output)
        except Exception as exc:
            self.failed.emit(str(exc))


class AnimationThread(QThread):
    finished_ok = Signal(str)
    failed = Signal(str)
    status = Signal(str)

    def __init__(self, settings, timeline, engine, output, preview=False):
        super().__init__()
        self.settings, self.timeline, self.engine, self.output, self.preview = settings, timeline, engine, output, preview

    def run(self):
        with tempfile.TemporaryDirectory(prefix='knowcast_job_') as folder:
            project = Path(folder) / 'project.json'
            project.write_text(json.dumps(self.settings, ensure_ascii=False), encoding='utf-8')
            cmd = [sys.executable, str(ROOT / 'animation.py'), '--project', str(project), '--timeline', self.timeline, '--sadtalker', self.engine, '--output', self.output, '--ffmpeg', find_ffmpeg() or 'ffmpeg', '--python', str(Path(self.engine) / '.venv' / 'Scripts' / 'python.exe')]
            cmd += ['--backend', self.settings.get('animation_backend', 'SadTalker'), '--size', str(self.settings.get('animation_size', 256))]
            if self.settings.get('animation_device') == 'CPU':
                cmd += ['--cpu', '--threads', str(self.settings.get('threads', 0))]
            if self.preview:
                cmd += ['--preview-seconds', '20']
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace', env={**os.environ, 'QT_QPA_PLATFORM': os.environ.get('QT_QPA_PLATFORM', 'offscreen')})
            recent = []
            for line in process.stdout:
                recent.append(line.strip())
                recent = recent[-25:]
                if '/' in line and ('المذيع' in line or 'الخبير' in line):
                    self.status.emit(line.strip())
            if process.wait():
                self.failed.emit('\n'.join(recent)[-2500:])
            else:
                self.finished_ok.emit(str(Path(self.output) / ('KNOW_CAST_preview.mp4' if self.preview else 'KNOW_CAST_animated.mp4')))


class DiarizationThread(QThread):
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, audio, subtitles, output, token):
        super().__init__()
        self.audio, self.subtitles, self.output, self.token = audio, subtitles, output, token

    def run(self):
        environment = {**os.environ, 'HF_TOKEN': self.token}
        process = subprocess.run([sys.executable, str(ROOT / 'diarize.py'), self.audio, self.subtitles, self.output, '--ffmpeg', find_ffmpeg() or 'ffmpeg'], capture_output=True, text=True, env=environment)
        if process.returncode:
            self.failed.emit(process.stderr[-1600:])
        else:
            self.finished_ok.emit(self.output)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('KNOW CAST Studio')
        self.resize(1050, 760)
        root = QWidget()
        layout = QVBoxLayout(root)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        scroll.setWidget(body)
        heading = QLabel('KNOW CAST Studio  |  تحويل الصوت إلى فيديو بودكاست')
        heading.setStyleSheet('font-size:22px;font-weight:bold;color:#e8b86b')
        layout.addWidget(heading)
        form = QFormLayout()
        self.audio = QLineEdit()
        self.logo = QLineEdit()
        self.subtitles = QLineEdit()
        self.host_image = QLineEdit()
        self.guest_image = QLineEdit()
        self.hf_token = QLineEdit()
        self.hf_token.setEchoMode(QLineEdit.Password)
        self.hf_token.setPlaceholderText('رمز Hugging Face؛ لا يُحفظ مع المشروع')
        self.engine = QLineEdit()
        self.engine.setPlaceholderText('مجلد المحرك المثبت بنماذجه')
        self.composed_scene = QLineEdit()
        self.composed_scene.setPlaceholderText('اختياري: لقطة الشخصيات جالسة لتصدير فيديو ثابت')
        self.studio = QLineEdit()
        self.studio.setPlaceholderText('القالب الافتراضي، أو اختر صورة استوديو أخرى')
        for label, field, filters in [('ملف الصوت', self.audio, 'Audio (*.m4a *.mp3 *.wav *.aac *.flac)'), ('الشعار (اختياري)', self.logo, 'Images (*.png *.jpg *.jpeg)'), ('الترجمة (اختياري)', self.subtitles, 'Subtitles (*.srt *.ass)'), ('صورة المذيع', self.host_image, 'Images (*.png *.jpg *.jpeg)'), ('صورة الخبير', self.guest_image, 'Images (*.png *.jpg *.jpeg)'), ('الاستوديو', self.studio, 'Images (*.png *.jpg *.jpeg)'), ('مشهد الجلوس', self.composed_scene, 'Images (*.png *.jpg *.jpeg)')]:
            row = QHBoxLayout()
            row.addWidget(field)
            button = QPushButton('اختيار')
            button.clicked.connect(lambda _, f=field, fl=filters: self.choose(f, fl))
            row.addWidget(button)
            form.addRow(label, row)
        self.title = QLineEdit('عنوان البودكاست')
        self.subtitle = QLineEdit('حوار ومعرفة بصورة أوضح')
        self.footer = QLineEdit('')
        self.host = QLineEdit('المذيع')
        self.guest = QLineEdit('الخبير')
        self.theme = QComboBox()
        self.theme.addItems(['زمردي وذهبي', 'أزرق سماوي'])
        self.language = QComboBox()
        self.language.addItem('تلقائي', 'auto')
        self.language.addItem('العربية', 'ar')
        self.language.addItem('الإنجليزية', 'en')
        self.animation_backend = QComboBox()
        self.animation_backend.addItems(['SadTalker', 'Ditto'])
        self.animation_device = QComboBox()
        self.animation_device.addItems(['CPU', 'NVIDIA'])
        self.animation_size = QComboBox()
        self.animation_size.addItems(['256', '512'])
        self.threads = QSpinBox()
        self.threads.setRange(0, 112)
        self.threads.setValue(0)
        self.threads.setSpecialValueText('تلقائي')
        self.encoder = QComboBox()
        self.encoder.addItems(['CPU', 'NVIDIA'])
        for name, widget in [('العنوان', self.title), ('الوصف', self.subtitle), ('تذييل اختياري', self.footer), ('اسم المذيع', self.host), ('اسم الخبير', self.guest), ('القالب', self.theme), ('لغة الكلام', self.language), ('التصدير', self.encoder), ('محرك التحريك', self.animation_backend), ('جهاز التحريك', self.animation_device), ('جودة الوجه', self.animation_size), ('خيوط CPU', self.threads)]:
            form.addRow(name, widget)
        form.addRow('مجلد محرك التحريك', self.engine)
        form.addRow('رمز فصل المتحدثين', self.hf_token)
        body_layout.addLayout(form)
        layout.addWidget(scroll)
        top_actions = QHBoxLayout()
        row = QHBoxLayout()
        preview = QPushButton('معاينة المشهد')
        preview.clicked.connect(self.preview_scene)
        top_actions.addWidget(preview)
        cutout = QPushButton('قص خلفية شخصية')
        cutout.clicked.connect(self.cutout_portrait)
        top_actions.addWidget(cutout)
        transcribe = QPushButton('تفريغ الكلام تلقائيًا')
        transcribe.clicked.connect(self.transcribe_audio)
        top_actions.addWidget(transcribe)
        diarize = QPushButton('اقتراح المتحدثين آليًا')
        diarize.clicked.connect(self.diarize_audio)
        top_actions.addWidget(diarize)
        edit = QPushButton('مراجعة المتحدثين')
        edit.clicked.connect(self.edit_captions)
        top_actions.addWidget(edit)
        save = QPushButton('حفظ المشروع')
        save.clicked.connect(self.save_project)
        load = QPushButton('فتح مشروع')
        load.clicked.connect(self.load_project)
        export = QPushButton('تصدير MP4')
        export.clicked.connect(self.export_video)
        preview_animation = QPushButton('تجربة تحريك 20 ثانية')
        preview_animation.clicked.connect(lambda: self.animate_video(preview=True))
        row.addWidget(preview_animation)
        animate = QPushButton('إنتاج فيديو متحرك')
        animate.clicked.connect(self.animate_video)
        for button in (save, load, export, animate):
            row.addWidget(button)
        layout.addLayout(top_actions)
        layout.addLayout(row)
        self.bar = QProgressBar()
        layout.addWidget(self.bar)
        self.status_label = QLabel('جاهز')
        layout.addWidget(self.status_label)
        note = QLabel('الصوت الأصلي هو مصدر الفيديو. التصدير محلي بالكامل، ولا يرفع الملف لأي خدمة.')
        layout.addWidget(note)
        self.setCentralWidget(root)
        self.setStyleSheet('QWidget{background:#102d29;color:#f5f5f5;font-size:15px} QLineEdit,QComboBox{background:#1d4640;padding:8px;border:1px solid #53736a;border-radius:5px} QPushButton{background:#bc9254;color:#102d29;padding:10px;border-radius:6px;font-weight:bold}')

    def choose(self, field, filters):
        path, _ = QFileDialog.getOpenFileName(self, 'اختر ملفًا', '', filters)
        if path:
            field.setText(path)

    def cutout_portrait(self):
        from PySide6.QtWidgets import QInputDialog
        label, accepted = QInputDialog.getItem(self, 'قص الخلفية', 'اختر الصورة:', ['المذيع', 'الخبير'], 0, False)
        if not accepted:
            return
        field = self.host_image if label == 'المذيع' else self.guest_image
        source = field.text().strip()
        if not Path(source).is_file():
            QMessageBox.warning(self, 'الصورة', 'اختر صورة الشخصية أولًا')
            return
        target, _ = QFileDialog.getSaveFileName(self, 'حفظ صورة شفافة', str(Path(source).with_name(Path(source).stem + '_cutout.png')), 'PNG (*.png)')
        if not target:
            return
        self.status_label.setText('جارٍ قص الخلفية... قد يُنزّل النموذج أول مرة')
        self.cutout_worker = CutoutThread(source, target)
        self.cutout_worker.finished_ok.connect(lambda path: (field.setText(path), self.status_label.setText('الصورة الشفافة جاهزة'), QMessageBox.information(self, 'تم', path)))
        self.cutout_worker.failed.connect(lambda error: QMessageBox.critical(self, 'تعذر قص الخلفية', error))
        self.cutout_worker.start()

    def values(self):
        return dict(audio=self.audio.text().strip(), logo=self.logo.text().strip(), subtitles=self.subtitles.text().strip(), title=self.title.text().strip(), subtitle=self.subtitle.text().strip(), footer=self.footer.text().strip(), host=self.host.text().strip(), guest=self.guest.text().strip(), host_image=self.host_image.text().strip(), guest_image=self.guest_image.text().strip(), studio=self.studio.text().strip(), composed_scene=self.composed_scene.text().strip(), theme=self.theme.currentText(), encoder=self.encoder.currentText(), language=self.language.currentData(), animation_backend=self.animation_backend.currentText(), animation_device=self.animation_device.currentText(), animation_size=int(self.animation_size.currentText()), threads=self.threads.value(), engine=self.engine.text().strip())

    def save_project(self):
        path, _ = QFileDialog.getSaveFileName(self, 'حفظ المشروع', '', 'KNOW CAST (*.knowcast.json)')
        if path:
            data = self.values()
            base = Path(path).resolve().parent
            for key in ('audio', 'logo', 'subtitles', 'host_image', 'guest_image', 'studio', 'composed_scene', 'engine'):
                if data.get(key):
                    try:
                        data[key] = os.path.relpath(data[key], base)
                    except ValueError:
                        pass
            Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    def load_project(self):
        path, _ = QFileDialog.getOpenFileName(self, 'فتح المشروع', '', 'KNOW CAST (*.knowcast.json)')
        if path:
            data = json.loads(Path(path).read_text(encoding='utf-8'))
            for key in ('audio', 'logo', 'subtitles', 'title', 'subtitle', 'footer', 'host', 'guest', 'host_image', 'guest_image', 'studio', 'composed_scene', 'engine'):
                value = data.get(key, '')
                if key in ('audio', 'logo', 'subtitles', 'host_image', 'guest_image', 'studio', 'composed_scene', 'engine') and value and not Path(value).is_absolute():
                    value = str((Path(path).resolve().parent / value).resolve())
                getattr(self, key).setText(value)
            self.theme.setCurrentText(data.get('theme', 'زمردي وذهبي'))
            self.encoder.setCurrentText(data.get('encoder', 'CPU'))
            self.language.setCurrentIndex(max(0, self.language.findData(data.get('language', 'auto'))))
            self.animation_backend.setCurrentText(data.get('animation_backend', 'SadTalker'))
            self.animation_device.setCurrentText(data.get('animation_device', 'CPU'))
            self.animation_size.setCurrentText(str(data.get('animation_size', 256)))
            self.threads.setValue(int(data.get('threads', 0)))

    def preview_scene(self):
        with tempfile.TemporaryDirectory(prefix='knowcast_preview_') as folder:
            path = Path(folder) / 'preview.png'
            make_background(self.values(), path)
            picture = QPixmap(str(path)).scaled(960, 540, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        dialog = QDialog(self)
        dialog.setWindowTitle('معاينة المشهد الثابت')
        container = QVBoxLayout(dialog)
        label = QLabel()
        label.setPixmap(picture)
        container.addWidget(label)
        dialog.exec()

    def transcribe_audio(self):
        audio = self.audio.text().strip()
        if not Path(audio).is_file():
            QMessageBox.warning(self, 'ملف الصوت', 'اختر ملف صوت موجودًا أولًا')
            return
        path, _ = QFileDialog.getSaveFileName(self, 'حفظ التفريغ', str(Path(audio).with_suffix('.srt')), 'SRT (*.srt)')
        if not path:
            return
        self.transcriber = TranscriptionThread(audio, path, self.language.currentData())
        self.transcriber.finished_ok.connect(self.transcription_done)
        self.transcriber.failed.connect(lambda message: QMessageBox.critical(self, 'فشل التفريغ', message))
        self.transcriber.start()

    def transcription_done(self, path):
        self.subtitles.setText(path)
        QMessageBox.information(self, 'تم التفريغ', 'تم حفظ ملف SRT. راجع النص وعدله بمحرر نصوص قبل التصدير.')

    def diarize_audio(self):
        audio, source = self.audio.text().strip(), self.subtitles.text().strip()
        if not Path(audio).is_file() or not source.lower().endswith('.srt') or not Path(source).is_file():
            QMessageBox.warning(self, 'ملفات ناقصة', 'اختر الصوت وملف SRT أولًا')
            return
        if not self.hf_token.text().strip():
            QMessageBox.warning(self, 'رمز الوصول', 'أدخل رمز Hugging Face بعد قبول شروط النموذج')
            return
        output = str(Path(source).with_suffix('.timeline.json'))
        self.diarizer = DiarizationThread(audio, source, output, self.hf_token.text().strip())
        self.diarizer.finished_ok.connect(lambda _: QMessageBox.information(self, 'تم', 'تم اقتراح المتحدثين. افتح «مراجعة المتحدثين» للتأكد.'))
        self.diarizer.failed.connect(lambda message: QMessageBox.critical(self, 'فشل الفصل', message))
        self.diarizer.start()

    def edit_captions(self):
        source = self.subtitles.text().strip()
        if not source.lower().endswith('.srt') or not Path(source).is_file():
            QMessageBox.warning(self, 'التفريغ', 'اختر ملف SRT أولًا')
            return
        cues = parse_srt(source)
        timeline_file = Path(source).with_suffix('.timeline.json')
        if timeline_file.is_file():
            suggested = json.loads(timeline_file.read_text(encoding='utf-8'))
            if len(suggested) == len(cues):
                for cue, proposal in zip(cues, suggested):
                    cue['speaker'] = proposal.get('speaker', 'المذيع')
        if not cues:
            QMessageBox.warning(self, 'التفريغ', 'لم أجد سطورًا صالحة في ملف SRT')
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('مراجعة النص والمتحدثين')
        dialog.resize(900, 600)
        layout = QVBoxLayout(dialog)
        table = QTableWidget(len(cues), 4)
        table.setHorizontalHeaderLabels(['البداية', 'النهاية', 'المتحدث', 'النص'])
        for row, cue in enumerate(cues):
            for col, key in enumerate(('start', 'end', 'speaker', 'text')):
                table.setItem(row, col, QTableWidgetItem(cue[key]))
        table.setColumnWidth(3, 480)
        layout.addWidget(table)
        hint = QLabel('اكتب «المذيع» أو «الخبير» في عمود المتحدث. راجع التوقيت والنص قبل الحفظ.')
        layout.addWidget(hint)
        button = QPushButton('حفظ الترجمة والمتحدثين')
        layout.addWidget(button)
        def commit():
            try:
                edited = []
                for row in range(table.rowCount()):
                    cue = dict(zip(('start', 'end', 'speaker', 'text'), (table.item(row, col).text().strip() for col in range(4))))
                    if cue['speaker'] not in ('المذيع', 'الخبير'):
                        raise ValueError(f'السطر {row + 1}: المتحدث يجب أن يكون المذيع أو الخبير')
                    edited.append(cue)
                output = str(Path(source).with_suffix('.ass'))
                save_ass(edited, output, self.host.text().strip(), self.guest.text().strip())
                Path(source).with_suffix('.timeline.json').write_text(json.dumps(edited, ensure_ascii=False, indent=2), encoding='utf-8')
                self.subtitles.setText(output)
                dialog.accept()
            except Exception as exc:
                QMessageBox.warning(dialog, 'راجع البيانات', str(exc))
        button.clicked.connect(commit)
        dialog.exec()

    def animate_video(self, preview=False):
        data = self.values()
        timeline = str(Path(data['subtitles']).with_suffix('.timeline.json')) if data['subtitles'] else ''
        if not Path(timeline).is_file() or not all(Path(data[key]).is_file() for key in ('audio', 'host_image', 'guest_image')):
            QMessageBox.warning(self, 'ملفات ناقصة', 'اختر الصوت وصور الشخصيتين، ثم راجع المتحدثين واحفظ جدولهم أولًا.')
            return
        if data['animation_backend'] == 'Ditto' and data['animation_device'] == 'CPU':
            QMessageBox.warning(self, 'Ditto', 'محرك Ditto الرسمي يستهدف CUDA؛ اختر NVIDIA أو استخدم SadTalker على CPU.')
            return
        if not (Path(data['engine']) / 'inference.py').is_file():
            QMessageBox.warning(self, 'المحرك', 'حدد مجلد المحرك الذي يحتوي inference.py.')
            return
        output = QFileDialog.getExistingDirectory(self, 'اختر مجلد الفيديو الناتج')
        if not output:
            return
        engine_python = Path(data['engine']) / '.venv' / 'Scripts' / 'python.exe'
        if not engine_python.is_file():
            QMessageBox.warning(self, 'بيئة المحرك', 'يلزم بيئة Python مستقلة داخل مجلد المحرك باسم .venv. راجع الدليل.')
            return
        self.animator = AnimationThread(data, timeline, data['engine'], output, preview=preview)
        self.status_label.setText('جارٍ إنتاج مقاطع المتحدثين...')
        self.animator.status.connect(self.status_label.setText)
        self.animator.finished_ok.connect(lambda path: QMessageBox.information(self, 'تم', path))
        self.animator.failed.connect(lambda message: QMessageBox.critical(self, 'فشل التحريك', message))
        self.animator.start()

    def export_video(self):
        data = self.values()
        if not Path(data['audio']).is_file():
            QMessageBox.warning(self, 'ملف الصوت', 'اختر ملف صوت موجودًا أولًا')
            return
        for image_key in ('host_image', 'guest_image', 'studio', 'composed_scene'):
            if data[image_key] and not Path(data[image_key]).is_file():
                QMessageBox.warning(self, 'الصورة', 'ملف صورة أحد المتحدثين غير موجود')
                return
        if data['subtitles'] and not Path(data['subtitles']).is_file():
            QMessageBox.warning(self, 'الترجمة', 'ملف SRT غير موجود')
            return
        if data['logo'] and not Path(data['logo']).is_file():
            QMessageBox.warning(self, 'الشعار', 'ملف الشعار غير موجود')
            return
        path, _ = QFileDialog.getSaveFileName(self, 'تصدير', '', 'MP4 (*.mp4)')
        if path:
            self.bar.setValue(0)
            self.worker = ExportThread(data, path)
            self.worker.progress.connect(self.bar.setValue)
            self.worker.finished_ok.connect(lambda p: QMessageBox.information(self, 'تم', f'تم إنشاء الفيديو:\n{p}'))
            self.worker.failed.connect(lambda message: QMessageBox.critical(self, 'فشل التصدير', message))
            self.worker.start()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
