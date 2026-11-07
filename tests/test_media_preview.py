import hashlib
import subprocess
import tempfile
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import media_preview
import server


class MediaPlaybackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def video(self, codec):
        path = self.root / ('clip-' + codec + '.mp4')
        command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                   '-f', 'lavfi', '-i', 'color=c=blue:s=96x54:r=12:d=1',
                   '-frames:v', '12', '-threads', '1', '-c:v', codec,
                   '-pix_fmt', 'yuv420p']
        if codec == 'libx265':
            command += ['-x265-params', 'pools=1:log-level=error']
        command += ['-movflags', '+faststart', str(path)]
        subprocess.run(command, capture_output=True, text=True, check=True, timeout=30)
        return path

    def test_hevc_gets_full_derived_h264_preview_without_changing_original(self):
        original = self.video('libx265')
        digest = hashlib.sha256(original.read_bytes()).hexdigest()
        first = media_preview.request('fixture', original)
        self.assertEqual(first['status'], 'processing')
        for _ in range(100):
            result = media_preview.request('fixture', original)
            if result['status'] != 'processing':
                break
            time.sleep(.1)
        self.assertEqual(result['status'], 'ready', result)
        self.assertTrue(result['derived'])
        preview = original.with_name(media_preview.PREVIEW_NAME)
        self.assertEqual(media_preview._probe(preview)['streams'][0]['codec_name'], 'h264')
        self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(), digest)

    def test_browser_compatible_h264_uses_original(self):
        original = self.video('libx264')
        result = media_preview.request('fixture', original)
        self.assertEqual(result['status'], 'ready')
        self.assertFalse(result['derived'])
        self.assertFalse(original.with_name(media_preview.PREVIEW_NAME).exists())

    def test_media_http_supports_ranges_and_head(self):
        previous = server.DATA
        server.DATA = self.root
        folder = self.root / 'media' / 'fixture'
        folder.mkdir(parents=True)
        (folder / 'sample.mp4').write_bytes(b'0123456789')
        http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        from threading import Thread
        thread = Thread(target=http.serve_forever, daemon=True)
        thread.start()
        url = f'http://127.0.0.1:{http.server_port}/media/fixture/sample.mp4'
        try:
            with urlopen(Request(url, headers={'Range': 'bytes=2-5'}), timeout=5) as response:
                self.assertEqual(response.status, 206)
                self.assertEqual(response.headers['Content-Range'], 'bytes 2-5/10')
                self.assertEqual(response.headers['Accept-Ranges'], 'bytes')
                self.assertEqual(response.read(), b'2345')
            with urlopen(Request(url, headers={'Range': 'bytes=-3'}), timeout=5) as response:
                self.assertEqual(response.read(), b'789')
            with urlopen(Request(url, method='HEAD'), timeout=5) as response:
                self.assertEqual(response.headers['Content-Length'], '10')
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(url, headers={'Range': 'bytes=11-12'}), timeout=5)
            self.assertEqual(error.exception.code, 416)
            error.exception.close()
        finally:
            http.shutdown()
            http.server_close()
            thread.join()
            server.DATA = previous


if __name__ == '__main__':
    unittest.main()
