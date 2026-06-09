"""
下载 m3u8 视频，处理 AES-128 加密，合并 ts 分片为 mp4。
"""

import re
import time
import requests
from pathlib import Path
from Crypto.Cipher import AES

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Referer": "https://h5.xiaoeknow.com/",
}
RETRY = 3


def download_video(play_url: str, output_path: Path, cookies: list = None,
                   on_progress=None) -> Path:
    """
    下载并解密 m3u8 视频，输出合并后的 mp4 文件。
    on_progress(pct): 可选回调，每个分片完成后调用，pct 0-100。
    """
    session = requests.Session()
    session.headers.update(HEADERS)
    if cookies:
        for c in cookies:
            session.cookies.set(c["name"], c["value"], domain=c.get("domain", ""))

    tmp_dir = output_path.parent / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    mp4_path = output_path.parent / (output_path.name + ".mp4")

    m3u8_text = _fetch(session, play_url)

    if m3u8_text.startswith("[xiaoe]"):
        m3u8_text = _decode_xiaoe(m3u8_text)

    if "#EXTM3U" not in m3u8_text:
        raise ValueError("获取到的内容不是合法的 m3u8 文件")

    if "#EXT-X-STREAM-INF" in m3u8_text:
        play_url = _extract_best_stream(m3u8_text, play_url)
        m3u8_text = _fetch(session, play_url)

    aes_key, aes_iv = _extract_key_iv(session, m3u8_text, play_url)
    ts_urls = _extract_ts_urls(m3u8_text, play_url)

    ts_files = _download_segments(session, ts_urls, tmp_dir, aes_key, aes_iv, on_progress)
    _merge(ts_files, mp4_path)

    for f in ts_files:
        try:
            f.unlink()
        except Exception:
            pass

    return mp4_path


def _fetch(session: requests.Session, url: str) -> str:
    for i in range(RETRY):
        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()
            return r.text
        except Exception:
            if i == RETRY - 1:
                raise
            time.sleep(2)


def _fetch_bytes(session: requests.Session, url: str) -> bytes:
    for i in range(RETRY):
        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()
            return r.content
        except Exception:
            if i == RETRY - 1:
                raise
            time.sleep(2)


def _decode_xiaoe(text: str) -> str:
    import base64
    raw = text[len("[xiaoe]"):]
    padding = 4 - len(raw) % 4
    if padding != 4:
        raw += "=" * padding
    try:
        return base64.b64decode(raw).decode("utf-8")
    except Exception:
        return base64.b64decode(raw.encode(), altchars=b"-_").decode("utf-8")


def _extract_best_stream(m3u8_text: str, base_url: str) -> str:
    lines = m3u8_text.splitlines()
    best_bw, best_url = -1, ""
    for i, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF"):
            bw = int(re.search(r"BANDWIDTH=(\d+)", line).group(1))
            url = lines[i + 1].strip()
            if bw > best_bw:
                best_bw, best_url = bw, url
    return _abs_url(best_url, base_url)


def _extract_key_iv(session: requests.Session, m3u8_text: str, base_url: str):
    match = re.search(r'#EXT-X-KEY:(.*)', m3u8_text)
    if not match:
        return None, None
    info = match.group(1)
    key_uri = re.search(r'URI="([^"]+)"', info)
    if not key_uri:
        return None, None
    aes_key = _fetch_bytes(session, _abs_url(key_uri.group(1), base_url))
    iv_match = re.search(r'IV=0x([0-9a-fA-F]+)', info)
    aes_iv = bytes.fromhex(iv_match.group(1).zfill(32)) if iv_match else b'\x00' * 16
    return aes_key, aes_iv


def _extract_ts_urls(m3u8_text: str, base_url: str) -> list[str]:
    return [
        _abs_url(line.strip(), base_url)
        for line in m3u8_text.splitlines()
        if line.strip() and not line.startswith("#")
    ]


def _abs_url(url: str, base_url: str) -> str:
    if url.startswith("http"):
        return url
    return "/".join(base_url.split("/")[:-1]) + "/" + url


def _download_segments(session, ts_urls, tmp_dir, aes_key, aes_iv, on_progress=None) -> list[Path]:
    files = []
    total = len(ts_urls)
    for i, url in enumerate(ts_urls):
        out = tmp_dir / f"seg_{i:05d}.ts"
        data = _fetch_bytes(session, url)
        if aes_key:
            data = AES.new(aes_key, AES.MODE_CBC, aes_iv).decrypt(data)
        out.write_bytes(data)
        files.append(out)
        if on_progress:
            on_progress((i + 1) / total * 100)
    return files


def _merge(ts_files: list[Path], output: Path):
    with open(output, "wb") as f:
        for ts in ts_files:
            f.write(ts.read_bytes())
