import subprocess
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(call):
    out = subprocess.run(
        ["bash", "-c", f"source ./cleanup_policy.sh; {call} && echo yes || echo no"],
        cwd=HERE, capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def delete(conclusion, age_days, successful_seen):
    return run(f"should_delete {conclusion} {age_days} {successful_seen}") == "yes"


class ShouldDeleteTest(unittest.TestCase):
    def test_newest_success_always_stays(self):
        self.assertFalse(delete("success", 400, 1))

    def test_older_success_stays_for_14_days(self):
        # A PR's CI proof must outlive the merge check.
        self.assertFalse(delete("success", 0, 2))
        self.assertFalse(delete("success", 13, 5))

    def test_older_success_goes_after_14_days(self):
        self.assertTrue(delete("success", 14, 2))

    def test_failed_after_7_days(self):
        self.assertFalse(delete("failure", 6, 0))
        self.assertTrue(delete("timed_out", 7, 0))

    def test_cancelled_and_unknown_after_1_day(self):
        self.assertFalse(delete("cancelled", 0, 0))
        self.assertTrue(delete("skipped", 1, 0))
        self.assertTrue(delete("null", 1, 0))


class SkipRepoTest(unittest.TestCase):
    def test_fillz_repos_are_skipped(self):
        for name in ("nomercy-ci", "nomercy-github-runner", "nomercy-ffmpeg",
                     "nomercy-ffmpeg-secrets", "nomercy-whisper-gguf-models",
                     "nomercy-whisper-models"):
            self.assertEqual(run(f"skip_repo NoMercy-Entertainment/{name}"), "yes", name)

    def test_other_repos_are_cleaned(self):
        self.assertEqual(run("skip_repo NoMercy-Entertainment/nomercy-media-server"), "no")
        self.assertEqual(run("skip_repo NoMercy-Entertainment/nomercy-ffmpeg-tools"), "no")


if __name__ == "__main__":
    unittest.main()
