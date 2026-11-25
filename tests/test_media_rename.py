"""homelab-rename: names Jellyfin reads, what it leaves alone, and that `undo` puts everything back."""
import os
import shutil
import tempfile
import unittest
from unittest import mock

import helpers


class RenameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = helpers.load_script("homelab_rename", "scripts/homelab-rename")

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="rename-")
        self.addCleanup(shutil.rmtree, self.base, True)
        self.movies = os.path.join(self.base, "movies")
        self.shows = os.path.join(self.base, "shows")
        os.makedirs(self.movies)
        os.makedirs(self.shows)
        self.r.UNDO_DIR = os.path.join(self.base, "undo")

    def touch(self, root, *parts):
        path = os.path.join(root, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()
        return path

    def tree(self, root):
        out = set()
        for base, _dirs, files in os.walk(root):
            for f in files:
                out.add(os.path.relpath(os.path.join(base, f), root))
        return out

    def run_all(self, root_movies=True, root_shows=True):
        groups = []
        for root, planner, on in ((self.movies, self.r.plan_movies, root_movies), (self.shows, self.r.plan_shows, root_shows)):
            if on:
                items, skipped = planner(root)
                todo, same, held = self.r.settle(items)
                groups.append((root, todo, same, held, skipped))
        return groups

    def do(self):
        groups = self.run_all()
        return self.r.apply([(g[0], g[1]) for g in groups]), groups

    def test_movie_names(self):
        for n in ("Dune.Part.Two.2024.2160p.WEB-DL.DDP5.1.Atmos.x265-GROUP.mkv", "Charlotte's.Web.2006.1080p.BluRay.x264-YIFY.mp4",
                  "2012.2009.1080p.BluRay.x264.mkv", "1917.2019.1080p.mkv", "Blade.Runner.2049.2017.720p.mkv", "the.matrix.1999.mkv",
                  "Some.Old.Movie.DVDRip.XviD.avi"):
            self.touch(self.movies, n)
        self.do()
        self.assertEqual(self.tree(self.movies), {
            "Dune Part Two (2024)/Dune Part Two (2024).mkv", "Charlotte's Web (2006)/Charlotte's Web (2006).mp4", "2012 (2009)/2012 (2009).mkv",
            "1917 (2019)/1917 (2019).mkv", "Blade Runner 2049 (2017)/Blade Runner 2049 (2017).mkv", "The Matrix (1999)/The Matrix (1999).mkv",
            "Some Old Movie/Some Old Movie.avi"})

    def test_movie_in_a_folder_with_a_useless_file_name_uses_the_folder(self):
        self.touch(self.movies, "Heat.1995.1080p", "x1.mkv")
        self.touch(self.movies, "Heat.1995.1080p", "sample.mkv")
        self.do()
        self.assertEqual(self.tree(self.movies), {"Heat (1995)/Heat (1995).mkv", "Heat.1995.1080p/sample.mkv"})

    def test_subtitles_travel_with_the_video_and_other_files_stay(self):
        self.touch(self.movies, "Inception.2010.1080p", "inception.2010.mkv")
        self.touch(self.movies, "Inception.2010.1080p", "inception.2010.en.srt")
        self.touch(self.movies, "Inception.2010.1080p", "info.nfo")
        self.do()
        self.assertEqual(self.tree(self.movies), {"Inception (2010)/Inception (2010).mkv", "Inception (2010)/Inception (2010).en.srt", "Inception.2010.1080p/info.nfo"})

    def test_a_correct_name_is_left_as_it_is_and_a_taken_name_is_not_overwritten(self):
        self.touch(self.movies, "Already (2020)", "Already (2020).mkv")
        self.touch(self.movies, "Already.2020.720p.mkv")
        (done, _failed, _log), groups = self.do()
        self.assertEqual(done, 0)
        self.assertEqual(len(groups[0][2]), 1)
        self.assertEqual(len(groups[0][3]), 1)
        self.assertIn("Already.2020.720p.mkv", self.tree(self.movies))

    def test_two_files_for_the_same_movie_do_not_overwrite_each_other(self):
        self.touch(self.movies, "Heat.1995.1080p.mkv")
        self.touch(self.movies, "Heat.1995.720p.mkv")
        (done, _f, _l), groups = self.do()
        self.assertEqual(done, 1)
        self.assertEqual(len(groups[0][3]), 1)

    def test_parts_of_one_movie_keep_their_part_number(self):
        self.touch(self.movies, "Big.Movie.2001.cd1.avi")
        self.touch(self.movies, "Big.Movie.2001.cd2.avi")
        self.do()
        self.assertEqual(self.tree(self.movies), {"Big Movie (2001)/Big Movie (2001) - part1.avi", "Big Movie (2001)/Big Movie (2001) - part2.avi"})

    def test_show_names_seasons_and_episodes(self):
        self.touch(self.shows, "Breaking.Bad.S01.1080p.BluRay", "Season 1", "Breaking.Bad.S01E01.1080p.BluRay.x264-GRP.mkv")
        self.touch(self.shows, "The Office (US)", "Season 02", "05 - Halloween.mkv")
        self.touch(self.shows, "The Office (US)", "Season 02", "The.Office.US.2x06.Valentines.Day.mkv")
        self.touch(self.shows, "Doctor.Who.2005.S01E01-E02.720p.mkv")
        self.touch(self.shows, "Show X", "Specials", "E01.mkv")
        self.touch(self.shows, "Breaking.Bad.S02E01.mkv")
        self.do()
        self.assertEqual(self.tree(self.shows), {
            "Breaking Bad/Season 01/Breaking Bad S01E01.mkv", "Breaking Bad/Season 02/Breaking Bad S02E01.mkv",
            "The Office (US)/Season 02/The Office (US) S02E05.mkv", "The Office (US)/Season 02/The Office (US) S02E06.mkv",
            "Doctor Who (2005)/Season 01/Doctor Who S01E01-E02.mkv", "Show X/Season 00/Show X S00E01.mkv"})

    def test_season_and_episode_written_out_in_words(self):
        self.touch(self.shows, "Frieren Beyond Journey's End", "Frieren Beyond Journey's End Season 2 - E01 (Dub).mp4")
        self.touch(self.shows, "Frieren Beyond Journey's End", "Frieren Beyond Journey's End Season 2 - E10 (Dub).mp4")
        self.touch(self.shows, "Show Y", "Show Y Season 3 Episode 4.mkv")
        self.do()
        self.assertEqual(self.tree(self.shows), {
            "Frieren Beyond Journey's End/Season 02/Frieren Beyond Journey's End S02E01.mp4",
            "Frieren Beyond Journey's End/Season 02/Frieren Beyond Journey's End S02E10.mp4",
            "Show Y/Season 03/Show Y S03E04.mkv"})

    def test_a_dash_and_space_between_the_season_and_the_episode_is_read(self):
        show = "Re ZERO -Starting Life in Another World-"
        folder = "ReZero Starting Life in Another World"
        self.touch(self.shows, folder, show + " S01 E01 (Dub).mp4")
        self.touch(self.shows, folder, show + " S01- E02 (Dub).mp4")
        self.touch(self.shows, folder, show + " S01 - E03 (Dub).mp4")
        self.do()
        self.assertEqual(self.tree(self.shows), {"%s/Season 01/%s S01E0%d.mp4" % (folder, folder, n) for n in (1, 2, 3)})

    def test_a_season_in_two_parts_goes_on_counting_after_the_first_part(self):
        folder = "Show Z"
        for n in range(1, 4):
            self.touch(self.shows, folder, "Show Z Season 2 - E0%d (Dub).mp4" % n)
        for n in range(1, 3):
            self.touch(self.shows, folder, "Show Z Season 2 Part 2 - E0%d (Dub).mp4" % n)
        self.do()
        self.assertEqual(self.tree(self.shows), {"Show Z/Season 02/Show Z S02E0%d.mp4" % n for n in (1, 2, 3, 4, 5)})
        # running it again changes nothing: the files already have their final names
        (done, _f, _l), _g = self.do()
        self.assertEqual(done, 0)

    def test_the_second_part_alone_is_left_alone(self):
        self.touch(self.shows, "Show Q", "Show Q Season 2 Part 2 - E01.mp4")
        (done, _f, _l), groups = self.do()
        self.assertEqual(done, 0)
        self.assertEqual(self.tree(self.shows), {"Show Q/Show Q Season 2 Part 2 - E01.mp4"})

    def test_the_year_found_in_one_episode_names_the_whole_show(self):
        self.touch(self.shows, "Doctor.Who.2005.S01E01.mkv")
        self.touch(self.shows, "Doctor.Who.S01E02.mkv")
        self.do()
        self.assertEqual(self.tree(self.shows), {"Doctor Who (2005)/Season 01/Doctor Who S01E01.mkv", "Doctor Who (2005)/Season 01/Doctor Who S01E02.mkv"})

    def test_a_file_without_an_episode_number_is_left_alone(self):
        self.touch(self.shows, "Show X", "random video.mkv")
        (done, _f, _l), groups = self.do()
        self.assertEqual(done, 0)
        self.assertEqual(len(groups[1][4]), 1)
        self.assertEqual(self.tree(self.shows), {"Show X/random video.mkv"})

    def test_trailers_and_samples_are_not_touched(self):
        self.touch(self.movies, "Movie.2020.1080p", "Movie.2020.1080p.mkv")
        self.touch(self.movies, "Movie.2020.1080p", "Sample", "sample.mkv")
        self.touch(self.movies, "Movie.2020.1080p", "Movie.2020-trailer.mkv")
        self.do()
        self.assertEqual(self.tree(self.movies), {"Movie (2020)/Movie (2020).mkv", "Movie.2020.1080p/Sample/sample.mkv", "Movie.2020.1080p/Movie.2020-trailer.mkv"})

    def test_an_emptied_folder_is_removed_and_undo_puts_everything_back(self):
        self.touch(self.movies, "Inception.2010.1080p", "inception.mkv")
        self.touch(self.movies, "Inception.2010.1080p", "inception.en.srt")
        self.touch(self.shows, "Breaking.Bad.S01.1080p", "Breaking.Bad.S01E01.mkv")
        before = (self.tree(self.movies), self.tree(self.shows), sorted(os.listdir(self.movies)), sorted(os.listdir(self.shows)))
        (done, failed, _log), _g = self.do()
        self.assertEqual((done, failed), (2, []))
        self.assertEqual(sorted(os.listdir(self.movies)), ["Inception (2010)"])
        self.assertEqual(sorted(os.listdir(self.shows)), ["Breaking Bad"])
        self.assertEqual(self.r.undo(), 0)
        self.assertEqual((self.tree(self.movies), self.tree(self.shows), sorted(os.listdir(self.movies)), sorted(os.listdir(self.shows))), before)

    def test_folders_left_empty_are_removed_and_come_back_with_undo(self):
        self.touch(self.shows, "Breaking.Bad.S01.1080p", "Breaking.Bad.S01E01.mkv")
        os.makedirs(os.path.join(self.shows, "Breaking.Bad.S01.1080p", "Season 1"))
        os.makedirs(os.path.join(self.shows, "Unrelated empty folder"))
        self.touch(self.movies, "Heat.1995.mkv")
        self.do()
        self.assertEqual(sorted(os.listdir(self.shows)), ["Breaking Bad", "Unrelated empty folder"])
        self.assertTrue(os.path.isdir(self.movies))
        self.r.undo()
        self.assertTrue(os.path.isdir(os.path.join(self.shows, "Breaking.Bad.S01.1080p", "Season 1")))
        self.assertEqual(self.tree(self.movies), {"Heat.1995.mkv"})

    def test_dry_run_changes_nothing(self):
        self.touch(self.movies, "Heat.1995.1080p.mkv")
        self.assertEqual(self.r.main(["--dry-run", "--movies", self.movies, "--shows", self.shows]), 0)
        self.assertEqual(self.tree(self.movies), {"Heat.1995.1080p.mkv"})

    def test_without_a_terminal_and_without_yes_nothing_is_changed(self):
        self.touch(self.movies, "Heat.1995.1080p.mkv")
        with mock.patch("sys.stdin.isatty", return_value=False):
            self.assertEqual(self.r.main(["--movies", self.movies, "--shows", self.shows]), 1)
        self.assertEqual(self.tree(self.movies), {"Heat.1995.1080p.mkv"})


if __name__ == "__main__":
    unittest.main()
