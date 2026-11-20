"""The static results page stays on the Reader shell and the site floor (stdlib only)."""

import json
import re
import unittest
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"


class SiteTest(unittest.TestCase):
    def setUp(self):
        self.html = (SITE / "index.html").read_text()
        self.script = (SITE / "app.js").read_text()

    def test_uses_the_shell_and_a_self_hosted_font(self):
        self.assertIn('href="reader-shell.css"', self.html)
        self.assertIn('class="rs"', self.html)
        self.assertIn('href="#main"', self.html)
        self.assertIn('id="main"', self.html)
        self.assertTrue((SITE / "fonts" / "geist-latin.woff2").is_file())
        self.assertNotRegex(self.html, r"fonts\.googleapis|vercel-insights|speed-insights")

    def test_font_ships_with_the_full_ofl_text(self):
        ofl = (SITE / "fonts" / "OFL.txt").read_text()
        self.assertIn("Copyright", ofl)
        self.assertIn("The Geist Project Authors", ofl)
        self.assertIn("SIL OPEN FONT LICENSE Version 1.1", ofl)
        self.assertIn("PERMISSION & CONDITIONS", ofl)
        self.assertIn("DISCLAIMER", ofl)
        self.assertIn("OFL.txt", (SITE / "fonts" / "LICENSE.txt").read_text())

    def test_metric_legend_matches_what_the_runner_measures(self):
        legend = re.sub(r"\s+", " ", self.html)
        self.assertIn("deploy script takes to return", legend)
        self.assertIn("deploy script returning to the first <code>/health</code>", legend)
        self.assertNotIn("under the same load", legend)
        self.assertIn("separate test: 4 concurrent connections for 20 seconds", legend)
        self.assertIn("20 concurrent connections, median of 3 runs of 30 seconds", legend)

    def test_links_back_to_the_hub_and_redirects_more_projects(self):
        self.assertIn('href="https://bookchaowalit.com/"', self.html)
        redirects = json.loads((SITE / "vercel.json").read_text())["redirects"]
        self.assertIn(
            {
                "source": "/more-projects",
                "destination": "https://bookchaowalit.com/",
                "permanent": True,
            },
            redirects,
        )
        self.assertIn(
            "cloud-benchmark-lab.vercel.app/sitemap.xml", (SITE / "robots.txt").read_text()
        )

    def test_empty_and_error_states_say_what_happens_next(self):
        self.assertIn('role="status"', self.html)
        for text in (
            "No published runs yet",
            "workflow_dispatch",
            "ADR-0003-railway.md",
            "ADR-0006-cloud-run.md",
            "Could not load the results",
        ):
            self.assertIn(text, self.script)

    def test_errors_above_zero_are_marked(self):
        self.assertIn("dd.dataset.bad", self.script)
        self.assertIn('[data-bad="true"]', (SITE / "site.css").read_text())

    def test_no_text_below_12px_in_site_css(self):
        sizes = [
            int(s)
            for s in re.findall(r"font(?:-size)?:[^;]*?(\d+)px", (SITE / "site.css").read_text())
        ]
        self.assertTrue(sizes)
        self.assertGreaterEqual(min(sizes), 12)


if __name__ == "__main__":
    unittest.main()
