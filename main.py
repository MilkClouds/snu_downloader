import argparse
import functools
import json
import logging
import pathlib
import re
import shutil
import time
from pathlib import Path

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from tqdm.auto import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

ETL_ROOT = "https://myetl.snu.ac.kr"
API_ROOT = f"{ETL_ROOT}/api/v1"
COOKIE_FILE = Path(__file__).parent / ".cookies.json"


# --- Utilities ---


def yes_or_no(question):
    while True:
        reply = input(question + " (y/n): ").lower().strip()
        if reply.startswith("y"):
            return True
        if reply.startswith("n"):
            return False


def sanitize(name: str) -> str:
    return re.sub(r'[\\/:"*?<>|]+', "", name)


def download_file(url, filepath, cookies=None):
    """Download a file with progress bar. Skips if already exists."""
    if filepath.exists():
        logging.info(f"  [skip] {filepath.name}")
        return
    logging.info(f"  [download] {filepath.name}")
    r = requests.get(url, stream=True, allow_redirects=True, cookies=cookies)
    if r.status_code != 200:
        logging.warning(f"  [error] {filepath.name} - HTTP {r.status_code}")
        return
    file_size = int(r.headers.get("Content-Length", 0))
    filepath.parent.mkdir(parents=True, exist_ok=True)
    r.raw.read = functools.partial(r.raw.read, decode_content=True)
    with logging_redirect_tqdm():
        with tqdm.wrapattr(r.raw, "read", total=file_size, desc="") as r_raw:
            with filepath.open("wb") as f:
                shutil.copyfileobj(r_raw, f)


# --- SSO Login ---


def _save_cookies(cookies):
    COOKIE_FILE.write_text(json.dumps(cookies), encoding="utf-8")


def _load_cookies():
    if COOKIE_FILE.exists():
        try:
            cookies = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
            # Test if cookies are still valid
            r = requests.get(f"{API_ROOT}/users/self", cookies=cookies)
            if r.status_code == 200:
                logging.info("저장된 쿠키로 로그인 성공!")
                return cookies
        except Exception:
            pass
    return None


def sso_login():
    """Return session cookies, reusing saved ones if valid."""
    cookies = _load_cookies()
    if cookies:
        return cookies

    options = webdriver.ChromeOptions()
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(5)

    driver.get(ETL_ROOT)
    logging.info("브라우저에서 SSO 로그인을 완료해주세요 (MFA 포함)...")

    for _ in range(120):
        time.sleep(1)
        try:
            alert = driver.switch_to.alert
            alert.accept()
            continue
        except Exception:
            pass
        try:
            url = driver.current_url
            if "myetl.snu.ac.kr" in url and "nsso" not in url:
                logging.info("로그인 성공!")
                cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
                driver.quit()
                _save_cookies(cookies)
                return cookies
        except Exception:
            pass

    driver.quit()
    raise TimeoutError("로그인 시간 초과 (2분)")


# --- Canvas API ---


def api_get_all(endpoint, cookies, params=None):
    """Fetch all pages from a Canvas API endpoint."""
    import json

    if params is None:
        params = {}
    params["per_page"] = 100
    url = f"{API_ROOT}{endpoint}"
    results = []
    while url:
        r = requests.get(url, cookies=cookies, params=params)
        r.raise_for_status()
        # Canvas prepends "while(1);" to JSON responses as CSRF protection
        text = r.text.removeprefix("while(1);")
        results.extend(json.loads(text))
        # Follow pagination via Link header
        url = None
        params = None  # params already encoded in Link URLs
        link = r.headers.get("Link", "")
        for part in link.split(","):
            if 'rel="next"' in part:
                url = part.split("<")[1].split(">")[0]
    return results


def get_courses(cookies, semester=None):
    """Fetch enrolled courses, optionally filtered by semester."""
    courses = api_get_all("/courses", cookies, {"enrollment_state": "active"})
    if semester:
        courses = [c for c in courses if semester in c.get("name", "")]
    return courses


def get_files(cookies, course_id):
    """Fetch all files in a course."""
    return api_get_all(f"/courses/{course_id}/files", cookies)


def get_folders(cookies, course_id):
    """Fetch all folders in a course."""
    return api_get_all(f"/courses/{course_id}/folders", cookies)


def get_assignments(cookies, course_id):
    """Fetch all assignments in a course."""
    return api_get_all(f"/courses/{course_id}/assignments", cookies)


def get_modules(cookies, course_id):
    """Fetch all modules with items."""
    return api_get_all(f"/courses/{course_id}/modules", cookies, {"include[]": "items"})


# --- Download logic ---


