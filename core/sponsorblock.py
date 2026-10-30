"""Skip sponsor reads in YouTube episodes, with SponsorBlock (sponsor.ajay.app): segments marked by viewers
("this part is an ad read", "subscribe reminder"...). No account.

Privacy: the video is never named. Only the first 4 characters of the video id's SHA-256 hash are sent, the
service answers with the segments of every video sharing that prefix, and the right one is picked here
(SponsorBlock's privacy-preserving "k-anonymity" lookup).

YouTube's own ads aren't in the streams Sevbify plays; what's left are ads the hosts read themselves, which is
exactly what SponsorBlock marks. Podcast feeds (RSS) with ads stitched in by the host can't be skipped this way.
"""
import hashlib
import json
import re

API = "https://sponsor.ajay.app/api/skipSegments/"
CATEGORIES = ["sponsor", "selfpromo", "interaction"]
_ID = re.compile(r"(?:v=|youtu\.be/|/shorts/|/live/|/embed/)([A-Za-z0-9_-]{11})")


def video_id(page_url):
    m = _ID.search(page_url or "")
    return m.group(1) if m else ""


def segments(net, page_url, categories=None):
    """[[start_ms, end_ms, category], ...] to skip in a YouTube video, sorted; [] when there are none."""
    vid = video_id(page_url)
    if not vid:
        return []
    prefix = hashlib.sha256(vid.encode("ascii")).hexdigest()[:4]
    cats = json.dumps(categories or CATEGORIES)
    try:
        data = net.get_json(API + prefix, {"categories": cats, "actionType": "skip"}, ttl=6 * 3600)
    except Exception as exc:                # 404 = no segments for any video with this prefix
        if "404" in str(exc):
            return []
        raise
    out = []
    for video in data if isinstance(data, list) else []:
        if not isinstance(video, dict) or video.get("videoID") != vid:
            continue
        for s in video.get("segments") or []:
            seg = s.get("segment") or []
            if len(seg) == 2 and s.get("actionType", "skip") == "skip":
                start, end = float(seg[0]), float(seg[1])
                if end - start >= 1:
                    out.append([int(start * 1000), int(end * 1000), s.get("category", "")])
    return sorted(out)
