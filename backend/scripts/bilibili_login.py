#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any


GENERATE_API = (
    "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
    "?source=main-fe-header"
)
POLL_API = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
NAV_API = "https://api.bilibili.com/x/web-interface/nav"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0 Safari/537.36"
)

COOKIE_PRIORITY = [
    "SESSDATA",
    "bili_jct",
    "DedeUserID",
    "DedeUserID__ckMd5",
    "sid",
    "buvid3",
    "buvid4",
    "b_nut",
    "CURRENT_FNVAL",
]


class BilibiliLoginError(RuntimeError):
    pass


def _request_json(opener: urllib.request.OpenerDirector, url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.bilibili.com/",
        },
    )

    try:
        with opener.open(request, timeout=20) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise BilibiliLoginError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise BilibiliLoginError(f"Network error: {exc}") from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise BilibiliLoginError(f"Invalid JSON response: {body[:500]}") from exc

    if payload.get("code") != 0:
        raise BilibiliLoginError(
            f"Bilibili API error: code={payload.get('code')}, "
            f"message={payload.get('message')}"
        )
    return payload


def _create_opener(cookie_jar: CookieJar) -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))


def generate_login_qr(
    opener: urllib.request.OpenerDirector,
) -> tuple[str, str]:
    payload = _request_json(opener, GENERATE_API)
    data = payload.get("data") or {}
    login_url = data.get("url")
    qrcode_key = data.get("qrcode_key")

    if not qrcode_key and login_url:
        parsed = urllib.parse.urlparse(login_url)
        qrcode_key = urllib.parse.parse_qs(parsed.query).get("qrcode_key", [""])[0]

    if not login_url or not qrcode_key:
        raise BilibiliLoginError(f"Unexpected QR payload: {payload}")
    return login_url, qrcode_key


def poll_login(
    opener: urllib.request.OpenerDirector,
    qrcode_key: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    poll_url = f"{POLL_API}?{urllib.parse.urlencode({'qrcode_key': qrcode_key})}"
    started_at = time.time()
    last_code: int | None = None

    while True:
        if time.time() - started_at > timeout_seconds:
            raise BilibiliLoginError("Login timed out. Please run this script again.")

        payload = _request_json(opener, poll_url)
        data = payload.get("data") or {}
        code = data.get("code")
        message = data.get("message") or ""

        if code == 0:
            print("[OK] Login confirmed.")
            return data

        if code != last_code:
            if code == 86101:
                print("[WAIT] Waiting for scan in the Bilibili mobile app...")
            elif code == 86090:
                print("[WAIT] Scanned. Please confirm login in the app...")
            elif code == 86038:
                raise BilibiliLoginError("QR code expired. Please run this script again.")
            else:
                print(f"[WAIT] Bilibili status code={code}, message={message}")
            last_code = code

        time.sleep(2)


def cookie_header_from_jar(cookie_jar: CookieJar) -> str:
    cookies = list(cookie_jar)
    selected: list[tuple[str, str]] = []
    selected_names: set[str] = set()

    def is_bilibili_cookie(cookie: Any) -> bool:
        return "bilibili.com" in (cookie.domain or "")

    for name in COOKIE_PRIORITY:
        for cookie in cookies:
            if cookie.name == name and is_bilibili_cookie(cookie):
                selected.append((cookie.name, cookie.value))
                selected_names.add(cookie.name)
                break

    for cookie in cookies:
        if cookie.name not in selected_names and is_bilibili_cookie(cookie):
            selected.append((cookie.name, cookie.value))
            selected_names.add(cookie.name)

    return "; ".join(f"{name}={value}" for name, value in selected)


def verify_cookie(cookie: str) -> tuple[bool, str | None]:
    cookie_jar = CookieJar()
    opener = _create_opener(cookie_jar)
    request = urllib.request.Request(
        NAV_API,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.bilibili.com/",
            "Cookie": cookie,
        },
    )

    try:
        with opener.open(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception:
        return False, None

    data = payload.get("data") or {}
    return bool(data.get("isLogin")), data.get("uname")


def save_downloader_cookie(config_path: Path, cookie: str) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}
    else:
        data = {}

    data["bilibili"] = {"cookie": cookie}
    config_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def default_config_path() -> Path:
    backend_dir = Path(__file__).resolve().parents[1]
    return backend_dir / "config" / "downloader.json"


