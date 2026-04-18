"""Parse 2026-04-18_전임상개론_조별_정리.md into docs/data.json."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MD_PATH = ROOT / "2026-04-18_전임상개론_조별_정리.md"
OUT_PATH = ROOT / "docs" / "data.json"

GROUP_HEADER_RE = re.compile(r"^##\s*(\d+)조\s*$", re.MULTILINE)
LEADER_RE = re.compile(r"조장:\s*(.+)")
TOPIC_RE = re.compile(r"발표주제:\s*(.+)")
MEMBER_RE = re.compile(
    r"-\s*([가-힣A-Za-z]+)\s*\((\d{8}),\s*([가-힣]+)\s*(\d)학년\)"
)
SLIDE_PREFIX_RE = re.compile(r"^슬라이드\s*(\d+)번\s*(.+)$")


def parse_group(block: str, group_id: int) -> dict:
    leader_match = LEADER_RE.search(block)
    leader_raw = leader_match.group(1).strip() if leader_match else "미정"
    leader = None if leader_raw in ("미정", "-") else leader_raw

    topic_match = TOPIC_RE.search(block)
    topic_raw = topic_match.group(1).strip() if topic_match else "미정"
    topic_confirmed = topic_raw != "미정"

    topic_text = topic_raw if topic_confirmed else None
    if topic_text:
        # Strip any leading "슬라이드 N번" reference from the topic name.
        m = SLIDE_PREFIX_RE.match(topic_text)
        if m:
            topic_text = m.group(2).strip().strip("`")

    members = [
        {
            "name": name,
            "studentId": sid,
            "department": dept,
            "year": int(year),
        }
        for name, sid, dept, year in MEMBER_RE.findall(block)
    ]

    gif_path = (
        f"assets/gifs/group-{group_id}.gif"
        if topic_confirmed
        else "assets/gifs/placeholder.gif"
    )

    return {
        "id": group_id,
        "leader": leader,
        "topic": topic_text,
        "topicConfirmed": topic_confirmed,
        "gifPath": gif_path,
        "members": members,
    }


def main() -> None:
    text = MD_PATH.read_text(encoding="utf-8")
    headers = list(GROUP_HEADER_RE.finditer(text))
    groups: list[dict] = []
    for i, h in enumerate(headers):
        start = h.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block = text[start:end]
        groups.append(parse_group(block, int(h.group(1))))

    payload = {
        "generatedAt": date.today().isoformat(),
        "source": MD_PATH.name,
        "groups": groups,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    total_members = sum(len(g["members"]) for g in groups)
    confirmed = sum(1 for g in groups if g["topicConfirmed"])
    leaders = sum(1 for g in groups if g["leader"])
    print(
        f"Wrote {OUT_PATH.relative_to(ROOT)}: "
        f"{len(groups)} groups, {total_members} members, "
        f"{leaders} leaders set, {confirmed} topics confirmed"
    )


if __name__ == "__main__":
    main()
