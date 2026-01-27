import logging
import os
import re
import time

import dotenv
import telegram
from plyer import notification
from selenium.webdriver.common.keys import Keys
from seleniumbase import BaseCase

dotenv.load_dotenv(override=True)
# BaseCase.main(__name__, __file__)
# logging.basicConfig(filename="./log.txt", level=logging.DEBUG)

TARGET = ("과목명 1", "과목명 2")
bot = telegram.Bot(token=os.environ["TELEGRAM_TOKEN"])


def notify(*args, **kwargs):
    bot.send_message(chat_id=os.environ["TELEGRAM_CHAT_ID"], text=kwargs["message"])
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
            title="수강신청 취소여석",
            message="로그인 완료",
            app_icon=None,
            timeout=10,
        )
        P = []
        Q = []
        C = 0
        while 1:
            self.open("https://sugang.snu.ac.kr/sugang/cc/cc210.action")
            for element in self.find_elements("a.course-info-detail"):
                num = element.get_attribute("id").split("_")[-1]
                sbjtNm = self.get_element(f"input#sbjtNm_{num}").get_attribute("value")
                logging.info(num, sbjtNm)
                if sbjtNm in TARGET:
                    abc = self.get_element(
                        f"#course_info_detail_{num} > ul > li:nth-child(2) > span:nth-child(1) > em"
                    ).get_attribute("innerText")
                    m = re.match(r"(\d+)/(\d+) \((\d+)\)", abc)
                    a, b, c = int(m[1]), int(m[2]), int(m[3])
                    if a < b:
                        Q.append(sbjtNm)
                    if C == 0:
                        notify(title="", message=f"{sbjtNm} {a}/{b}({c})")
            for sbjtNm in TARGET:
                if (sbjtNm in Q) and (sbjtNm not in P):
                    notify(
                        title="취소여석+",
                        message=sbjtNm,
                        app_icon=None,
                        timeout=10,
                    )
                if (sbjtNm in P) and (sbjtNm not in Q):
                    notify(
                        title="취소여석-",
                        message=sbjtNm,
                        app_icon=None,
                        timeout=10,
                    )
            P = Q.copy()
            Q = []
            C = 1
            time.sleep(7)
