"""Daily Facebook photo publisher. Python 3.12+, standard library only."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent
PAGE_ID = "61574574579911"


def save(state):
    temporary = ROOT / "state.json.tmp"
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary.replace(ROOT / "state.json")


def git_save(message):
    for args in (["add", "state.json"], ["commit", "-m", message], ["push", "origin", "HEAD"]):
        subprocess.run(["git", *args], cwd=ROOT, check=True)


def load():
    state = json.loads((ROOT / "state.json").read_text(encoding="utf-8"))
    index, total = state["current_index"], state["total_images"]
    if type(index) is not int or type(total) is not int or not 1 <= index <= total:
        raise ValueError("State must contain integer indices: 1 <= current_index <= total_images.")
    if state.get("pending"):
        raise ValueError("Unresolved posting attempt. Check Facebook and follow README recovery instructions.")
    return state


def photo_path(index):
    path = ROOT / "images" / f"image_{index}.jpg"
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"Missing or empty image: {path.name}")
    if path.read_bytes()[:3] != b"\xff\xd8\xff":
        raise ValueError(f"Not a JPEG: {path.name}")
    return path


def api(request):
    try:
        with urlopen(request, timeout=90) as response:
            return json.load(response)
    except HTTPError as error:
        # Do not print response bodies or URLs, which may contain credentials.
        raise RuntimeError(f"Meta returned HTTP {error.code}. Check token and Page permissions.") from None
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Meta request failed ({type(error).__name__}); outcome may be uncertain.") from None


def publish(path, caption, token, base):
    boundary = uuid.uuid4().hex
    data = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="message"\r\n\r\n{caption}\r\n'
        f'--{boundary}\r\nContent-Disposition: form-data; name="published"\r\n\r\ntrue\r\n'
        f'--{boundary}\r\nContent-Disposition: form-data; name="source"; filename="{path.name}"\r\n'
        'Content-Type: image/jpeg\r\n\r\n'
    ).encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    result = api(Request(base + "/photos", data=data, headers={
        "Authorization": "Bearer " + token,
        "Content-Type": "multipart/form-data; boundary=" + boundary,
    }, method="POST"))
    if not isinstance(result, dict) or not result.get("id"):
        raise RuntimeError("Meta did not return a photo ID. Inspect the Page before retrying.")
    return str(result["id"])


def run(dry_run=False, persist=False):
    state = load()
    index = state["current_index"]
    path = photo_path(index)
    caption_file = path.with_suffix(".txt")
    caption = caption_file.read_text(encoding="utf-8").strip() if caption_file.exists() else f"Daily Post #{index}"
    if dry_run:
        print(f"Validated {path.name} for Page {PAGE_ID}. Caption: {caption}")
        return
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN", "").strip()
    version = os.environ.get("FB_GRAPH_API_VERSION", "")
    page = os.environ.get("FB_PAGE_ID", PAGE_ID)
    if page != PAGE_ID:
        raise ValueError("FB_PAGE_ID differs from the configured target Page.")
    if not token or not re.fullmatch(r"v[0-9]+\.0", version):
        raise ValueError("Set FB_PAGE_ACCESS_TOKEN and FB_GRAPH_API_VERSION (a supported version from your Meta app).")
    base = f"https://graph.facebook.com/{version}/{PAGE_ID}"
    identity = api(Request(base + "?fields=id,name", headers={"Authorization": "Bearer " + token}))
    if str(identity.get("id")) != PAGE_ID:
        raise ValueError("Could not verify the target Page with this token.")
    state["pending"] = {"index": index, "started_at": datetime.now(timezone.utc).isoformat()}
    save(state)
    if persist:
        git_save("Record pending Facebook post [skip ci]")
    # No automatic retry: a timeout can happen after Facebook has published.
    photo_id = publish(path, caption, token, base)
    state["last_post"] = {"index": index, "photo_id": photo_id, "posted_at": datetime.now(timezone.utc).isoformat()}
    state["current_index"] = index % state["total_images"] + 1
    state["pending"] = None
    save(state)
    if persist:
        git_save("Advance Facebook photo index [skip ci]")
    print(f"Published photo {photo_id}; next image is {state['current_index']}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Validate next image without network access or state changes")
    parser.add_argument("--persist", action="store_true", help="Commit and push state before and after publishing")
    args = parser.parse_args()
    try:
        run(args.dry_run, args.persist)
    except (ValueError, OSError, RuntimeError, KeyError, subprocess.CalledProcessError) as error:
        # Error messages are deliberately sanitized in api(); never print headers or tokens.
        print(f"Posting stopped: {error}", file=sys.stderr)
        sys.exit(1)
