import base64
import secrets
import struct
import zlib


_DIGITS = {
    "0": ("111", "101", "101", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "010", "010", "111"),
    "2": ("111", "001", "001", "111", "100", "100", "111"),
    "3": ("111", "001", "001", "111", "001", "001", "111"),
    "4": ("101", "101", "101", "111", "001", "001", "001"),
    "5": ("111", "100", "100", "111", "001", "001", "111"),
    "6": ("111", "100", "100", "111", "101", "101", "111"),
    "7": ("111", "001", "001", "010", "010", "010", "010"),
    "8": ("111", "101", "101", "111", "101", "101", "111"),
    "9": ("111", "101", "101", "111", "001", "001", "111"),
}


def make_numeric_code(length: int = 4) -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def captcha_png_data_uri(code: str, width: int = 160, height: int = 52) -> str:
    background = (244, 249, 247)
    pixels = [list(background) for _ in range(width * height)]

    def set_pixel(x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < width and 0 <= y < height:
            pixels[y * width + x] = list(color)

    for _ in range(220):
        set_pixel(
            secrets.randbelow(width),
            secrets.randbelow(height),
            (170 + secrets.randbelow(55), 180 + secrets.randbelow(45), 176 + secrets.randbelow(45)),
        )

    for line_index in range(3):
        color = ((52, 128, 119), (182, 103, 53), (91, 108, 146))[line_index]
        y = 8 + secrets.randbelow(height - 16)
        slope = secrets.choice((-1, 1))
        for x in range(width):
            set_pixel(x, y + slope * (x - width // 2) // 18, color)

    scale = 5
    start_x = 17
    colors = ((25, 91, 84), (64, 76, 73), (156, 76, 42), (42, 100, 92))
    for index, char in enumerate(code):
        glyph = _DIGITS[char]
        x0 = start_x + index * 34 + secrets.randbelow(3)
        y0 = 8 + secrets.randbelow(4)
        color = colors[index % len(colors)]
        for row, bits in enumerate(glyph):
            for column, bit in enumerate(bits):
                if bit == "1":
                    for dy in range(scale):
                        for dx in range(scale):
                            set_pixel(x0 + column * scale + dx, y0 + row * scale + dy, color)

    raw = b"".join(
        b"\x00" + bytes(channel for pixel in pixels[y * width : (y + 1) * width] for channel in pixel)
        for y in range(height)
    )

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")
