# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "beautifulsoup4>=4.14.3",
#     "tqdm>=4.67.1",
#     "playwright>=1.49.0",
# ]
# ///
"""
01. SNU 수강신청 강좌 수집 스크립트

NetFunnel 대기열을 통과한 브라우저 컨텍스트에서
JavaScript로 병렬 fetch를 실행하여 빠르게 수집합니다.

Usage:
    uv run 01_fetch_courses.py [--batch-size N] [--year YYYY] [--semester NAME]

Examples:
    uv run 01_fetch_courses.py
    uv run 01_fetch_courses.py --batch-size 5
    uv run 01_fetch_courses.py --year 2025 --semester Fall
"""

import argparse
import json
import logging
import re
import time

from bs4 import BeautifulSoup as Soup
from playwright.sync_api import sync_playwright
from tqdm import tqdm

logging.basicConfig(level=logging.DEBUG, format="%(message)s", filename="log.txt", encoding="utf-8")

# 학기 코드 매핑
SEMESTER_CODES = {
    "Spring": "U000200001U000300001",
    "Summer": "U000200001U000300002",
    "Fall": "U000200002U000300001",
    "Winter": "U000200002U000300002",
}


def fetch_all_courses(year: int, semester_code: str, batch_size: int = 10) -> dict:
    """Playwright를 사용하여 모든 강좌 수집"""
    result = {}

    print("NetFunnel 대기열 통과 중... (브라우저 자동 실행)")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://sugang.snu.ac.kr")

        # NetFunnel 통과 대기 (최대 120초)
        for _ in range(120):
            try:
                if page.query_selector('button:has-text("로그인")'):
                    break
            except Exception:
                pass
            time.sleep(1)

        print("NetFunnel 통과 완료!")

        # 1. 전체 페이지 수 확인
        search_data = f"workType=S&pageNo=1&srchOpenSchyy={year}&srchOpenShtm={semester_code}&srchSbjtNm=&srchSbjtCd=&seeMore=%EB%8D%94%EB%B3%B4%EA%B8%B0&srchCptnCorsFg=&srchOpenShyr=&srchOpenUpSbjtFldCd=&srchOpenSbjtFldCd=&srchOpenUpDeptCd=&srchOpenDeptCd=&srchOpenMjCd=&srchOpenSubmattCorsFg=&srchOpenSubmattFgCd1=&srchOpenSubmattFgCd2=&srchOpenSubmattFgCd3=&srchOpenSubmattFgCd4=&srchOpenSubmattFgCd5=&srchOpenSubmattFgCd6=&srchOpenSubmattFgCd7=&srchOpenSubmattFgCd8=&srchOpenSubmattFgCd9=&srchExcept=&srchOpenPntMin=&srchOpenPntMax=&srchCamp=&srchBdNo=&srchProfNm=&srchOpenSbjtTmNm=&srchOpenSbjtDayNm=&srchOpenSbjtTm=&srchOpenSbjtNm=&srchTlsnAplyCapaCntMin=&srchTlsnAplyCapaCntMax=&srchLsnProgType=&srchTlsnRcntMin=&srchTlsnRcntMax=&srchMrksGvMthd=&srchIsEngSbjt=&srchMrksApprMthdChgPosbYn=&srchIsPendingCourse=&srchGenrlRemoteLtYn=&srchLanguage=ko&srchCurrPage=1&srchPageSize=9999"

        first_html = page.evaluate(
            """async (data) => {
            const res = await fetch('https://sugang.snu.ac.kr/sugang/cc/cc100InterfaceSrch.action', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: data
            });
            return await res.text();
        }""",
            search_data,
        )

        match = re.search(r'<a href="javascript:fnGotoPage\((\d+)\);" class="arrow last">', first_html)
        if not match:
            print("페이지 수 파싱 실패")
            print(first_html[:1000])
            browser.close()
            return result

        total_pages = int(match[1])
        print(f"총 {total_pages} 페이지 수집 시작...")

        # 2. 모든 페이지에서 강좌 코드 수집
        all_courses = []

        for page_no in tqdm(range(1, total_pages + 1), desc="페이지 수집"):
            page_data = search_data.replace("pageNo=1", f"pageNo={page_no}")
            html = page.evaluate(
                """async (data) => {
                const res = await fetch('https://sugang.snu.ac.kr/sugang/cc/cc100InterfaceSrch.action', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                    body: data
                });
                return await res.text();
            }""",
                page_data,
            )

            soup = Soup(html, "html.parser")
            for element in soup.select("a.course-info-detail"):
                try:
                    span = element.select("ul > li:nth-child(1) > span:nth-child(3)")[0]
                    m = re.match(r"(.*?)\((\d+)\)", span.text)
                    if m:
                        all_courses.append((span.text, m[1], m[2]))
                except Exception:
                    continue

        print(f"총 {len(all_courses)}개 강좌 코드 수집 완료")

        # 3. 각 강좌의 상세정보 수집 (배치 처리)
        for i in tqdm(range(0, len(all_courses), batch_size), desc="상세정보 수집"):
            batch = all_courses[i : i + batch_size]
            batch_data = [{"key": c[0], "sbjtCd": c[1], "ltNo": c[2]} for c in batch]

            batch_results = page.evaluate(
                """async (args) => {
                const {courses, year, semCode} = args;
                return Promise.all(courses.map(async (c) => {
                    const data = `workType=+&openSchyy=${year}&openShtmFg=${semCode.slice(0,10)}&openDetaShtmFg=${semCode.slice(10)}&sbjtCd=${c.sbjtCd}&ltNo=${c.ltNo}&sbjtSubhCd=000&t_profPersNo=`;
                    const [r101, r103] = await Promise.all([
                        fetch('https://sugang.snu.ac.kr/sugang/cc/cc101ajax.action', {
                            method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'}, body: data
                        }).then(r => r.json()).catch(() => null),
                        fetch('https://sugang.snu.ac.kr/sugang/cc/cc103ajax.action', {
                            method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'}, body: data
                        }).then(r => r.json()).catch(() => null)
                    ]);
                    return {key: c.key, r101, r103};
                }));
            }""",
                {"courses": batch_data, "year": year, "semCode": semester_code},
            )

            for item in batch_results:
                result[item["key"]] = {"r101": item["r101"], "r103": item["r103"]}

        browser.close()

    return result


def main():
    parser = argparse.ArgumentParser(description="SNU 수강신청 강좌 수집")
    parser.add_argument("--batch-size", type=int, default=10, help="병렬 요청 배치 크기 (기본값: 10)")
    parser.add_argument("--year", type=int, default=2026, help="학년도 (기본값: 2026)")
    parser.add_argument(
        "--semester",
        type=str,
        default="Spring",
        choices=["Spring", "Summer", "Fall", "Winter"],
        help="학기 (기본값: Spring)",
    )
    args = parser.parse_args()

    sem_code = SEMESTER_CODES[args.semester]
    result = fetch_all_courses(args.year, sem_code, args.batch_size)
    print(f"Fetched: {len(result)} courses")

    output_file = f"output_{args.year}_{args.semester}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"Saved to {output_file}")


if __name__ == "__main__":
    main()
