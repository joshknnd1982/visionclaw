# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Brings the guides that come with every build of VisionClaw up to date.

Only the guides named in guides.MAY_SHIP are fetched: those whose owner allows them to be passed on. Each is
read from the address fixed in guides.SOURCES, turned into Markdown by the same code the add-on uses, and
written to addon/globalPlugins/visionClaw/claw/shipped/guides with a line at its top that says whose it is and
under which licence, and a record of the day. Run it before a release, then build:

  python tools/update_shipped_guides.py [folder with pages fetched earlier]

With a folder, nothing goes online: a page is read from the file in it whose name is the last part of the
page's address. Nothing about anyone is sent; it is a plain request for a public page.
"""
import datetime
import json
import os
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import harness  # noqa: E402,F401
from visionClaw.claw import guides  # noqa: E402

AGENT = "VisionClaw build tool"


def fetch(url, folder=""):
	if folder:
		with open(os.path.join(folder, url.rsplit("/", 1)[-1]), encoding="utf-8", errors="replace") as f:
			return f.read()
	if urllib.parse.urlparse(url).hostname not in guides.HOSTS or not url.startswith("https://"):
		raise ValueError(f"{url} is not one of the fixed addresses")
	with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": AGENT}), timeout=60) as answer:
		if urllib.parse.urlparse(answer.geturl()).hostname not in guides.HOSTS:
			raise ValueError(f"{url} was answered from somewhere else")
		return answer.read(guides.MAX_BYTES).decode("utf-8", errors="replace")


def main():
	sys.stdout.reconfigure(errors="replace")
	folder = sys.argv[1] if len(sys.argv) > 1 else ""
	day = datetime.date.today().isoformat()
	os.makedirs(guides.SHIPPED, exist_ok=True)
	record = {}
	for source in guides.SOURCES:
		path = os.path.join(guides.SHIPPED, source["id"] + ".md")
		if source["id"] not in guides.MAY_SHIP:
			# Never left in the build by an earlier run: what may not be passed on is not shipped.
			if os.path.isfile(path):
				os.remove(path)
			print(f"not shipped (its owner has not said it may be passed on): {source['title']}")
			continue
		text = fetch(source["url"], folder)
		markdown = guides.toMarkdown(text) if source["html"] else guides.tidy(text)
		count = len(guides.cut(markdown))
		if len(markdown) < guides.MIN_CHARS or count < 5:
			sys.exit(f"What came back for the {source['title']} is not the guide. Nothing was changed for it.")
		# What stands before the first heading is not read as part of the guide (guides.cut).
		head = (
			f"<!-- {source['title']}, by {source['by']} and contributors. {guides.MAY_SHIP[source['id']]}. From "
			f"{source['url']} on {day}, turned into Markdown by VisionClaw. -->\n\n")
		with open(path, "w", encoding="utf-8", newline="\n") as f:
			f.write(head + markdown)
		record[source["title"]] = {"date": day, "sections": count, "format": guides.FORMAT, "licence": guides.MAY_SHIP[source["id"]]}
		print(f"shipped: {source['title']}, {count} sections, {len(markdown)} characters")
	with open(os.path.join(guides.SHIPPED, guides.RECORD), "w", encoding="utf-8", newline="\n") as f:
		json.dump(record, f, indent=1)
		f.write("\n")


if __name__ == "__main__":
	main()
