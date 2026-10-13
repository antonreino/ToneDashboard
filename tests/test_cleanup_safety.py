import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import emby_organizer
from emby_organizer import MediaOrganizer


class CleanupSafetyTests(unittest.TestCase):
    def organizer(self):
        obj = MediaOrganizer.__new__(MediaOrganizer)
        obj.dry_run = False
        return obj

    def test_non_video_file_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "juego.pkg"
            path.write_bytes(b"pkg")
            self.assertTrue(self.organizer().should_ignore(path))

    def test_cleanup_preserves_non_video_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox = Path(tmp)
            folder = inbox / "Juego"
            folder.mkdir()
            pkg = folder / "juego.pkg"
            pkg.write_bytes(b"pkg")
            with patch.object(emby_organizer, "INBOX_DIR", inbox):
                self.organizer().cleanup_download_folder(folder / "pelicula.mkv")
            self.assertTrue(folder.exists())
            self.assertTrue(pkg.exists())

    def test_cleanup_preserves_sidecars(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox = Path(tmp)
            folder = inbox / "Pelicula"
            folder.mkdir()
            subtitle = folder / "subtitulos.srt"
            poster = folder / "poster.jpg"
            subtitle.write_text("subs", encoding="utf-8")
            poster.write_bytes(b"jpg")
            with patch.object(emby_organizer, "INBOX_DIR", inbox):
                self.organizer().cleanup_download_folder(folder / "pelicula.mkv")
            self.assertTrue(subtitle.exists())
            self.assertTrue(poster.exists())

    def test_cleanup_removes_only_empty_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox = Path(tmp)
            folder = inbox / "Pelicula"
            folder.mkdir()
            with patch.object(emby_organizer, "INBOX_DIR", inbox):
                self.organizer().cleanup_download_folder(folder / "pelicula.mkv")
            self.assertFalse(folder.exists())

    def test_global_cleanup_preserves_non_video_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox = Path(tmp)
            nested = inbox / "Juego" / "Datos"
            nested.mkdir(parents=True)
            iso = nested / "juego.iso"
            iso.write_bytes(b"iso")
            with patch.object(emby_organizer, "INBOX_DIR", inbox):
                self.organizer().cleanup_empty_folders()
            self.assertTrue(iso.exists())
            self.assertTrue(nested.exists())

    def test_global_cleanup_removes_nested_empty_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            inbox = Path(tmp)
            (inbox / "A" / "B" / "C").mkdir(parents=True)
            with patch.object(emby_organizer, "INBOX_DIR", inbox):
                self.organizer().cleanup_empty_folders()
            self.assertFalse((inbox / "A").exists())
            self.assertTrue(inbox.exists())


if __name__ == "__main__":
    unittest.main()
