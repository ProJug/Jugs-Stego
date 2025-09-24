# backend/app/stego.py
import struct
from io import BytesIO
from PIL import Image
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes
import os

MAGIC = b'PSMG'
SALT_LEN = 16
NONCE_LEN = 12
TAG_LEN = 16
AES_KEY_LEN = 32
# Allow tuning on constrained hosts; default solid
PBKDF2_ITERS = int(os.getenv("PBKDF2_ITERS", "200000"))

def bytes_to_bits(b: bytes):
    for byte in b:
        for i in range(7, -1, -1):
            yield (byte >> i) & 1

def bits_to_bytes(bits):
    b = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for bit in bits[i:i+8]:
            byte = (byte << 1) | bit
        b.append(byte)
    return bytes(b)

def _ensure_rgb(img: Image.Image) -> Image.Image:
    if img.mode not in ('RGB','RGBA'):
        return img.convert('RGBA')
    return img

def capacity_bytes_for_image_bytes(cover_bytes: bytes) -> int:
    img = Image.open(BytesIO(cover_bytes))
    img = _ensure_rgb(img)
    return (img.width * img.height * 3) // 8

def _embed_bits_into_image(img: Image.Image, bits):
    pixels = list(img.getdata())
    bits = list(bits)
    total_channels = len(pixels) * 3
    if len(bits) > total_channels:
        raise ValueError("Not enough capacity in image for payload")
    out_pixels = []
    bit_idx = 0
    for px in pixels:
        ch = list(px)
        for c in range(3):  # R,G,B
            if bit_idx < len(bits):
                ch[c] = (ch[c] & ~1) | bits[bit_idx]
                bit_idx += 1
        out_pixels.append(tuple(ch))
    out_img = Image.new('RGBA' if img.mode == 'RGBA' else 'RGB', img.size)
    out_img.putdata(out_pixels)
    return out_img

def _encrypt_payload(plaintext_bytes: bytes, passphrase: str):
    salt = get_random_bytes(SALT_LEN)
    key = PBKDF2(passphrase, salt, dkLen=AES_KEY_LEN, count=PBKDF2_ITERS)
    nonce = get_random_bytes(NONCE_LEN)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext_bytes)
    return salt, nonce, ciphertext + tag

def build_embedded_payload(plaintext_bytes: bytes, passphrase: str) -> bytes:
    salt, nonce, ct_and_tag = _encrypt_payload(plaintext_bytes, passphrase)
    parts = [
        MAGIC,
        salt,
        nonce,
        struct.pack('>I', len(ct_and_tag)),
        ct_and_tag
    ]
    return b''.join(parts)

def embed_into_png_bytes(cover_bytes: bytes, payload_bytes: bytes) -> bytes:
    img = Image.open(BytesIO(cover_bytes))
    img = _ensure_rgb(img)
    capacity_bits = img.width * img.height * 3
    if len(payload_bytes) * 8 > capacity_bits:
        raise ValueError(f"Payload too large. Capacity: {capacity_bits//8} bytes, payload: {len(payload_bytes)} bytes")
    out_img = _embed_bits_into_image(img, bytes_to_bits(payload_bytes))
    out = BytesIO()
    out_img.save(out, 'PNG')
    return out.getvalue()

def extract_from_png_bytes(stego_bytes: bytes, passphrase: str) -> bytes:
    img = Image.open(BytesIO(stego_bytes))
    img = _ensure_rgb(img)
    pixels = list(img.getdata())
    bits = []
    for px in pixels:
        for c in range(3):
            bits.append(px[c] & 1)

    header_bits = bits[:288]  # 36 bytes
    header = bits_to_bytes(header_bits)
    if header[:4] != MAGIC:
        raise ValueError("MAGIC not found — not a valid stego payload")

    salt = header[4:4+SALT_LEN]
    nonce = header[4+SALT_LEN:4+SALT_LEN+NONCE_LEN]
    ct_len = struct.unpack('>I', header[4+SALT_LEN+NONCE_LEN:4+SALT_LEN+NONCE_LEN+4])[0]

    total_payload_bytes = 4 + SALT_LEN + NONCE_LEN + 4 + ct_len
    total_payload_bits = total_payload_bytes * 8
    if total_payload_bits > len(bits):
        raise ValueError("Truncated payload in image")

    payload = bits_to_bytes(bits[:total_payload_bits])
    ct_and_tag = payload[4+SALT_LEN+NONCE_LEN+4:]

    key = PBKDF2(passphrase, salt, dkLen=AES_KEY_LEN, count=PBKDF2_ITERS)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    try:
        plaintext = cipher.decrypt_and_verify(ct_and_tag[:-TAG_LEN], ct_and_tag[-TAG_LEN:])
    except Exception as e:
        raise ValueError("Decryption/verification failed (wrong passphrase or corrupted data)") from e
    return plaintext
