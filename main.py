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
import yt_dlp
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
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


def download_file(url, filepath, cookies=None, headers=None):
    """Download a file with progress bar. Skips if already exists."""
    if filepath.exists():
        logging.info(f"  [skip] {filepath.name}")
        return
    logging.info(f"  [download] {filepath.name}")
    r = requests.get(url, stream=True, allow_redirects=True, cookies=cookies, headers=headers)
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
    if params is None:
        params = {}
    params["per_page"] = 100
    url = f"{API_ROOT}{endpoint}"
    results = []
    while url:
        r = requests.get(url, cookies=cookies, params=params)
        r.raise_for_status()
        text = r.text.removeprefix("while(1);")
        results.extend(json.loads(text))
        url = None
        params = None
        link = r.headers.get("Link", "")
        for part in link.split(","):
            if 'rel="next"' in part:
                url = part.split("<")[1].split(">")[0]
    return results


def get_courses(cookies, semester=None):
    courses = api_get_all("/courses", cookies, {"enrollment_state": "active"})
    if semester:
        courses = [c for c in courses if semester in c.get("name", "")]
    return courses


def get_files(cookies, course_id):
    return api_get_all(f"/courses/{course_id}/files", cookies)


def get_folders(cookies, course_id):
    return api_get_all(f"/courses/{course_id}/folders", cookies)


def get_assignments(cookies, course_id):
    return api_get_all(f"/courses/{course_id}/assignments", cookies)


def get_modules(cookies, course_id):
    return api_get_all(f"/courses/{course_id}/modules", cookies, {"include[]": "items"})


# --- Video download ---


