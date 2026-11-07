"""Browser-compatible, derived video previews; original recordings are immutable."""
from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path
from urllib.parse import quote

_lock = threading.Lock()
_jobs: dict[str, dict] = {}
PREVIEW_NAME = 'preview-h264.mp4'


def _probe(path: Path) -> dict:
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
         '-show_entries', 'stream=codec_name,pix_fmt,width:format=format_name',
         '-of', 'json', str(path)], capture_output=True, text=True,
        timeout=20, check=True)
    return json.loads(result.stdout)


def _browser_compatible(path: Path) -> bool:
    info = _probe(path)
    stream = next(iter(info.get('streams') or []), {})
    return (path.suffix.lower() == '.mp4' and stream.get('codec_name') == 'h264'
            and stream.get('pix_fmt') == 'yuv420p')


def _convert(key: str, source: Path, preview: Path) -> None:
    temporary = preview.with_name('preview-h264.tmp.mp4')
    try:
        temporary.unlink(missing_ok=True)
        info = _probe(source)
        width = int((info.get('streams') or [{}])[0].get('width') or 1280)
        preview_width = max(2, min(1280, width) // 2 * 2)
        subprocess.run(
            ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
             '-threads', '2', '-i', str(source), '-map', '0:v:0', '-map', '0:a:0?',
             '-vf', f'fps=12,scale={preview_width}:-2:flags=fast_bilinear',
             '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '26',
             '-pix_fmt', 'yuv420p', '-threads', '2',
             '-c:a', 'aac', '-b:a', '96k', '-movflags', '+faststart', str(temporary)],
            capture_output=True, text=True, timeout=1800, check=True)
        if not temporary.is_file() or temporary.stat().st_size == 0:
            raise ValueError('No browser preview was produced')
        os.replace(temporary, preview)
        with _lock:
            _jobs[key] = {'status': 'ready'}
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        temporary.unlink(missing_ok=True)
        with _lock:
            _jobs[key] = {'status': 'failed', 'error': str(error)[-300:]}


def request(media_id: str, source: Path) -> dict:
    """Return a playable URL or start a bounded local preview job once."""
    if not isinstance(media_id, str) or not source.is_file():
        raise ValueError('Recording not found')
    key = str(source.resolve())
    preview = source.with_name(PREVIEW_NAME)
    if preview.is_file() and preview.stat().st_size and preview.stat().st_mtime_ns >= source.stat().st_mtime_ns:
        return {'status': 'ready', 'url': f'/media/{quote(media_id)}/{PREVIEW_NAME}',
                'derived': True}
    with _lock:
        job = _jobs.get(key)
        if job and job['status'] == 'failed':
            return dict(job)
        if job and job['status'] == 'running':
            return {'status': 'processing'}
    try:
        compatible = _browser_compatible(source)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return {'status': 'failed', 'error': f'Cannot inspect recording: {error}'}
    if compatible:
        return {'status': 'ready', 'url': f'/media/{quote(media_id)}/{quote(source.name)}',
                'derived': False}
    with _lock:
        if key not in _jobs or _jobs[key]['status'] != 'running':
            _jobs[key] = {'status': 'running'}
            threading.Thread(target=_convert, args=(key, source, preview), daemon=True).start()
    return {'status': 'processing'}