def download_course(cookies, course, output_dir: Path):
    """Download all files and show assignments for a course."""
    course_id = course["id"]
    course_name = sanitize(course.get("name", str(course_id)))
    course_dir = output_dir / course_name
    course_dir.mkdir(parents=True, exist_ok=True)

    logging.info(f"\n{'='*60}")
    logging.info(f"📁 {course_name}")
    logging.info(f"{'='*60}")

    # --- Files ---
    try:
        folders = {f["id"]: f.get("full_name", "") for f in get_folders(cookies, course_id)}
        files = get_files(cookies, course_id)
        logging.info(f"\n  파일 ({len(files)}개)")

        for f in files:
            folder_path = folders.get(f.get("folder_id"), "")
            # Strip "course files/" prefix from folder path
            folder_path = re.sub(r"^course files/?", "", folder_path)
            file_dir = course_dir / "files" / folder_path if folder_path else course_dir / "files"
            filepath = file_dir / sanitize(f["display_name"])
            download_file(f["url"], filepath, cookies=cookies)
    except Exception as e:
        logging.warning(f"  파일 목록 조회 실패: {e}")

    # --- Assignments ---
    try:
        assignments = get_assignments(cookies, course_id)
        if assignments:
            logging.info(f"\n  과제 ({len(assignments)}개)")
            assignment_dir = course_dir / "assignments"
            assignment_dir.mkdir(parents=True, exist_ok=True)

            for a in assignments:
                name = a.get("name", "Untitled")
                due = a.get("due_at", "기한 없음")
                points = a.get("points_possible", "?")
                sub_types = ", ".join(a.get("submission_types", []))
                logging.info(f"  [{name}] 마감: {due} | 배점: {points} | 제출: {sub_types}")

                # Save assignment description as HTML
                desc = a.get("description")
                if desc:
                    desc_file = assignment_dir / f"{sanitize(name)}.html"
                    if not desc_file.exists():
                        desc_file.write_text(desc, encoding="utf-8")
    except Exception as e:
        logging.warning(f"  과제 목록 조회 실패: {e}")


# --- Main ---

DISCLAIMER = """\
==============================================================================================================================
DISCLAIMER: This program is not affiliated with SNU. Use at your own risk.
==============================================================================================================================
The information provided by SNU eTL Batch Downloader ("we," "us," or "our") on our application is for general
informational purposes only. All information on our application is provided in good faith, however we make no
representation or warranty of any kind, express or implied, regarding the accuracy, adequacy, validity, reliability,
availability, or completeness of any information on our application. UNDER NO CIRCUMSTANCE SHALL WE HAVE ANY LIABILITY
TO YOU FOR ANY LOSS OR DAMAGE OF ANY KIND INCURRED AS A RESULT OF THE USE OF OUR APPLICATION OR RELIANCE ON ANY
INFORMATION PROVIDED ON OUR APPLICATION. YOUR USE OF OUR APPLICATION AND YOUR RELIANCE ON ANY INFORMATION ON OUR
APPLICATION IS SOLELY AT YOUR OWN RISK.
==============================================================================================================================
본 프로그램에 의해 제공된 모든 정보는 일반적인 목적으로만 사용할 수 있습니다. 이 프로그램의/으로 만들어진 모든 정보는 공익을
위한 것이나, 개발자는 프로그램의 안정성, 적법성, 정확성, 정밀성, 의존성, 가용성, 완전성에 대하여 그 어떤 보증을 보장하지도,
함의하지도 않습니다. 이러한 조건 하에 개발자는 이 프로그램의 사용이나 생성된 정보로 인한 그 어떤 피해나 행위에 관해서도 책임을
지지 않습니다. 이 프로그램을 사용하는 것은 상기 내용에 동의하였으며, 프로그램의 사용으로 인한 책임은 전부 사용자에게 있습니다.
==============================================================================================================================
By using this program, you agree to the above terms.
=============================================================================================================================="""

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.info(DISCLAIMER)

    if not yes_or_no("Do you agree with the terms above?"):
        exit()

    parser = argparse.ArgumentParser(description="SNU eTL Batch Downloader")
    parser.add_argument("-d", dest="outputDir", default=".", type=Path, help="Directory to save files")
    parser.add_argument("-l", dest="lectureId", type=str, default="all", help="Lecture ID or 'all'")
    parser.add_argument("-s", dest="semester", type=str, default=None, help="Semester filter (e.g. '2026-1')")
    args = parser.parse_args()

    cookies = sso_login()

    if args.lectureId == "all":
        courses = get_courses(cookies, semester=args.semester)
    else:
        # Single course - fetch its info
        r = requests.get(f"{API_ROOT}/courses/{args.lectureId}", cookies=cookies)
        r.raise_for_status()
        courses = [r.json()]

    logging.info(f"\n{len(courses)}개 강의 발견")
    for course in courses:
        download_course(cookies, course, args.outputDir)

    logging.info(f"\n완료!")