def _create_headless_driver(cookies):
    """Create a headless Chrome driver with eTL session cookies."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(5)
    driver.get(ETL_ROOT + "/123")
    for name, value in cookies.items():
        driver.add_cookie({"name": name, "value": value, "domain": "myetl.snu.ac.kr"})
    return driver


def download_video_items(cookies, course_id, course_dir: Path):
    """Download videos from ExternalTool/ExternalUrl module items."""
    modules = get_modules(cookies, course_id)
    video_items = []
    for m in modules:
        for item in m.get("items", []):
            if item["type"] in ("ExternalTool", "ExternalUrl"):
                video_items.append((m["name"], item))

    if not video_items:
        return

    logging.info(f"\n  영상 ({len(video_items)}개)")
    video_dir = course_dir / "_videos"
    video_dir.mkdir(parents=True, exist_ok=True)

    driver = None
    try:
        for module_name, item in video_items:
            title = sanitize(item["title"])
            item_type = item["type"]

            # ExternalUrl: check if YouTube
            if item_type == "ExternalUrl":
                ext_url = item.get("external_url", "")
                if "youtube.com" in ext_url or "youtu.be" in ext_url:
                    _download_youtube(ext_url, title, video_dir)
                else:
                    logging.info(f"  [skip] {title} (외부 링크: {ext_url[:60]})")
                continue

            # ExternalTool: SNU-CMS or YouTube embedded in iframe
            html_url = item.get("html_url", "")
            if not html_url:
                continue

            if driver is None:
                driver = _create_headless_driver(cookies)

            try:
                driver.get(html_url)
                time.sleep(3)

                # Find tool_content iframe (Canvas LTI container)
                try:
                    tool_iframe = driver.find_element(By.ID, "tool_content")
                except Exception:
                    logging.info(f"  [skip] {title} (tool_content iframe 없음)")
                    continue

                driver.switch_to.frame(tool_iframe)
                inner_iframes = driver.find_elements(By.TAG_NAME, "iframe")
                if inner_iframes:
                    driver.switch_to.frame(inner_iframes[0])

                src = driver.page_source

                # YouTube embedded
                if "onYouTubeIframeAPIReady" in src:
                    match = re.search(r"videoId:\s*'(.+?)'", src)
                    if match:
                        _download_youtube(f"https://www.youtube.com/watch?v={match.group(1)}", title, video_dir)
                    else:
                        logging.info(f"  [skip] {title} (YouTube ID 추출 실패)")
                # SNU-CMS video
                else:
                    match = re.search(r'var\s+content_id\s*=\s*"([^"]+)"', src)
                    if not match:
                        match = re.search(r'content_id=([a-f0-9]+)', src)
                    if match:
                        content_id = match.group(1)
                        video_url = _get_cms_video_url(content_id)
                        if video_url:
                            filepath = video_dir / f"{title}.mp4"
                            download_file(video_url, filepath, headers={"Referer": "https://lcms.snu.ac.kr"})
                        else:
                            logging.info(f"  [skip] {title} (영상 URL 조회 실패)")
                    else:
                        logging.info(f"  [skip] {title} (영상 ID 추출 실패)")

                driver.switch_to.default_content()

            except Exception as e:
                logging.warning(f"  [error] {title}: {e}")
                try:
                    driver.switch_to.default_content()
                except Exception:
                    pass
    finally:
        if driver:
            driver.quit()


def _get_cms_video_url(content_id: str) -> str | None:
    """Fetch actual video CDN URL from SNU-CMS content API."""
    try:
        r = requests.get(f"https://lcms.snu.ac.kr/viewer/ssplayer/uniplayer_support/content.php?content_id={content_id}")
        if r.status_code != 200:
            return None
        # Extract progressive media URL from XML
        match = re.search(r'method="progressive"\s+target="all">([^<]+)\[MEDIA_FILE\]', r.text)
        if match:
            return match.group(1) + "screen.mp4"
        # Fallback: try lcms direct URL
        return f"https://lcms.snu.ac.kr/contents/snu0000001/{content_id}/contents/media_files/screen.mp4"
    except Exception:
        return None


def _download_youtube(url, title, video_dir: Path):
    """Download a YouTube video using yt-dlp."""
    existing = list(video_dir.glob(f"{title}.*"))
    if existing:
        logging.info(f"  [skip] {title} (이미 존재)")
        return
    logging.info(f"  [yt-dlp] {title}")
    try:
        ydl_opts = {
            "outtmpl": str(video_dir / f"{title}.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        logging.warning(f"  [error] {title}: {e}")


# --- Download logic ---


def download_course(cookies, course, output_dir: Path):
    """Download all files, videos, and show assignments for a course."""
    course_id = course["id"]
    course_name = sanitize(course.get("name", str(course_id)))
    course_dir = output_dir / course_name
    course_dir.mkdir(parents=True, exist_ok=True)

    logging.info(f"\n{'='*60}")
    logging.info(f" {course_name}")
    logging.info(f"{'='*60}")

    # --- Files ---
    try:
        folders = {f["id"]: f.get("full_name", "") for f in get_folders(cookies, course_id)}
        files = get_files(cookies, course_id)
        logging.info(f"\n  파일 ({len(files)}개)")

        for f in files:
            folder_path = folders.get(f.get("folder_id"), "")
            # Strip "course files/" prefix, use eTL folder structure directly
            folder_path = re.sub(r"^course files/?", "", folder_path)
            file_dir = course_dir / folder_path if folder_path else course_dir
            filepath = file_dir / sanitize(f["display_name"])
            download_file(f["url"], filepath, cookies=cookies)
    except Exception as e:
        logging.warning(f"  파일 목록 조회 실패: {e}")

    # --- Videos ---
    try:
        download_video_items(cookies, course_id, course_dir)
    except Exception as e:
        logging.warning(f"  영상 다운로드 실패: {e}")

    # --- Assignments ---
    try:
        assignments = get_assignments(cookies, course_id)
        if assignments:
            logging.info(f"\n  과제 ({len(assignments)}개)")
            assignment_dir = course_dir / "_assignments"
            assignment_dir.mkdir(parents=True, exist_ok=True)

            for a in assignments:
                name = a.get("name", "Untitled")
                due = a.get("due_at", "기한 없음")
                points = a.get("points_possible", "?")
                sub_types = ", ".join(a.get("submission_types", []))
                logging.info(f"  [{name}] 마감: {due} | 배점: {points} | 제출: {sub_types}")

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

DEFAULT_OUTPUT_DIR = Path(__file__).parent / "downloads"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(
        description="SNU eTL Batch Downloader — download lecture files, videos, and assignments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
        "  %(prog)s                          # download all current courses\n"
        "  %(prog)s -s 2026-1                # download 2026 spring semester only\n"
        "  %(prog)s -l 296200                # download a single course by ID\n"
        "  %(prog)s -s 2026-1 -d ~/lectures  # save to custom directory\n"
        "  %(prog)s --logout                 # clear saved login session\n",
    )
    parser.add_argument("-d", "--dir", dest="outputDir", default=DEFAULT_OUTPUT_DIR, type=Path,
                        help=f"output directory (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("-l", "--lecture", dest="lectureId", type=str, default="all",
                        help="course ID, or 'all' to download every enrolled course (default: all)")
    parser.add_argument("-s", "--semester", type=str, default=None,
                        help="filter courses by semester (e.g. '2026-1')")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="skip the disclaimer prompt")
    parser.add_argument("--logout", action="store_true",
                        help="clear saved login cookies and exit")
    args = parser.parse_args()

    # Handle --logout
    if args.logout:
        if COOKIE_FILE.exists():
            COOKIE_FILE.unlink()
            logging.info("로그인 세션이 삭제되었습니다.")
        else:
            logging.info("저장된 세션이 없습니다.")
        exit()

    # Disclaimer
    if not args.yes:
        logging.info(DISCLAIMER)
        if not yes_or_no("Do you agree with the terms above?"):
            exit()

    try:
        cookies = sso_login()

        if args.lectureId == "all":
            courses = get_courses(cookies, semester=args.semester)
        else:
            r = requests.get(f"{API_ROOT}/courses/{args.lectureId}", cookies=cookies)
            r.raise_for_status()
            courses = [json.loads(r.text.removeprefix("while(1);"))]

        if not courses:
            logging.info("조건에 맞는 강의가 없습니다.")
            exit()

        logging.info(f"\n{len(courses)}개 강의 발견")
        logging.info(f"저장 경로: {args.outputDir.resolve()}\n")

        for course in courses:
            download_course(cookies, course, args.outputDir)

        logging.info(f"\n완료!")

    except KeyboardInterrupt:
        logging.info("\n\n중단되었습니다.")
        exit(1)
