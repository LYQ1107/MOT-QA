"""Archive official documentation over direct connections; do not download datasets."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
class Redirect308(urllib.request.HTTPRedirectHandler):
    # System Python 3.10 does not dispatch HTTP 308; hf-mirror currently uses it.
    def http_error_308(self, request, fp, code, message, headers):
        return self.http_error_302(request, fp, 307, message, headers)


OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), Redirect308())


def fetch(name, url, optional=False):
    request = urllib.request.Request(url, headers={"User-Agent": "MOT-QA-Pilot-stage1-inventory"})
    status = 200
    try:
        with OPENER.open(request, timeout=35) as response:
            data = response.read()
            status = response.status
    except urllib.error.HTTPError as error:
        status = error.code
        data = error.read()
        if status not in (404, 410) or not optional:
            record(name, url, data, status, error=str(error))
            raise
    except Exception as error:
        record(name, url, b"", None, error=repr(error))
        raise
    target = ROOT / "sources" / name
    target.write_bytes(data)
    row = record(name, url, data, status)
    print(json.dumps(row), flush=True)
    return data


def record(name, url, data, status, error=None):
    row = dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),
               resource=name, url=url, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
               http_status=status, direct=True, error=error)
    with (ROOT / "logs" / "network_transfers.jsonl").open("a") as stream:
        stream.write(json.dumps(row) + "\n")
    with (ROOT / "logs" / "downloads.md").open("a") as stream:
        stream.write(f"| {row['time']} | {name} | {url} | {len(data)} | {row['sha256']} | HTTP {status}; {error or 'direct'} |\n")
    return row


def repo(owner, repo, prefix):
    latest = json.loads(fetch(prefix + "_commits.json", f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=1"))
    revision = latest[0]["sha"]
    tree = json.loads(fetch(prefix + "_tree.json", f"https://api.github.com/repos/{owner}/{repo}/git/trees/{revision}?recursive=1"))
    paths = {x["path"] for x in tree["tree"]}
    fetch(prefix + "_README.md", f"https://raw.githubusercontent.com/{owner}/{repo}/{revision}/README.md")
    for candidate in ("LICENSE", "LICENSE.md", "LICENSE.txt"):
        if candidate in paths:
            fetch(prefix + "_" + candidate, f"https://raw.githubusercontent.com/{owner}/{repo}/{revision}/{candidate}")
    return dict(repository=f"https://github.com/{owner}/{repo}", revision=revision,
                tree_truncated=tree.get("truncated"), files=len(paths))


def main():
    for key in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
        os.environ.pop(key, None)
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
    registry = {}
    # Sequential writes preserve a readable download log.
    for owner, name, prefix in [("DanceTrack", "DanceTrack", "dancetrack"),
                                ("MCG-NJU", "SportsMOT", "sportsmot"),
                                ("Nathan-Li123", "LaMOT", "lamot"),
                                ("dyhBUPT", "iKUN", "ikun")]:
        registry[prefix] = repo(owner, name, prefix)
    for name, url, optional in [
        ("dancetrack_paper.html", "https://arxiv.org/html/2111.14690v3", False),
        ("sportsmot_paper.html", "https://arxiv.org/html/2304.05170v2", False),
        ("motchallenge_paper.html", "https://arxiv.org/html/2010.07548v2", False),
        ("ikun_paper.html", "https://arxiv.org/html/2312.16245v2", False),
        ("motchallenge_site.html", "https://motchallenge.net/", True),
        ("mot17_official.html", "https://motchallenge.net/data/MOT17/", False),
    ]:
        fetch(name, url, optional=optional)
    (ROOT / "results" / "official_source_registry.json").write_text(json.dumps(registry, indent=2) + "\n")


if __name__ == "__main__":
    main()
