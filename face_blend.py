"""Locate faces and create soft masks for seated-scene face replacement."""
from pathlib import Path


def detect_face(image_path, side=None):
    import cv2
    image = cv2.imread(str(image_path))
    if image is None:
        raise RuntimeError(f'تعذر فتح الصورة: {image_path}')
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = detector.detectMultiScale(gray, scaleFactor=1.05, minNeighbors=4, minSize=(28, 28))
    if side:
        faces = [box for box in faces if ((box[0] + box[2]/2 < image.shape[1]/2) == (side == 'left'))]
    if not len(faces):
        raise RuntimeError(f'لم يُكتشف وجه واضح في {image_path}. اختر صورة أمامية أو مشهدًا أوضح.')
    return tuple(map(int, max(faces, key=lambda box: box[2] * box[3])))


def create_mask(width, height, path):
    from PIL import Image, ImageDraw, ImageFilter
    mask = Image.new('L', (width, height), 0)
    draw = ImageDraw.Draw(mask)
    inset = max(4, min(width, height) // 12)
    draw.ellipse((inset, inset, width-inset, height-inset), fill=255)
    mask.filter(ImageFilter.GaussianBlur(max(3, inset // 2))).save(path)


def crop_box(face, image_width, image_height, multiplier=1.4):
    x, y, w, h = face
    nw, nh = min(image_width, int(w * multiplier)), min(image_height, int(h * multiplier))
    left = max(0, min(image_width - nw, round(x + w/2 - nw/2)))
    top = max(0, min(image_height - nh, round(y + h/2 - nh/2)))
    return left, top, nw, nh
