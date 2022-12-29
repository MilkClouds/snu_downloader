import selenium, re, argparse, traceback, logging, argparse, yt_dlp
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import List

from misc import yes_or_no, PasswordPromptAction, environ_or_required, download

class Lecture:
    urlRoot: str = "https://myetl.snu.ac.kr"
    cookies: List[dict] = None

    def __init__(self, lectureId: str, args):
        self.lectureId = lectureId
        self.lectureName = None
        self.lectureFiles = []

        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        self.driver = webdriver.Chrome(options = options)
        self.driver.implicitly_wait(5)

        if Lecture.cookies is None:
            self.driver.get(Lecture.urlRoot)
            element = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input#login_id"))
            )

            self.driver.find_element(By.CSS_SELECTOR, "input#login_id").send_keys(args.username)
            self.driver.find_element(By.CSS_SELECTOR, "input#login_pwd").send_keys(args.password)
            self.driver.find_element(By.CSS_SELECTOR, 'input[onclick="loginProc();"]').click()

            element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#header > div.ic-app-header__main-navigation > div > a"))
            )
            Lecture.cookies = self.driver.get_cookies()
        else:
            # '/123': to bypass domain settings in cookie
            self.driver.get(Lecture.urlRoot + '/123')
            for cookie in Lecture.cookies:
                self.driver.add_cookie(cookie)

        self.hrefs = []
        try:
            self.driver.get(Lecture.urlRoot + f"/courses/{self.lectureId}/modules")
            self.lectureName = re.sub(r'[\\/:"*?<>|]+', '', self.driver.find_element(By.CSS_SELECTOR, "#breadcrumbs > ul > li:nth-child(2) > a > span").get_attribute("innerText"))
            self.downloadPath = args.outputDir / self.lectureName

            Path(self.downloadPath).mkdir(parents=True, exist_ok=True)

            self.hrefs = [element.get_attribute("href") for element in self.driver.find_elements(By.CSS_SELECTOR, "div.module-item-title > span > a")]
            logging.info("Lecture [ {} ] added".format(self.lectureName))

        except Exception:
            traceback.print_exc()
            logging.info(f"Failed to get lecture [ {self.lectureId} ]")

    def download_page(self, href: str):
        if not href[-1].isnumeric():
            return
        self.driver.get(href)
        self.driver.implicitly_wait(1)
        cookies = {cookie['name']: cookie['value'] for cookie in self.driver.get_cookies()}

        try:
            element = self.driver.find_element(By.CSS_SELECTOR, "#content > div:nth-child(2) > span > a")
            if element.get_attribute("download"):
                # file download
                Downloader.downloadExecutor.submit(self.file_download, element.get_attribute("href"), element.get_attribute("innerText")[9:], cookies)
        except:
            pass

        try:
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            self.driver.switch_to.frame(iframes[1])
            self.driver.switch_to.frame(self.driver.find_element(By.TAG_NAME, "iframe"))
            src = self.driver.page_source
            if "onYouTubeIframeAPIReady" in src:
                id = re.search("videoId: '(.+?)'", src)[1]
                Downloader.downloadExecutor.submit(self.yt_download, id)
                return
            contentId = self.driver.find_element(By.NAME, "thumbnail").get_attribute("content").split("/")[-1]
            contentUrl = f"https://snu-cms-object.cdn.ntruss.com/contents/snu0000001/{contentId}/contents/media_files/screen.mp4"
            Downloader.downloadExecutor.submit(self.file_download, contentUrl, f"{self.driver.title}.mp4", cookies)
        except:
            pass

    def download_all(self):
        if len(self.hrefs) == 0:
            return
        logging.info("Downloading all files in lecture [ {} ]".format(self.lectureName))
        [self.download_page(href) for href in self.hrefs]

    def file_download(self, contentUrl: str, fileName: str, cookies: dict):
        file = self.downloadPath / re.sub(r'[\\/:"*?<>|]+', '', fileName)
        if file.exists():
            logging.info(f"Skipping [ {file} ] since it already exists")
            return
        logging.info(f"Downloading [ {file.name} ]")
        download(contentUrl, file, headers={"Referer": "https://lcms.snu.ac.kr"}, cookies=cookies)

    def yt_download(self, id: int):
        # resize concurrent-fragments if necessary
        ydl_opts = {"concurrent-fragments": 4, "paths": str(self.downloadPath)}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download(id)


