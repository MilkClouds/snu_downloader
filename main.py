import time
import selenium, threading, re, argparse, traceback, logging
import argparse, os, getpass, dotenv
import functools, pathlib, shutil, requests
from pathlib import Path
from threading import Lock
from selenium import webdriver
from selenium.webdriver.common.by import By
from tqdm.auto import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from concurrent.futures import ThreadPoolExecutor

from misc import yes_or_no, PasswordPromptAction, environ_or_required, download

class Lecture:
    def __init__(self, lectureId: str, driver: webdriver.Chrome, downloadPath: str):
        self.lectureId = lectureId
        self.lectureName = None
        self.downloadPath = downloadPath
        self.lectureFiles = []
        self.driver = driver
        self.hrefs = []
        self.valid = False
        try:
            self.driver.get(Downloader.webSiteRoot + f"/courses/{self.lectureId}")
            self.driver.implicitly_wait(5)
            self.downloadPath /= re.sub(r'[\\/:"*?<>|]+', '', self.driver.title)
            self.lectureName = self.driver.title

            Path(self.downloadPath).mkdir(parents=True, exist_ok=True)

            self.hrefs = [element.get_attribute("href") for element in self.driver.find_elements(By.CSS_SELECTOR, "div.module-item-title > span > a")]
            self.valid = True

        except Exception as e:
            print(e)
            logging.info(f"Failed to get lecture [ {self.lectureId} ]")

    def download_page(self, href: str):
        ret = []

        if not href[-1].isnumeric():
            return
        self.driver.get(href)
        self.driver.implicitly_wait(1)

        try:
            element = self.driver.find_element(By.CSS_SELECTOR, "#content > div:nth-child(2) > span > a")
            if element.get_attribute("download"):
                self.download_file(element.get_attribute("href"), element.get_attribute("innerText")[9:])
        except:
            pass

        try:
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            self.driver.switch_to.frame(iframes[1])
            self.driver.switch_to.frame(self.driver.find_element(By.TAG_NAME, "iframe"))
            contentId = self.driver.find_element(By.NAME, "thumbnail").get_attribute("content").split("/")[-1]
            contentUrl = f"https://snu-cms-object.cdn.ntruss.com/contents/snu0000001/{contentId}/contents/media_files/screen.mp4"
            self.download_file(contentUrl, f"{self.driver.title}.mp4")
        except:
            pass

    def download_all(self):
        logging.info("Downloading all files in lecture [ {} ]".format(self.lectureName))
        [self.download_page(href) for href in self.hrefs]

    def download_file(self, contentUrl: str, fileName: str):
        file = self.downloadPath / re.sub(r'[\\/:"*?<>|]+', '', fileName)
        if file.exists():
            logging.info(f"Skipping [ {file} ] since it already exists")
            return
        cookies = {cookie['name']: cookie['value'] for cookie in self.driver.get_cookies()}

        logging.info(f"Found [ {file} ]")

        future = Downloader.downloadExecutor.submit(download, contentUrl, file, headers={"Referer": "https://lcms.snu.ac.kr"}, cookies=cookies)
        Downloader.futures.append(future)


class Downloader:

    logging.basicConfig(level=logging.INFO, format='%(message)s')

    @classmethod
    def init(cls, outputDir: str, webSiteRoot: str, max_threads: int):
        cls.targetLectures = []
        cls.outputDir = outputDir
        cls.webSiteRoot = webSiteRoot
        cls.authenticated = False
        cls.completedDownloads = 0
        cls.totalDownloads = 0
        cls.downloadExecutor = ThreadPoolExecutor(max_workers=max_threads)
        cls.lectureExecutor = ThreadPoolExecutor(max_workers=1)
        cls.futures = []

        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        cls.driver = webdriver.Chrome(options = options)

    @classmethod
    def authenticate(cls, username, password) -> bool:
        cls.driver.get(cls.webSiteRoot)
        cls.driver.find_element(By.ID, "si_id").send_keys(username)
        cls.driver.find_element(By.ID, "si_pwd").send_keys(password)
        cls.driver.find_element(By.CLASS_NAME, "btn_login").click()

        cls.driver.get(cls.webSiteRoot)
        cls.driver.implicitly_wait(1)

        try:
            cls.driver.find_element(By.CLASS_NAME, "btn_login")
        except:
            logging.info("Successfully authenticated")
            cls.authenticated = True
            return True

        logging.info("Failed authentication")
        return False

    @classmethod
    def add_lecture(cls, lectureId) -> bool:
        if not cls.authenticated:
            logging.info("Not authenticated")
            return False
        if lectureId in cls.targetLectures:
            return False
        else:
            lecture = Lecture(lectureId, cls.driver, cls.outputDir)
            logging.info("Lecture [ {} ] added".format(lecture.lectureName))
            if lecture.valid:
                cls.targetLectures.append(lecture)
                return True
        return False
    
    @classmethod
    def download_all_lectures(cls):
        if not cls.authenticated:
            logging.info("Not authenticated")
        logging.info("Downloading all lectures")

        for lecture in cls.targetLectures:
            cls.lectureExecutor.submit(lecture.download_all)

        cls.lectureExecutor.shutdown(wait=True)
        cls.downloadExecutor.shutdown(wait=True)

    @classmethod
    def quit(cls):
        cls.driver.quit()


if __name__ == "__main__":
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
    parser.add_argument("-d", dest = "dir", default = ".", type = Path, help = "Directory to save files")
    parser.add_argument("-l", dest = "lectureId", type = str, help = "Lecture ID", **environ_or_required('lectureId'))
    parser.add_argument("-u", dest = "username", type = str, help = "SNU username", **environ_or_required('username'))
    parser.add_argument("-p", dest = "password", action = PasswordPromptAction, type = str, help = "SNU password", **environ_or_required('password'))
    args = parser.parse_args()


    try:
        Downloader.init(outputDir=args.dir, webSiteRoot="https://myetl.snu.ac.kr", max_threads=1)
        Downloader.authenticate(args.username, args.password)
        Downloader.add_lecture(args.lectureId)
        Downloader.download_all_lectures()
    except selenium.common.exceptions.WebDriverException:
        logging.info("[!] Download chromedriver https://chromedriver.chromium.org/downloads")
        traceback.print_exc()