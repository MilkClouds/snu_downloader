
from seleniumbase import BaseCase
from selenium.webdriver.common.keys import Keys
from plyer import notification
import dotenv, time, os, re, logging, telegram
dotenv.load_dotenv(override = True)
# BaseCase.main(__name__, __file__)
# logging.basicConfig(filename="./log.txt", level=logging.DEBUG)

TARGET = ("과목명 1", "과목명 2")
bot = telegram.Bot(token = os.environ["TELEGRAM_TOKEN"])

def notify(*args, **kwargs):
    bot.send_message(chat_id = os.environ["TELEGRAM_CHAT_ID"], text = kwargs['message'])
    notification.notify(*args, **kwargs)

class RecorderTest(BaseCase):
    def test_recording(self):
        self.open("https://sugang.snu.ac.kr/sugang/cc/cc100InterfaceSrch.action")
        self.click('a[href="/sugang/co/co010.action"]')
        self.open_if_not_url("https://sugang.snu.ac.kr/sugang/co/co010.action")
        self.type("input#si_id", Keys.TAB)
        self.type("input#v_password", os.environ.get("password"))
        self.execute_script(f'document.CO010.si_id.value="{os.environ.get("username")}"')
        self.execute_script("fnSsoLogin()")
        time.sleep(1)
        notify(
                title = '수강신청 취소여석',
                message = '로그인 완료',
                app_icon = None,
                timeout = 10,
            )
        while 1:
            self.open("https://sugang.snu.ac.kr/sugang/cc/cc210.action")
            for element in self.find_elements('a.course-info-detail'):
                num = element.get_attribute("id").split("_")[-1]
                sbjtNm = self.get_element(f"input#sbjtNm_{num}").get_attribute('value')
                logging.info(num, sbjtNm)
                if sbjtNm in TARGET:
                    abc = self.get_element(f'#course_info_detail_{num} > ul > li:nth-child(2) > span:nth-child(1) > em').get_attribute('innerText')
                    m = re.match(r"(\d+)/(\d+) \((\d+)\)", abc)
                    a, b, c = m[1], m[2], m[3]
                    if a >= c:
                        notify(
                            title = '수강신청 취소여석',
                            message = sbjtNm,
                            app_icon = None,
                            timeout = 10,
                        )
            time.sleep(5)