def write_qr_page(login_url: str, output_path: Path) -> None:
    svg = make_qr_svg(login_url)
    escaped_url = html.escape(login_url)
    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bilibili Login QR</title>
  <style>
    :root {{
      color-scheme: light dark;
      font-family: "Segoe UI", Arial, sans-serif;
      background: #f5f7fb;
      color: #17181c;
    }}
    body {{
      min-height: 100vh;
      margin: 0;
      display: grid;
      place-items: center;
      padding: 24px;
      box-sizing: border-box;
    }}
    main {{
      width: min(420px, 100%);
      background: #ffffff;
      border: 1px solid #d7dce5;
      border-radius: 8px;
      padding: 24px;
      box-shadow: 0 14px 40px rgba(21, 31, 52, 0.12);
      text-align: center;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 22px;
      line-height: 1.3;
    }}
    p {{
      margin: 8px 0;
      color: #555f70;
      line-height: 1.6;
    }}
    .qr {{
      display: inline-grid;
      place-items: center;
      margin: 18px 0 12px;
      padding: 14px;
      background: #fff;
      border: 1px solid #dfe4ed;
      border-radius: 8px;
    }}
    svg {{
      width: min(300px, 72vw);
      height: auto;
      display: block;
    }}
    textarea {{
      width: 100%;
      min-height: 72px;
      box-sizing: border-box;
      resize: vertical;
      margin-top: 12px;
      font-family: Consolas, monospace;
      font-size: 12px;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        background: #111318;
        color: #f3f5f9;
      }}
      main {{
        background: #1b1f27;
        border-color: #313947;
        box-shadow: none;
      }}
      p {{
        color: #b8c0cf;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>Bilibili QR Login</h1>
    <p>Scan this QR code with the Bilibili mobile app, then confirm login.</p>
    <div class="qr">{svg}</div>
    <p>The terminal will continue automatically after confirmation.</p>
    <textarea readonly>{escaped_url}</textarea>
  </main>
</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(page, encoding="utf-8")


ALIGNMENT_POSITIONS = {
    1: [],
    2: [6, 18],
    3: [6, 22],
    4: [6, 26],
    5: [6, 30],
    6: [6, 34],
    7: [6, 22, 38],
    8: [6, 24, 42],
    9: [6, 26, 46],
    10: [6, 28, 50],
}

# Level L block data for versions 1 through 10. This comfortably covers
# Bilibili's current QR login URL without requiring any third-party package.
LEVEL_L_BLOCKS = {
    1: (7, [19]),
    2: (10, [34]),
    3: (15, [55]),
    4: (20, [80]),
    5: (26, [108]),
    6: (18, [68, 68]),
    7: (20, [78, 78]),
    8: (24, [97, 97]),
    9: (30, [116, 116]),
    10: (18, [68, 68, 69, 69]),
}


def make_qr_svg(text: str, border: int = 4) -> str:
    data = text.encode("utf-8")
    version = _choose_version(len(data))
    ecc_len, block_lengths = LEVEL_L_BLOCKS[version]
    data_codewords = sum(block_lengths)
    codewords = _make_data_codewords(data, version, data_codewords)
    all_codewords = _add_error_correction(codewords, ecc_len, block_lengths)
    modules = _make_qr_matrix(version, all_codewords, mask=0)

    size = len(modules)
    dimension = size + border * 2
    path_parts: list[str] = []
    for y, row in enumerate(modules):
        for x, dark in enumerate(row):
            if dark:
                path_parts.append(f"M{x + border},{y + border}h1v1h-1z")

    path = "".join(path_parts)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {dimension} {dimension}" '
        f'shape-rendering="crispEdges" role="img" aria-label="Bilibili login QR">'
        f'<rect width="100%" height="100%" fill="#fff"/>'
        f'<path d="{path}" fill="#111"/>'
        f"</svg>"
    )


def _choose_version(byte_count: int) -> int:
    for version in sorted(LEVEL_L_BLOCKS):
        _, block_lengths = LEVEL_L_BLOCKS[version]
        count_bits = 8 if version <= 9 else 16
        capacity_bits = sum(block_lengths) * 8
        required_bits = 4 + count_bits + byte_count * 8
        if required_bits <= capacity_bits:
            return version
    raise BilibiliLoginError(
        "QR login URL is too long for the bundled QR encoder. "
        "Please install a QR package or update this script."
    )


def _append_bits(bits: list[int], value: int, length: int) -> None:
    for i in range(length - 1, -1, -1):
        bits.append((value >> i) & 1)


def _make_data_codewords(data: bytes, version: int, data_codewords: int) -> list[int]:
    bits: list[int] = []
    _append_bits(bits, 0x4, 4)
    _append_bits(bits, len(data), 8 if version <= 9 else 16)
    for byte in data:
        _append_bits(bits, byte, 8)

    capacity_bits = data_codewords * 8
    _append_bits(bits, 0, min(4, capacity_bits - len(bits)))
    while len(bits) % 8 != 0:
        bits.append(0)

    codewords = [
        sum(bits[i + bit] << (7 - bit) for bit in range(8))
        for i in range(0, len(bits), 8)
    ]
    pad = 0xEC
    while len(codewords) < data_codewords:
        codewords.append(pad)
        pad ^= 0xEC ^ 0x11
    return codewords


def _add_error_correction(
    data_codewords: list[int],
    ecc_len: int,
    block_lengths: list[int],
) -> list[int]:
    divisor = _reed_solomon_divisor(ecc_len)
    blocks: list[list[int]] = []
    offset = 0
    for length in block_lengths:
        block = data_codewords[offset : offset + length]
        offset += length
        blocks.append(block + _reed_solomon_remainder(block, divisor))

    result: list[int] = []
    max_data_len = max(block_lengths)
    for index in range(max_data_len):
        for block, data_len in zip(blocks, block_lengths):
            if index < data_len:
                result.append(block[index])

    for index in range(ecc_len):
        for block, data_len in zip(blocks, block_lengths):
            result.append(block[data_len + index])

    return result


GF_EXP = [0] * 512
GF_LOG = [0] * 256
_x = 1
for _i in range(255):
    GF_EXP[_i] = _x
    GF_LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    GF_EXP[_i] = GF_EXP[_i - 255]


def _gf_multiply(x: int, y: int) -> int:
    if x == 0 or y == 0:
        return 0
    return GF_EXP[GF_LOG[x] + GF_LOG[y]]


def _reed_solomon_divisor(degree: int) -> list[int]:
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for i in range(degree):
            result[i] = _gf_multiply(result[i], root)
            if i + 1 < degree:
                result[i] ^= result[i + 1]
        root = _gf_multiply(root, 0x02)
    return result


def _reed_solomon_remainder(data: list[int], divisor: list[int]) -> list[int]:
    result = [0] * len(divisor)
    for byte in data:
        factor = byte ^ result.pop(0)
        result.append(0)
        for i, coefficient in enumerate(divisor):
            result[i] ^= _gf_multiply(coefficient, factor)
    return result


def _make_qr_matrix(version: int, codewords: list[int], mask: int) -> list[list[bool]]:
    size = version * 4 + 17
    modules = [[False] * size for _ in range(size)]
    reserved = [[False] * size for _ in range(size)]

    def set_module(x: int, y: int, dark: bool, reserve: bool = True) -> None:
        if 0 <= x < size and 0 <= y < size:
            modules[y][x] = dark
            if reserve:
                reserved[y][x] = True

    def reserve_module(x: int, y: int) -> None:
        if 0 <= x < size and 0 <= y < size:
            reserved[y][x] = True

    def draw_finder(left: int, top: int) -> None:
        for dy in range(-1, 8):
            for dx in range(-1, 8):
                x = left + dx
                y = top + dy
                dark = (
                    0 <= dx <= 6
                    and 0 <= dy <= 6
                    and (
                        dx in (0, 6)
                        or dy in (0, 6)
                        or (2 <= dx <= 4 and 2 <= dy <= 4)
                    )
                )
                set_module(x, y, dark)

    def draw_alignment(cx: int, cy: int) -> None:
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                distance = max(abs(dx), abs(dy))
                set_module(cx + dx, cy + dy, distance in (0, 2))

    draw_finder(0, 0)
    draw_finder(size - 7, 0)
    draw_finder(0, size - 7)

    for i in range(8, size - 8):
        set_module(i, 6, i % 2 == 0)
        set_module(6, i, i % 2 == 0)

    for cy in ALIGNMENT_POSITIONS[version]:
        for cx in ALIGNMENT_POSITIONS[version]:
            if (
                (cx == 6 and cy == 6)
                or (cx == size - 7 and cy == 6)
                or (cx == 6 and cy == size - 7)
            ):
                continue
            draw_alignment(cx, cy)

    _reserve_format_bits(size, reserve_module)
    if version >= 7:
        _reserve_version_bits(size, reserve_module)

    data_bits = [
        (codeword >> bit) & 1
        for codeword in codewords
        for bit in range(7, -1, -1)
    ]

    bit_index = 0
    upward = True
    x = size - 1
    while x > 0:
        if x == 6:
            x -= 1
        y_range = range(size - 1, -1, -1) if upward else range(size)
        for y in y_range:
            for column in (x, x - 1):
                if not reserved[y][column]:
                    bit = data_bits[bit_index] if bit_index < len(data_bits) else 0
                    if _mask_bit(mask, column, y):
                        bit ^= 1
                    set_module(column, y, bool(bit), reserve=False)
                    bit_index += 1
        upward = not upward
        x -= 2

    _draw_format_bits(version, mask, set_module)
    if version >= 7:
        _draw_version_bits(version, set_module)
    return modules


def _mask_bit(mask: int, x: int, y: int) -> bool:
    if mask == 0:
        return (x + y) % 2 == 0
    raise ValueError(f"Unsupported mask: {mask}")


def _reserve_format_bits(size: int, reserve_module: Any) -> None:
    for i in range(6):
        reserve_module(8, i)
        reserve_module(i, 8)
    reserve_module(8, 7)
    reserve_module(8, 8)
    reserve_module(7, 8)
    for i in range(9, 15):
        reserve_module(8, size - 15 + i)
        reserve_module(14 - i, 8)
    for i in range(8):
        reserve_module(size - 1 - i, 8)
        reserve_module(8, size - 1 - i)
    reserve_module(8, size - 8)


def _draw_format_bits(version: int, mask: int, set_module: Any) -> None:
    size = version * 4 + 17
    bits = _format_bits(mask)

    for i in range(6):
        set_module(8, i, _get_bit(bits, i))
        set_module(i, 8, _get_bit(bits, i))
    set_module(8, 7, _get_bit(bits, 6))
    set_module(8, 8, _get_bit(bits, 7))
    set_module(7, 8, _get_bit(bits, 8))
    for i in range(9, 15):
        set_module(14 - i, 8, _get_bit(bits, i))

    for i in range(8):
        set_module(size - 1 - i, 8, _get_bit(bits, i))
    for i in range(8, 15):
        set_module(8, size - 15 + i, _get_bit(bits, i))

    set_module(8, size - 8, True)


def _format_bits(mask: int) -> int:
    data = (1 << 3) | mask  # Error correction level L is encoded as 01.
    rem = data
    for _ in range(10):
        rem = (rem << 1) ^ ((rem >> 9) * 0x537)
    return ((data << 10) | rem) ^ 0x5412


def _reserve_version_bits(size: int, reserve_module: Any) -> None:
    for i in range(18):
        a = size - 11 + i % 3
        b = i // 3
        reserve_module(a, b)
        reserve_module(b, a)


def _draw_version_bits(version: int, set_module: Any) -> None:
    size = version * 4 + 17
    bits = _version_bits(version)
    for i in range(18):
        bit = _get_bit(bits, i)
        a = size - 11 + i % 3
        b = i // 3
        set_module(a, b, bit)
        set_module(b, a, bit)


def _version_bits(version: int) -> int:
    rem = version
    for _ in range(12):
        rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
    return (version << 12) | rem


def _get_bit(value: int, index: int) -> bool:
    return ((value >> index) & 1) != 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Login to Bilibili with a QR code and write the cookie to "
            "backend/config/downloader.json."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=default_config_path(),
        help="Path to downloader.json. Defaults to backend/config/downloader.json.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Seconds to wait for QR scan confirmation.",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open the QR page in the default browser.",
    )
    parser.add_argument(
        "--keep-qr-page",
        action="store_true",
        help="Keep the temporary QR HTML page after the script exits.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()
    qr_page = config_path.parent / "bilibili_login_qr.html"

    cookie_jar = CookieJar()
    opener = _create_opener(cookie_jar)

    print("[INFO] Requesting Bilibili QR login ticket...")
    try:
        login_url, qrcode_key = generate_login_qr(opener)
        write_qr_page(login_url, qr_page)
        print(f"[INFO] QR page written to: {qr_page}")
        if not args.no_open:
            webbrowser.open(qr_page.resolve().as_uri())
            print("[INFO] Opened the QR page in your default browser.")
        else:
            print("[INFO] Open this file and scan the QR code:")
            print(f"       {qr_page}")

        poll_login(opener, qrcode_key, args.timeout)
        cookie = cookie_header_from_jar(cookie_jar)
        if "SESSDATA=" not in cookie:
            raise BilibiliLoginError(
                "Login succeeded, but SESSDATA was not found in returned cookies."
            )

        is_login, uname = verify_cookie(cookie)
        if not is_login:
            raise BilibiliLoginError("Cookie verification failed.")

        save_downloader_cookie(config_path, cookie)
        display_name = f" ({uname})" if uname else ""
        print(f"[OK] Bilibili cookie verified{display_name}.")
        print(f"[OK] Wrote downloader config: {config_path}")
        print("[INFO] Restart the backend if it is already running.")
        return 0
    except BilibiliLoginError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    finally:
        if not args.keep_qr_page:
            try:
                qr_page.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
