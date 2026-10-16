import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import emby_organizer as m


class OrganizerRegressions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.patch = patch.object(m, 'INBOX_DIR', self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.org = m.MediaOrganizer.__new__(m.MediaOrganizer)
        self.org.dry_run = False
        self.org.uploader = Mock()
        self.org.uploader.list_remote_dirs.return_value = []
        self.org.classify_with_tmdb = Mock(return_value=None)
        self.uploader = m.SftpUploader.__new__(m.SftpUploader)
        self.uploader.targets = {k: m.SftpTarget('u', 'h', 22, '/' + k) for k in ('series', 'anime', 'movies')}

    def test_release_destinations(self):
        cases = [
            ('Ted.Lasso.S01E01.2160p.WEB-DL.mkv', '/series/Ted Lasso/Season 1/S01E01.mkv'),
            ('Ted Lasso 4K/Ted.Lasso.S01E01.mkv', '/series/Ted Lasso/Season 1/S01E01.mkv'),
            ('Ted Lasso/Season 2/Ted.Lasso.S02E03.mkv', '/series/Ted Lasso/Season 2/S02E03.mkv'),
            ('Ted Lasso/Season 2/S02E03.mkv', '/series/Ted Lasso/Season 2/S02E03.mkv'),
            ('Ted.Lasso.S00E01.mkv', '/series/Ted Lasso/Season 0/S00E01.mkv'),
            ('Ted.Lasso.S01E01E02.mkv', '/series/Ted Lasso/Season 1/S01E01E02.mkv'),
            ('Ted.Lasso.S01E01-S01E03.mkv', '/series/Ted Lasso/Season 1/S01E01E02E03.mkv'),
            ('Ted.Lasso.S01E01-E02.mkv', '/series/Ted Lasso/Season 1/S01E01E02.mkv'),
            ('Ted.Lasso.S01E01-02.mkv', '/series/Ted Lasso/Season 1/S01E01E02.mkv'),
            ('Ted Lasso S01E01E02/video.mkv', '/series/Ted Lasso/Season 1/S01E01E02.mkv'),
            ('Ted.Lasso.Cap.103.mkv', '/series/Ted Lasso/Season 1/S01E03.mkv'),
            ('Ted.Lasso.Capitulo.103.mkv', '/series/Ted Lasso/Season 1/S01E03.mkv'),
            ('Dune.2021.2160p.mkv', '/movies/Dune (2021).mkv'),
            ('1917.2019.1080p.mkv', '/movies/1917 (2019).mkv'),
            ('[SubsPlease] One Piece - 1120 (1080p) [A1B2C3D4].mkv', '/anime/One Piece/Season 1/S01E1120.mkv'),
        ]
        for relative, expected in cases:
            with self.subTest(relative=relative):
                media = self.org.classify(self.root / relative)
                self.assertEqual(self.uploader.build_remote_path(media), expected)

    def test_cross_season_is_not_partially_uploaded(self):
        self.assertEqual(self.org.classify(self.root / 'Show.S01E10-S02E01.mkv').category, 'unknown')

    def test_quality_cleaning_preserves_title_numbers(self):
        self.assertEqual(self.org.clean_title('The.100.4K.UHD.HDR.H.265'), 'The 100')
        self.assertNotEqual(self.org.normalize_name('The Office'), self.org.normalize_name('Office'))

    def test_remote_failure_does_not_invent_library(self):
        self.org.uploader.list_remote_dirs.side_effect = OSError('offline')
        with self.assertRaises(m.OrganizerError):
            self.org.classify(self.root / 'Ted.Lasso.S01E01.mkv')

    def test_existing_exact_title_is_reused(self):
        self.org.uploader.list_remote_dirs.side_effect = lambda category: ['Ted Lasso'] if category == 'series' else []
        self.assertEqual(self.org.classify(self.root / 'Ted.Lasso.S01E01.mkv').title, 'Ted Lasso')

    def test_quarantine_descendants_and_symlinks_ignored(self):
        for name in ('NoClasificado/sub/video.mkv', '.staging/sub/video.mkv'):
            file = self.root / name
            file.parent.mkdir(parents=True)
            file.write_bytes(b'a')
            self.assertTrue(self.org.should_ignore(file))
        target = self.root / 'target.mkv'
        target.write_bytes(b'a')
        link = self.root / 'link.mkv'
        link.symlink_to(target)
        self.assertTrue(self.org.should_ignore(link))
        self.assertFalse(self.org.should_ignore(target))
        self.org.cleanup_empty_folders()
        self.assertTrue((self.root / 'NoClasificado/sub').exists())

    def test_old_mtime_copy_requires_full_observation(self):
        file = self.root / 'video.mkv'
        file.write_bytes(b'a')
        os.utime(file, (1, 1))
        with patch.object(m.time, 'monotonic', side_effect=[0, 179, 180, 181, 361]):
            self.assertFalse(self.org.is_stable(file))
            self.assertFalse(self.org.is_stable(file))
            self.assertTrue(self.org.is_stable(file))
            file.write_bytes(b'changed')
            self.assertFalse(self.org.is_stable(file))
            self.assertTrue(self.org.is_stable(file))

    def test_upload_change_preserves_local_and_does_not_publish(self):
        file = self.root / 'video.mkv'
        file.write_bytes(b'a')
        sftp = Mock()
        sftp.put.side_effect = lambda *_: file.write_bytes(b'changed')
        self.uploader.ensure_remote_dir = Mock()
        self.uploader._with_reconnect = lambda category, op: op(sftp)
        with self.assertRaises(m.OrganizerError):
            self.uploader.upload_file(file, 'movies', '/movies/video.mkv')
        sftp.rename.assert_not_called()
        sftp.remove.assert_called_once()
        self.assertTrue(file.exists())

    def test_scan_continues_after_one_file_error(self):
        for name in ('a.mkv', 'b.mkv'):
            (self.root / name).write_bytes(b'a')
        self.org.process_file = Mock(side_effect=[OSError('bad file'), None])
        with self.assertLogs(level='ERROR'):
            self.org.scan_once()
        self.assertEqual(self.org.process_file.call_count, 2)

    def test_existing_destination_preserves_source(self):
        file = self.root / 'Ted.Lasso.S01E01.mkv'
        file.write_bytes(b'a')
        self.org.is_stable = Mock(return_value=True)
        self.org.uploader.exists.return_value = True
        self.org.quarantine = Mock()
        self.org.process_file(file)
        self.org.uploader.upload_file.assert_not_called()
        self.org.quarantine.assert_called_once()
        self.assertTrue(file.exists())

    def test_tmdb_rejects_unrelated_and_ambiguous_results(self):
        for results in ([{'media_type': 'movie', 'title': 'Other'}],
                        [{'media_type': 'movie', 'title': 'Dune'}, {'media_type': 'movie', 'title': 'Dune'}]):
            response = Mock()
            response.json.return_value = {'results': results}
            with patch.object(m, 'TMDB_API_KEY', 'test'), patch.object(self.org, 'load_tmdb_cache', return_value={}), patch.object(self.org, 'save_tmdb_cache'), patch.object(m.requests, 'get', return_value=response):
                self.assertIsNone(self.org.tmdb_search_multi('Dune'))

    def test_tmdb_rejects_wrong_year(self):
        del self.org.classify_with_tmdb
        with patch.object(self.org, 'tmdb_search_multi', return_value={'media_type': 'movie', 'title': 'Dune', 'release_date': '1984-01-01'}):
            self.assertIsNone(self.org.classify_with_tmdb(self.root / 'Dune.2021.mkv'))

    def test_episode_without_series_identity_is_unknown(self):
        self.assertEqual(self.org.classify(self.root / 'S01E01.mkv').category, 'unknown')

    def test_duplicate_or_reversed_episode_is_unknown(self):
        for name in ('Show.S01E01E01.mkv', 'Show.S01E03E02.mkv', 'Show.S01E03-01.mkv'):
            self.assertEqual(self.org.classify(self.root / name).category, 'unknown')

    def test_success_deletes_only_uploaded_source(self):
        file = self.root / 'Ted.Lasso.S01E01.mkv'
        file.write_bytes(b'a')
        self.org.is_stable = Mock(return_value=True)
        self.org.uploader.exists.return_value = False
        self.org.notify_telegram = Mock()
        with patch.object(m, 'add_history'):
            self.org.process_file(file)
        self.assertFalse(file.exists())
        self.org.uploader.upload_file.assert_called_once()
        self.org.notify_telegram.assert_called_once()

    def test_upload_error_and_source_change_preserve_source(self):
        for mutation in (False, True):
            file = self.root / 'Ted.Lasso.S01E01.mkv'
            file.write_bytes(b'a')
            self.org.is_stable = Mock(return_value=True)
            self.org.uploader.exists.return_value = False
            def upload(*args):
                if mutation:
                    file.write_bytes(b'new')
                else:
                    raise OSError('connection lost')
            self.org.uploader.upload_file.side_effect = upload
            with self.assertRaises((OSError, m.OrganizerError)):
                self.org.process_file(file)
            self.assertTrue(file.exists())

    def test_dry_run_does_not_upload_or_remove(self):
        self.org.dry_run = True
        self.org.is_stable = Mock(return_value=True)
        file = self.root / 'Ted.Lasso.S01E01.mkv'
        file.write_bytes(b'a')
        with patch.object(m, 'add_history'):
            self.org.process_file(file)
        self.assertTrue(file.exists())
        self.org.uploader.upload_file.assert_not_called()

    def test_tmdb_old_cache_is_not_used_forever(self):
        response = Mock()
        response.json.return_value = {'results': [{'media_type': 'movie', 'title': 'Dune'}]}
        with patch.object(m, 'TMDB_API_KEY', 'test'), patch.object(self.org, 'load_tmdb_cache', return_value={'dune': {'title': 'Wrong'}}), patch.object(self.org, 'save_tmdb_cache'), patch.object(m.requests, 'get', return_value=response) as get:
            self.assertEqual(self.org.tmdb_search_multi('Dune')['title'], 'Dune')
            get.assert_called_once()

    def test_title_that_is_a_year_has_no_invented_release_year(self):
        self.assertIsNone(self.org.detect_year('1917.1080p'))
        self.assertEqual(self.org.detect_year('1917.2019.1080p'), 2019)

    def test_source_changing_during_classification_is_deferred(self):
        file = self.root / 'Ted.Lasso.S01E01.mkv'
        file.write_bytes(b'a')
        self.org.is_stable = Mock(return_value=True)
        media = self.org.classify(file)
        def classify(*args):
            file.write_bytes(b'new content')
            return media
        self.org.classify = classify
        self.org.process_file(file)
        self.assertTrue(file.exists())
        self.org.uploader.upload_file.assert_not_called()

    def test_technical_suffix_does_not_become_movie_title(self):
        media = self.org.classify(self.root / 'Dune.2021.4K.HDR.HEVC-GROUP.mkv')
        self.assertEqual(self.uploader.build_remote_path(media), '/movies/Dune (2021).mkv')

    def test_ambiguous_remote_folders_are_not_merged(self):
        self.org.uploader.list_remote_dirs.return_value = ['Ted Lasso', 'Ted-Lasso']
        with self.assertRaises(m.OrganizerError):
            self.org.classify(self.root / 'Ted.Lasso.S01E01.mkv')

    def test_main_rejects_concurrent_instance(self):
        lock = (self.root / 'organizer.lock').open('a')
        self.addCleanup(lock.close)
        m.fcntl.flock(lock, m.fcntl.LOCK_EX | m.fcntl.LOCK_NB)
        with patch.object(m, 'STATE_DIR', self.root), patch.object(m, 'setup_logging'), patch.object(m, 'parse_args', return_value=Mock(scan_once=True, daemon=False, dry_run=False, verbose=False)), patch.object(m, 'MediaOrganizer') as constructor:
            with self.assertRaises(SystemExit):
                m.main()
            constructor.assert_not_called()

    def test_one_shot_observes_quiet_period(self):
        with patch.object(m, 'STATE_DIR', self.root), patch.object(m, 'setup_logging'), patch.object(m, 'parse_args', return_value=Mock(scan_once=True, daemon=False, dry_run=True, verbose=False)), patch.object(m, 'MediaOrganizer') as constructor, patch.object(m.time, 'sleep') as sleep:
            m.main()
            self.assertEqual(constructor.return_value.scan_once.call_count, 2)
            sleep.assert_called_once_with(m.STABLE_SECONDS)
            constructor.return_value.shutdown.assert_called_once()

    def test_generic_container_is_not_a_series_identity(self):
        for name in ('Series/S01E01.mkv', 'Torrent/Season 1/S01E01.mkv'):
            self.assertEqual(self.org.classify(self.root / name).category, 'unknown')
        media = self.org.classify(self.root / 'Series/Ted Lasso/Temporada 2/S02E01.mkv')
        self.assertEqual(media.title, 'Ted Lasso')

    def test_inbox_name_cannot_supply_episode_metadata(self):
        with patch.object(m, 'INBOX_DIR', self.root / 'Inbox4x07'):
            movie = self.org.classify(m.INBOX_DIR / 'Dune.2021.2160p.mkv')
            self.assertEqual(movie.category, 'movies')
            self.assertIsNone(movie.episode)
