# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
02. 하이브리드/비대면/온라인 강좌 검색 스크립트

01_fetch_courses.py로 수집한 JSON 파일에서
하이브리드, 비대면, 온라인 키워드가 포함된 강좌를 검색합니다.

Usage:
    uv run 02_find_remote.py [--file PATH] [--dept DEPT1,DEPT2,...] [--all]
    
Examples:
    uv run 02_find_remote.py
    uv run 02_find_remote.py --file output_2025_Fall.json
    uv run 02_find_remote.py --dept 컴퓨터공학부,수리과학부
    uv run 02_find_remote.py --all  # 모든 학과 표시
"""

import argparse
import json
from pathlib import Path


# 검색할 키워드
KEYWORDS = ["하이브리드", "비대면", "온라인"]

# 기본 필터링 학과 목록
DEFAULT_DEPARTMENTS = [
    "수리과학부",
    "컴퓨터공학부",
    "데이터사이언스학과",
]


def find_remote_courses(data: dict, departments: list[str] | None = None) -> list[dict]:
    """원격 수업 관련 강좌 검색"""
    results = []
    
    for course_key, course_data in data.items():
        r101 = course_data.get("r101")
        if r101 is None:
            continue
        
        # 전체 데이터를 문자열로 변환하여 키워드 검색
        course_str = str(course_data)
        matched_keywords = [kw for kw in KEYWORDS if kw in course_str]
        
        if not matched_keywords:
            continue
        
        # 강좌 기본 정보 추출
        info = r101.get("LISTTAB01", {})
        dept = info.get("departmentKorNm", "")
        
        # 학과 필터링 (departments가 None이면 모든 학과 표시)
        if departments is not None and dept not in departments:
            continue
        
        # 키워드 주변 컨텍스트 추출
        context = ""
        for kw in matched_keywords:
            pos = course_str.find(kw)
            if pos != -1:
                context = course_str[max(0, pos - 30) : pos + 30]
                break
        
        results.append({
            "code": course_key,
            "name": info.get("sbjtNm", ""),
            "professor": info.get("profNm", ""),
            "department": dept,
            "keywords": matched_keywords,
            "context": context,
        })
    
    return results


def print_results(results: list[dict], verbose: bool = False):
    """결과 출력"""
    if not results:
        print("검색 결과가 없습니다.")
        return
    
    print(f"\n{'='*80}")
    print(f"총 {len(results)}개 강좌 발견")
    print(f"{'='*80}\n")
    
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
            print(f"    키워드: {', '.join(c['keywords'])}")
            if verbose:
                print(f"    컨텍스트: ...{c['context']}...")
            print()


def main():
    parser = argparse.ArgumentParser(description="하이브리드/비대면/온라인 강좌 검색")
    parser.add_argument("--file", type=str, default="output_2026_Spring.json",
                        help="검색할 JSON 파일 (기본값: output_2026_Spring.json)")
    parser.add_argument("--dept", type=str, default=None,
                        help="필터링할 학과 (콤마로 구분, 예: 컴퓨터공학부,수리과학부)")
    parser.add_argument("--all", action="store_true",
                        help="모든 학과 표시 (필터링 없음)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="상세 출력 (컨텍스트 포함)")
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

    # 학과 필터 설정
    if args.all:
        departments = None
    elif args.dept:
        departments = [d.strip() for d in args.dept.split(",")]
    else:
        departments = DEFAULT_DEPARTMENTS
        print(f"기본 필터링 학과: {', '.join(departments)}")
        print("(모든 학과를 보려면 --all 옵션 사용)")

    # 검색 실행
    results = find_remote_courses(data, departments)
    print_results(results, args.verbose)


if __name__ == "__main__":
    main()

