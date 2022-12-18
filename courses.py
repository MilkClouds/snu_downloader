from seleniumbase import SB
from selenium.webdriver.common.by import By
import dotenv, os, logging
dotenv.load_dotenv(override = True)

def get_lectures():
    logging.info("Fetching lecture list...")
    with SB(headless=True) as sb:
        sb.open("https://myetl.snu.ac.kr")
        sb.type("input#login_id", os.environ.get("username"))
        sb.type("input#login_pwd", os.environ.get("password"))
        sb.click('input[value="로그인"]')
        sb.open("https://myetl.snu.ac.kr/courses")
        trs = sb.find_elements("#my_courses_table > tbody > tr")
        lectures = [tr.find_element(By.CSS_SELECTOR, 'a').get_attribute('href').split("/")[-1] for tr in trs]
        logging.info(f"Fetched lectures: {lectures}")
        return lectures

if __name__ == "__main__":
    print(get_lectures())
