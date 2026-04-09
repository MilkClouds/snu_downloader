"""Fetch calendar events (events + assignments) from SNU eTL (Canvas).

Reuses login/session logic from main.py. Run:
    uv run python calendar_fetch.py                   # all upcoming events
    uv run python calendar_fetch.py -s 2026-1         # filter courses by semester
    uv run python calendar_fetch.py --days 14         # look ahead N days (default 30)
    uv run python calendar_fetch.py --past            # include past events too
"""

import argparse
import logging
from datetime import datetime, timedelta, timezone

from main import API_ROOT, api_get_all, get_courses, sso_login

KST = timezone(timedelta(hours=9))


# Canvas caps context_codes[] at 10 per request; batch to stay under the limit.
CONTEXT_CODE_BATCH = 10


def fetch_calendar_events(cookies, context_codes, start_date, end_date, event_type):
    """Fetch calendar events or assignment events, batching context_codes."""
    results: list[dict] = []
    seen_ids: set = set()
    for i in range(0, len(context_codes), CONTEXT_CODE_BATCH):
        batch = context_codes[i : i + CONTEXT_CODE_BATCH]
        params = {
            "type": event_type,
            "start_date": start_date,
            "end_date": end_date,
            "context_codes[]": batch,
        }
        events = api_get_all("/calendar_events", cookies, params)
        for ev in events:
            eid = ev.get("id")
            if eid in seen_ids:
                continue
            seen_ids.add(eid)
            results.append(ev)
    return results


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _fmt_kst(dt: datetime | None) -> str:
    if dt is None:
        return "기한 없음"
    return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M KST")


def _format_entry(
    ev: dict,
    course_name_by_code: dict[str, str],
    submission_by_assignment: dict[int, dict],
) -> tuple[datetime, str]:
    title = ev.get("title") or "(제목 없음)"
    ctx = ev.get("context_code", "")
    course_label = course_name_by_code.get(ctx, ctx)

    # Assignments expose due_at under ev["assignment"]; plain events use start_at.
    assignment = ev.get("assignment") or {}
    due = _parse_iso(assignment.get("due_at")) or _parse_iso(ev.get("start_at"))
    points = assignment.get("points_possible")

    # Look up the current user's own submission state. Canvas's
    # assignment.has_submitted_submissions is course-wide (true if ANY student
    # submitted), so we can't use it to check whether *I* submitted.
    submission = submission_by_assignment.get(assignment.get("id")) if assignment else None
    user_submitted = bool(submission and submission.get("submitted_at"))
    workflow = (submission or {}).get("workflow_state")

    marker = ""
    if assignment:
        if user_submitted:
            marker = " [제출완료]" if workflow != "graded" else " [채점완료]"
        elif points is not None:
            marker = f" [{points}점]"
        else:
            marker = " [과제]"

    sort_key = due or datetime.max.replace(tzinfo=timezone.utc)
    line = f"  {_fmt_kst(due):<22} | {course_label:<30} | {title}{marker}"
    return sort_key, line


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(description="Fetch SNU eTL calendar events")
    parser.add_argument("-s", "--semester", default=None, help="filter courses by semester (e.g. 2026-1)")
    parser.add_argument("--days", type=int, default=30, help="look ahead N days (default 30)")
    parser.add_argument("--past", action="store_true", help="also include events from the past --days window")
    parser.add_argument(
        "--only",
        choices=["event", "assignment", "both"],
        default="both",
        help="fetch only events, only assignments, or both (default both)",
    )
    args = parser.parse_args()

    cookies = sso_login()
    courses = get_courses(cookies, semester=args.semester)
    if not courses:
        logging.info("조건에 맞는 강의가 없습니다.")
        return

    context_codes = [f"course_{c['id']}" for c in courses]
    course_name_by_code = {f"course_{c['id']}": c.get("name", str(c["id"])) for c in courses}

    # Build per-user submission lookup by fetching each course's assignments
    # with include[]=submission (returns the CURRENT user's submission inline).
    submission_by_assignment: dict[int, dict] = {}
    for c in courses:
        try:
            assignments = api_get_all(
                f"/courses/{c['id']}/assignments", cookies, {"include[]": "submission"}
            )
        except Exception as e:
            logging.warning(f"  [error] {c.get('name')} 과제 조회 실패: {e}")
            continue
        for a in assignments:
            sub = a.get("submission")
            if sub is not None:
                submission_by_assignment[a["id"]] = sub

    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=args.days)) if args.past else now
    end = now + timedelta(days=args.days)
    start_iso = start.date().isoformat()
    end_iso = end.date().isoformat()

    logging.info(f"강의 {len(courses)}개 | 기간 {start_iso} ~ {end_iso} | {API_ROOT}/calendar_events")

    types = ["event", "assignment"] if args.only == "both" else [args.only]
    entries: list[tuple[datetime, str]] = []
    for t in types:
        try:
            events = fetch_calendar_events(cookies, context_codes, start_iso, end_iso, t)
        except Exception as e:
            logging.warning(f"  [error] type={t} 조회 실패: {e}")
            continue
        logging.info(f"  {t}: {len(events)}개")
        for ev in events:
            entries.append(_format_entry(ev, course_name_by_code, submission_by_assignment))

    entries.sort(key=lambda x: x[0])
    if not entries:
        logging.info("\n표시할 일정이 없습니다.")
        return

    logging.info("\n" + "=" * 80)
    logging.info(f" 일정 ({len(entries)}개)")
    logging.info("=" * 80)
    for _, line in entries:
        logging.info(line)


if __name__ == "__main__":
    main()
