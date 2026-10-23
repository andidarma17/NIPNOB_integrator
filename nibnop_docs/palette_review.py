"""Development-only colour-vision and grayscale preview for the PDF theme.

Run with NumPy and Pillow; neither package is loaded by the QGIS plugin.
Matrices are the severity-1 precomputed Machado et al. simulation matrices.
This is a visual screen, not a clinical validation or a print proof.
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

PALETTE = [
    ('BPN / struktur', '#243B76'),
    ('PBB', '#9AA9B2'),
    ('Level 1', '#096B63'),
    ('Level 2', '#D4D9DD'),
    ('Teks Level 2', '#35414A'),
    ('Tanpa pasangan', '#E4E8EB'),
    ('Overlap / peringatan', '#A42C3A'),
    ('Gap', '#788892'),
    ('Invalid awal', '#53636E'),
]
MATRICES = {
    'Normal': np.eye(3),
    'Protanopia': np.array([[.152286, 1.052583, -.204868],
                            [.114503, .786281, .099216],
                            [-.003882, -.048116, 1.051998]]),
    'Deuteranopia': np.array([[.367322, .860646, -.227968],
                              [.280085, .672501, .047413],
                              [-.011820, .042940, .968881]]),
    'Tritanopia*': np.array([[1.255528, -.076749, -.178779],
                             [-.078411, .930809, .147602],
                             [.004733, .691367, .303900]]),
}


def linear(rgb):
    return np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)


def srgb(rgb):
    rgb = np.clip(rgb, 0, 1)
    return np.where(rgb <= .0031308, rgb * 12.92, 1.055 * rgb ** (1 / 2.4) - .055)


def simulate(hex_value, matrix):
    rgb = np.array([int(hex_value[i:i+2], 16) for i in (1, 3, 5)]) / 255
    return tuple(np.rint(srgb(matrix @ linear(rgb)) * 255).astype(int))


width, row_h = 1170, 74
image = Image.new('RGB', (width, 135 + row_h * len(PALETTE)), 'white')
draw = ImageDraw.Draw(image)
font_path = Path(__file__).resolve().parents[1] / 'fonts' / 'SourceSans3-Regular.ttf'
font = ImageFont.truetype(str(font_path), 19)
small = ImageFont.truetype(str(font_path), 15)
heads = list(MATRICES) + ['Abu-abu']
draw.text((20, 10), 'Uji palet laporan PDF · simulasi layar', font=font, fill='#202831')
draw.text((20, 42), '* Simulasi tritanopia bersifat perkiraan; cek juga tanda bentuk dan label.', font=small, fill='#44515C')
for j, name in enumerate(heads):
    draw.text((285 + j * 174, 95), name, font=small, fill='#202831')
for i, (role, hex_value) in enumerate(PALETTE):
    y = 125 + i * row_h
    draw.text((20, y + 9), role, font=font, fill='#202831')
    draw.text((20, y + 35), hex_value, font=small, fill='#44515C')
    for j, matrix in enumerate(MATRICES.values()):
        fill = simulate(hex_value, matrix)
        draw.rectangle((285 + j * 174, y, 430 + j * 174, y + 50), fill=fill, outline='#44515C')
    orig = np.array([int(hex_value[k:k+2], 16) for k in (1, 3, 5)]) / 255
    lum = float(np.array([.2126, .7152, .0722]) @ linear(orig))
    gray = round(srgb(np.array([lum]))[0] * 255)
    draw.rectangle((285 + 4 * 174, y, 430 + 4 * 174, y + 50), fill=(gray, gray, gray), outline='#44515C')
image.save(Path(__file__).with_name('palette_review.png'))
