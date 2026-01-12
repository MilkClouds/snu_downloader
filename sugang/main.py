# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "beautifulsoup4>=4.14.3",
#     "tqdm>=4.67.1",
#     "playwright>=1.49.0",
# ]
# ///
"""
SNU 수강신청 강좌 수집 스크립트 (Playwright 기반)

NetFunnel 대기열을 통과한 브라우저 컨텍스트에서
JavaScript로 병렬 fetch를 실행하여 빠르게 수집합니다.
"""

import json
import logging
import re
import time

from bs4 import BeautifulSoup as Soup
from playwright.sync_api import sync_playwright
from tqdm import tqdm

logging.basicConfig(level=logging.DEBUG, format="%(message)s", filename="log.txt", encoding="utf-8")

srchOpenSchyy = 2026
srchOpenShtms = dict(
    Spring="U000200001U000300001",
    # Summer= "U000200001U000300002",
    # Fall  = "U000200002U000300001",
    # Winter= "U000200002U000300002"
)

# 한 번에 처리할 병렬 요청 수
BATCH_SIZE = 10


def fetch_all_courses(srchOpenSchyy: int, srchOpenShtm: str) -> dict:
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
                login_btn = page.query_selector('button:has-text("로그인")')
                if login_btn:
                    break
            except Exception:
                pass
            time.sleep(1)

        print("NetFunnel 통과 완료!")

        # 1. 전체 페이지 수 확인
        search_data = f"workType=S&pageNo=1&srchOpenSchyy={srchOpenSchyy}&srchOpenShtm={srchOpenShtm}&srchSbjtNm=&srchSbjtCd=&seeMore=%EB%8D%94%EB%B3%B4%EA%B8%B0&srchCptnCorsFg=&srchOpenShyr=&srchOpenUpSbjtFldCd=&srchOpenSbjtFldCd=&srchOpenUpDeptCd=&srchOpenDeptCd=&srchOpenMjCd=&srchOpenSubmattCorsFg=&srchOpenSubmattFgCd1=&srchOpenSubmattFgCd2=&srchOpenSubmattFgCd3=&srchOpenSubmattFgCd4=&srchOpenSubmattFgCd5=&srchOpenSubmattFgCd6=&srchOpenSubmattFgCd7=&srchOpenSubmattFgCd8=&srchOpenSubmattFgCd9=&srchExcept=&srchOpenPntMin=&srchOpenPntMax=&srchCamp=&srchBdNo=&srchProfNm=&srchOpenSbjtTmNm=&srchOpenSbjtDayNm=&srchOpenSbjtTm=&srchOpenSbjtNm=&srchTlsnAplyCapaCntMin=&srchTlsnAplyCapaCntMax=&srchLsnProgType=&srchTlsnRcntMin=&srchTlsnRcntMax=&srchMrksGvMthd=&srchIsEngSbjt=&srchMrksApprMthdChgPosbYn=&srchIsPendingCourse=&srchGenrlRemoteLtYn=&srchLanguage=ko&srchCurrPage=1&srchPageSize=9999"

        first_page_html = page.evaluate(
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

        match = re.search(r'<a href="javascript:fnGotoPage\((\d+)\);" class="arrow last">', first_page_html)
        if not match:
            print("페이지 수 파싱 실패")
            print(first_page_html[:1000])
            browser.close()
            return result

        total_pages = int(match[1])
        print(f"총 {total_pages} 페이지 수집 시작...")

        # 2. 모든 페이지에서 강좌 코드 수집
        all_courses = []  # [(sbjtCd, ltNo), ...]

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
        for i in tqdm(range(0, len(all_courses), BATCH_SIZE), desc="상세정보 수집"):
            batch = all_courses[i : i + BATCH_SIZE]

            # JavaScript로 병렬 fetch 실행
            batch_data = [
                {
                    "key": course[0],
                    "sbjtCd": course[1],
                    "ltNo": course[2],
                }
                for course in batch
            ]

            batch_results = page.evaluate(
                """async (args) => {
                const {courses, srchOpenSchyy, srchOpenShtm} = args;
                const results = await Promise.all(courses.map(async (course) => {
                    const data = `workType=+&openSchyy=${srchOpenSchyy}&openShtmFg=${srchOpenShtm.slice(0,10)}&openDetaShtmFg=${srchOpenShtm.slice(10)}&sbjtCd=${course.sbjtCd}&ltNo=${course.ltNo}&sbjtSubhCd=000&t_profPersNo=`;

                    const [r101, r103] = await Promise.all([
                        fetch('https://sugang.snu.ac.kr/sugang/cc/cc101ajax.action', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                            body: data
                        }).then(r => r.json()).catch(() => null),
                        fetch('https://sugang.snu.ac.kr/sugang/cc/cc103ajax.action', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                            body: data
                        }).then(r => r.json()).catch(() => null)
                    ]);

                    return {key: course.key, r101, r103};
                }));
                return results;
            }""",
                {"courses": batch_data, "srchOpenSchyy": srchOpenSchyy, "srchOpenShtm": srchOpenShtm},
            )

            for item in batch_results:
                result[item["key"]] = {"r101": item["r101"], "r103": item["r103"]}

        browser.close()

    return result


def main():
    for sem, srchOpenShtm in srchOpenShtms.items():
        result = fetch_all_courses(srchOpenSchyy, srchOpenShtm)
        print(f"Fetched : {len(result)}")
        with open(f"output_{srchOpenSchyy}_{sem}.json", "w", encoding="utf-8") as file:
            json.dump(result, file, ensure_ascii=False)


if __name__ == "__main__":
    main()

    # ===================================
    for sem, srchOpenShtm in srchOpenShtms.items():
        with open(f"output_{srchOpenSchyy}_{sem}.json", "r", encoding="utf-8") as file:
            result = json.load(file)
        for i, j in result.items():
            if j["r101"] is None:  # 2022_Fall, 457.629A(001)
                print(i)
                continue
            # =====================================================
            # 정말 절평이 꿀강일까? 궁금해서 찾아본 기록
            # 역시 교바교..
            # if j['r101']["LISTTAB01"]['mrksRelevalYn'] != "YES":
            #     # if j['r101']['LISTTAB01']['departmentKorNm'] not in ('수리과학부', '컴퓨터공학부'):
            #     if j['r101']['LISTTAB01']['departmentKorNm'] not in ('컴퓨터공학부',):
            #         continue
            #     assert j['r101']["LISTTAB01"]['mrksRelevalYn'] == 'NO'
            #     print(f'{srchOpenSchyy}_{sem}', i, j['r101']['LISTTAB01']['sbjtNm'], j['r101']['LISTTAB01']['profNm'], j['r101']['LISTTAB01']['departmentKorNm'], sep=' / ')
            # =====================================================
            if "하이브리드" in str(j) or "비대면" in str(j) or "온라인" in str(j):
                if j["r101"]["LISTTAB01"]["departmentKorNm"] not in (
                    "수리과학부",
                    "컴퓨터공학부",
                    "데이터사이언스학과",
                ):
                    continue
                pos = max((str(j).find("하이브리드"), str(j).find("비대면"), str(j).find("온라인")))
                print(
                    i,
                    j["r101"]["LISTTAB01"]["sbjtNm"],
                    j["r101"]["LISTTAB01"]["profNm"],
                    j["r101"]["LISTTAB01"]["departmentKorNm"],
                    sep=" / ",
                )
                print(str(j)[pos - 30 : pos + 30])
