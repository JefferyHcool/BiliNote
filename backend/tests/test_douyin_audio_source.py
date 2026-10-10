import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.downloaders.douyin_downloader import DouyinDownloader
from app.services.douyin_audio_cache import retire_legacy_douyin_cache


class DouyinAudioSourceTests(unittest.TestCase):
    def test_audio_comes_from_video_not_music(self):
        downloader = DouyinDownloader()
        detail = {
            'aweme_id': '123', 'item_title': 'demo', 'caption': '', 'video_tag': [],
            'music': {'play_url': {'uri': 'https://example.com/wrong-music'}},
            'video': {'duration': 85000, 'cover': True,
                      'cover_original_scale': {'url_list': ['cover']}},
        }
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(downloader, 'fetch_video_info', return_value={'aweme_detail': detail}), \
             patch.object(downloader, 'download_video', return_value='/video.mp4'), \
             patch('app.downloaders.douyin_downloader.LocalDownloader.convert_to_mp3') as convert, \
             patch('app.downloaders.douyin_downloader.requests.get') as request:
            result = downloader.download('https://www.douyin.com/video/123', output_dir=folder)
            convert.assert_called_once_with('/video.mp4', str(Path(folder) / '123_video_audio.mp3'))
            request.assert_not_called()
            self.assertEqual(result.raw_info['audio_source'], 'video_track_v1')
            self.assertEqual(result.video_path, '/video.mp4')

    def test_old_cache_backed_up_and_new_cache_reused(self):
        with tempfile.TemporaryDirectory() as folder:
            audio, transcript = Path(folder) / 'audio.json', Path(folder) / 'transcript.json'
            audio.write_text(json.dumps({'raw_info': {}}))
            transcript.write_text('old transcript')
            self.assertTrue(retire_legacy_douyin_cache(audio, transcript))
            self.assertFalse(audio.exists())
            self.assertFalse(transcript.exists())
            backups = list(Path(folder).glob('*.bak'))
            self.assertEqual(len(backups), 2)
            self.assertIn('old transcript', [p.read_text() for p in backups])
            audio.write_text(json.dumps({'raw_info': {'audio_source': 'video_track_v1'}}))
            transcript.write_text('new transcript')
            self.assertFalse(retire_legacy_douyin_cache(audio, transcript))
            self.assertEqual(transcript.read_text(), 'new transcript')

    def test_orphan_transcript_not_reused(self):
        with tempfile.TemporaryDirectory() as folder:
            audio, transcript = Path(folder) / 'audio.json', Path(folder) / 'transcript.json'
            transcript.write_text('old transcript')
            self.assertTrue(retire_legacy_douyin_cache(audio, transcript))
            self.assertFalse(transcript.exists())
