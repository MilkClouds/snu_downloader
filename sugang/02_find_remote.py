# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
02. 하이브리드/비대면/온라인 강좌 검색 스크립트

01_fetch_courses.py로 수집한 JSON 파일에서
하이브리드, 비대면, 온라인 키워드가 포함된 강좌를 검색합니다.

Usage:
    uv run 02_find_remote.py [--file PATH] [--subject KEYWORDS] [--dept KEYWORDS] [--all]

Examples:
    uv run 02_find_remote.py
    uv run 02_find_remote.py --file output_2025_Fall.json
    uv run 02_find_remote.py --subject 물리,컴퓨터,프로그래밍
    uv run 02_find_remote.py --dept 컴퓨터공학부,물리학과
    uv run 02_find_remote.py --all  # 모든 원격 강좌 표시
"""

import argparse
import json
from pathlib import Path

# 원격 수업 키워드
REMOTE_KEYWORDS = ["하이브리드", "비대면", "온라인"]

# 기본 과목명 검색 키워드
DEFAULT_SUBJECT_KEYWORDS = [
    "물리",
    "컴퓨터",
    "Computer",
    "Physics",
    "프로그래밍",
    "알고리즘",
    "자료구조",
    "운영체제",
    "소프트웨어",
    "코딩",
    "데이터",
    "인공지능",
    "머신러닝",
    "딥러닝",
    "정보과학",
]

# 기본 학과명 검색 키워드
DEFAULT_DEPT_KEYWORDS = ["물리", "컴퓨터", "전기·정보", "데이터사이언스"]


def find_remote_courses(
    data: dict,
    subject_keywords: list[str] | None = None,
    dept_keywords: list[str] | None = None,
) -> list[dict]:
    """원격 수업 관련 강좌 검색

    Args:
        data: 강좌 데이터
        subject_keywords: 과목명 검색 키워드 (None이면 필터링 안함)
        dept_keywords: 학과명 검색 키워드 (None이면 필터링 안함)

    Returns:
        검색된 강좌 목록
    """
    results = []

    for course_key, course_data in data.items():
        course_str = str(course_data)

        # 원격 수업 키워드 확인
        matched_remote = [kw for kw in REMOTE_KEYWORDS if kw in course_str]
        if not matched_remote:
            continue

        # 강좌 정보 추출
        r101 = course_data.get("r101", {})
        info = r101.get("LISTTAB01", {}) if r101 else {}
        name = info.get("sbjtNm", "")
        dept = info.get("departmentKorNm", "") or ""

        # 필터링 (subject_keywords와 dept_keywords 둘 다 None이면 모든 원격 강좌 표시)
        if subject_keywords is not None or dept_keywords is not None:
            matched_subject = []
            matched_dept = []

            if subject_keywords:
                matched_subject = [kw for kw in subject_keywords if kw.lower() in name.lower()]
            if dept_keywords:
                matched_dept = [kw for kw in dept_keywords if kw in dept]

            if not matched_subject and not matched_dept:
                continue

            matched_keywords = matched_subject + matched_dept
        else:
            matched_keywords = []

        results.append(
            {
                "code": course_key,
                "name": name,
                "professor": info.get("profNm", ""),
                "department": dept,
                "remote_keywords": matched_remote,
                "matched_keywords": matched_keywords,
            }
        )

    return results


def print_results(results: list[dict]):
    """결과 출력"""
    if not results:
        print("검색 결과가 없습니다.")
        return

    print(f"\n{'=' * 80}")
    print(f"총 {len(results)}개 강좌 발견")
    print(f"{'=' * 80}\n")

    # 학과별로 그룹화
    by_dept: dict[str, list] = {}
    for r in results:
        dept = r["department"] or "(학과 없음)"
        if dept not in by_dept:
            by_dept[dept] = []
        by_dept[dept].append(r)

    for dept, courses in sorted(by_dept.items()):
        print(f"\n[{dept}] - {len(courses)}개")
        print("-" * 60)
        for c in courses:
            print(f"  {c['code']}")
            print(f"    과목명: {c['name']}")
            print(f"    교수: {c['professor']}")
            print(f"    원격: {', '.join(c['remote_keywords'])}")
            if c["matched_keywords"]:
                print(f"    매칭: {', '.join(c['matched_keywords'])}")
            print()


def main():
    parser = argparse.ArgumentParser(description="하이브리드/비대면/온라인 강좌 검색")
    parser.add_argument(
        "--file",
        type=str,
        default="output_2026_Spring.json",
        help="검색할 JSON 파일 (기본값: output_2026_Spring.json)",
    )
    parser.add_argument(
        "--subject",
        type=str,
        default=None,
        help="과목명 검색 키워드 (콤마로 구분, 예: 물리,컴퓨터,프로그래밍)",
    )
    parser.add_argument(
        "--dept",
        type=str,
        default=None,
        help="학과명 검색 키워드 (콤마로 구분, 예: 컴퓨터공학부,물리학과)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="모든 원격 강좌 표시 (필터링 없음)",
    )
    args = parser.parse_args()

    # 파일 로드
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"파일을 찾을 수 없습니다: {file_path}")
        print("먼저 01_fetch_courses.py를 실행하여 데이터를 수집하세요.")
        return

    print(f"파일 로드 중: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"총 {len(data)}개 강좌 로드 완료")

    # 필터 설정
    if args.all:
        subject_keywords = None
        dept_keywords = None
        print("모든 원격 강좌를 검색합니다.")
    elif args.subject or args.dept:
        subject_keywords = [k.strip() for k in args.subject.split(",")] if args.subject else None
        dept_keywords = [k.strip() for k in args.dept.split(",")] if args.dept else None
        if subject_keywords:
            print(f"과목명 키워드: {', '.join(subject_keywords)}")
        if dept_keywords:
            print(f"학과명 키워드: {', '.join(dept_keywords)}")
    else:
        subject_keywords = DEFAULT_SUBJECT_KEYWORDS
        dept_keywords = DEFAULT_DEPT_KEYWORDS
        print(f"기본 과목명 키워드: {', '.join(subject_keywords)}")
        print(f"기본 학과명 키워드: {', '.join(dept_keywords)}")
        print("(모든 원격 강좌를 보려면 --all 옵션 사용)")

    # 검색 실행
    results = find_remote_courses(data, subject_keywords, dept_keywords)
    print_results(results)


if __name__ == "__main__":
    main()
