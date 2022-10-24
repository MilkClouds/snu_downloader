import argparse
import platform
import asyncio
import getpass
import subprocess
from dotenv import load_dotenv
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from typing import Optional

load_dotenv(override = True)

root = "https://myetl.snu.ac.kr"
args = argparse.Namespace()

class PasswordPromptAction(argparse.Action):
    def __init__(self,
             option_strings,
             dest = None,
             nargs = 0,
             default = None,
             required = False,
             type = None,
             metavar = None,
             help = None):
        super(PasswordPromptAction, self).__init__(
             option_strings = option_strings,
             dest = dest,
             nargs = nargs,
             default = default,
             required = required,
             metavar = metavar,
             type = type,
             help = help)

    def __call__(self, parser, args, values, option_string = None):
        password = getpass.getpass()
        setattr(args, self.dest, password)

def yes_or_no(question):
    while "the answer is invalid":
        reply = str(input(question+' (y/n): ')).lower().strip()
        if len(reply) > 0:
            if reply[0] == 'y':
                return True
            if reply[0] == 'n':
                return False



async def file_download(contentUrl: str, fileName: Optional[str] = "out.mp4"):
    fileName = fileName.replace('/', '+')
    cmd = "wget.exe" if platform.system() == "Windows" else "wget"
    subprocess.run(f"{cmd} {contentUrl} --header \"Referer: https://lcms.snu.ac.kr\" -O \"{fileName}\"", cwd = args.dir, shell = True)

async def download_selenium():
    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(options = options)
    url = root + f"/courses/{args.lectureId}"
    driver.get(url)
    driver.find_element(By.ID, "si_id").send_keys(args.username)
    driver.find_element(By.ID, "si_pwd").send_keys(args.password)
    driver.find_element(By.CLASS_NAME, "btn_login").click()
    driver.get(url)
    driver.implicitly_wait(5)
    args.dir += driver.title
    Path(args.dir).mkdir(exist_ok = True)

    for href in [element.get_attribute("href") for element in driver.find_elements(By.CSS_SELECTOR, "div.module-item-title > span > a")]:
        if not href[-1].isnumeric():
            continue
        driver.get(href)
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        driver.switch_to.frame(iframes[1])
        driver.switch_to.frame(driver.find_element(By.TAG_NAME, "iframe"))

        contentId = driver.find_element(By.NAME, "thumbnail").get_attribute("content").split("/")[-1]
        contentUrl = f"https://snu-cms-object.cdn.ntruss.com/contents/snu0000001/{contentId}/contents/media_files/screen.mp4"

        await file_download(contentUrl, f"{driver.title}.mp4")

    driver.quit()

if __name__ == "__main__":
    
    print("==============================================================================================================================")
    print("DISCLAIMER: This program is not affiliated with SNU. Use at your own risk.")
    print("==============================================================================================================================")
    print("The information provided by SNU eTL Batch Downloader (\"we,\" \"us,\" or \"our\") on our application is for general\ninformational purposes only. All information on our application is provided in good faith, however we make no\nrepresentation or warranty of any kind, express or implied, regarding the accuracy, adequacy, validity, reliability,\navailability, or completeness of any information on our application. UNDER NO CIRCUMSTANCE SHALL WE HAVE ANY LIABILITY\nTO YOU FOR ANY LOSS OR DAMAGE OF ANY KIND INCURRED AS A RESULT OF THE USE OF OUR APPLICATION OR RELIANCE ON ANY\nINFORMATION PROVIDED ON OUR APPLICATION. YOUR USE OF OUR APPLICATION AND YOUR RELIANCE ON ANY INFORMATION ON OUR\nAPPLICATION IS SOLELY AT YOUR OWN RISK.")
    print("==============================================================================================================================")
    print("본 프로그램에 의해 제공된 모든 정보는 일반적인 목적으로만 사용할 수 있습니다. 이 프로그램의/으로 만들어진 모든 정보는 공익을\n위한 것이나, 개발자는 프로그램의 안정성, 적법성, 정확성, 정밀성, 의존성, 가용성, 완전성에 대하여 그 어떤 보증을 보장하지도,\n함의하지도 않습니다. 이러한 조건 하에 개발자는 이 프로그램의 사용이나 생성된 정보로 인한 그 어떤 피해나 행위에 관해서도 책임을\n지지 않습니다. 이 프로그램을 사용하는 것은 상기 내용에 동의하였으며, 프로그램의 사용으로 인한 책임은 전부 사용자에게 있습니다.")
    print("==============================================================================================================================")
    print("By using this program, you agree to the above terms.\nThis disclaimer can be found at https://github.com/milkclouds/snu_downloader/blob/main/README.md")
    print("==============================================================================================================================")
    
    if not yes_or_no("Do you agree with the terms above?"):
        exit()

    parser = argparse.ArgumentParser(description = "SNU eTL Batch Downloader")
    parser.add_argument("-d", dest = "dir", default = "./", type = str, help = "Directory to save files")
    parser.add_argument("-l", dest = "lectureId", type = str, required = True, help = "Lecture ID")
    parser.add_argument("-u", dest = "username", type = str, required = True, help = "SNU username")
    parser.add_argument("-p", dest = "password", action = PasswordPromptAction, type = str, required = True, help = "SNU password")
    args = parser.parse_args()

    if args.dir[-1] != '/':
        args.dir += '/'
    
    Path(args.dir).mkdir(exist_ok = True)
    asyncio.run(download_selenium())
