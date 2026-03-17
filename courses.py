import logging

from selenium.webdriver.common.by import By
from seleniumbase import SB


def wait_for_etl_login(sb, timeout=120):
    """Open eTL and wait for the user to complete SSO login (including MFA)."""
    sb.open("https://myetl.snu.ac.kr")
    logging.info("브라우저에서 SSO 로그인을 완료해주세요 (MFA 포함)...")
    for _ in range(timeout):
        sb.sleep(1)
        try:
            # Dismiss any unexpected alerts
            alert = sb.driver.switch_to.alert
            alert.accept()
            continue
        except Exception:
            pass
        try:
            url = sb.get_current_url()
            if "myetl.snu.ac.kr" in url and "nsso" not in url:
                logging.info("로그인 성공!")
                return
        except Exception:
            pass
    raise TimeoutError("로그인 시간 초과 (2분)")


def get_lectures(semester: str = None):
    logging.info("Fetching lecture list...")
    with SB(headless=False) as sb:
        wait_for_etl_login(sb)
        sb.open("https://myetl.snu.ac.kr/courses")
        sb.sleep(3)
        trs = sb.find_elements("#my_courses_table > tbody > tr")
        lectures = []
        for tr in trs:
            try:
                row_text = tr.text
                if semester and semester not in row_text:
                    continue
                lectures.append(tr.find_element(By.CSS_SELECTOR, "a").get_attribute("href").split("/")[-1])
            except Exception:
                pass
        cookies = sb.driver.get_cookies()
        logging.info(f"Fetched lectures (semester={semester}): {lectures}")
        return lectures, cookies


if __name__ == "__main__":
    print(get_lectures())