class Downloader:
    LECTURE_MAX_THREADS = 1
    DOWNLOAD_MAX_THREADS = 1

    targetLectures = []
    downloadExecutor = ThreadPoolExecutor(max_workers=DOWNLOAD_MAX_THREADS)
    lectureExecutor = ThreadPoolExecutor(max_workers=LECTURE_MAX_THREADS)

    args = SimpleNamespace(**{})

    @classmethod
    def add_lecture(cls, lectureId) -> bool:
        lecture = Lecture(lectureId, cls.args)
        cls.targetLectures.append(lecture)
        return lecture
    
    @classmethod
    def add_lectures(cls, lectureIds):
        if len(lectureIds) == 0:
            return
        # evaluate 0th first to get cookie
        cls.lectureExecutor.submit(cls.add_lecture, lectureIds[0]).result()
        [*cls.lectureExecutor.map(cls.add_lecture, lectureIds[1:])]
    
    @classmethod
    def download_all_lectures(cls):
        logging.info("Downloading all lectures")

        for lecture in cls.targetLectures:
            cls.lectureExecutor.submit(lecture.download_all)

        cls.lectureExecutor.shutdown(wait=True)
        cls.downloadExecutor.shutdown(wait=True)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    logging.info("==============================================================================================================================")
    logging.info("DISCLAIMER: This program is not affiliated with SNU. Use at your own risk.")
    logging.info("==============================================================================================================================")
    logging.info("The information provided by SNU eTL Batch Downloader (\"we,\" \"us,\" or \"our\") on our application is for general\ninformational purposes only. All information on our application is provided in good faith, however we make no\nrepresentation or warranty of any kind, express or implied, regarding the accuracy, adequacy, validity, reliability,\navailability, or completeness of any information on our application. UNDER NO CIRCUMSTANCE SHALL WE HAVE ANY LIABILITY\nTO YOU FOR ANY LOSS OR DAMAGE OF ANY KIND INCURRED AS A RESULT OF THE USE OF OUR APPLICATION OR RELIANCE ON ANY\nINFORMATION PROVIDED ON OUR APPLICATION. YOUR USE OF OUR APPLICATION AND YOUR RELIANCE ON ANY INFORMATION ON OUR\nAPPLICATION IS SOLELY AT YOUR OWN RISK.")
    logging.info("==============================================================================================================================")
    logging.info("본 프로그램에 의해 제공된 모든 정보는 일반적인 목적으로만 사용할 수 있습니다. 이 프로그램의/으로 만들어진 모든 정보는 공익을\n위한 것이나, 개발자는 프로그램의 안정성, 적법성, 정확성, 정밀성, 의존성, 가용성, 완전성에 대하여 그 어떤 보증을 보장하지도,\n함의하지도 않습니다. 이러한 조건 하에 개발자는 이 프로그램의 사용이나 생성된 정보로 인한 그 어떤 피해나 행위에 관해서도 책임을\n지지 않습니다. 이 프로그램을 사용하는 것은 상기 내용에 동의하였으며, 프로그램의 사용으로 인한 책임은 전부 사용자에게 있습니다.")
    logging.info("==============================================================================================================================")
    logging.info("By using this program, you agree to the above terms.\nThis disclaimer can be found at RETRACTED")
    logging.info("==============================================================================================================================")
    
    if not yes_or_no("Do you agree with the terms above?"):
        exit()

    parser = argparse.ArgumentParser(description = "SNU eTL Batch Downloader")
    parser.add_argument("-d", dest = "outputDir", default = ".", type = Path, help = "Directory to save files")
    parser.add_argument("-l", dest = "lectureId", type = str, help = "Lecture ID", **environ_or_required('lectureId'))
    parser.add_argument("-u", dest = "username", type = str, help = "SNU username", **environ_or_required('username'))
    parser.add_argument("-p", dest = "password", action = PasswordPromptAction, type = str, help = "SNU password", **environ_or_required('password'))
    args = parser.parse_args()

    try:
        Downloader.args = args
        if args.lectureId.isnumeric():
            Downloader.add_lecture(args.lectureId)
        elif args.lectureId == 'all':
            from courses import get_lectures
            Downloader.add_lectures(get_lectures(args.username, args.password))
        Downloader.download_all_lectures()
    except selenium.common.exceptions.WebDriverException:
        logging.info("[!] Download chromedriver https://chromedriver.chromium.org/downloads")
        traceback.print_exc()