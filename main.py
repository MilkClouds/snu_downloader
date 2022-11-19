import selenium, re, argparse, traceback, logging, yt_dlp
from multiprocessing.dummy import Pool
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from misc import yes_or_no, PasswordPromptAction, environ_or_required, download

root = "https://myetl.snu.ac.kr"
# Limited to maximum 1 thread once. Modify at **your own risk.**
MAX_THREADS = 1
logging.basicConfig(level=logging.INFO, format='%(message)s')

def file_download(contentUrl: str, fileName: str, driver: webdriver.Chrome, cookies: dict):
    file = args.dir / re.sub(r'[\\/:"*?<>|]+', '', fileName)
    if file.exists():
        logging.info(f"Skipping [ {file} ] since it already exists")
        return
    logging.info(f"Downloading [ {file.name} ]")
    download(contentUrl, file, headers={"Referer": "https://lcms.snu.ac.kr"}, cookies=cookies)

def yt_download(id: int):
    # resize concurrent-fragments if necessary
    ydl_opts = {"concurrent-fragments": 4, "paths": str(args.dir)}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download(id)

def download_page(driver: webdriver.Chrome, href):
    if not href[-1].isnumeric():
        return
    driver.get(href)
    driver.implicitly_wait(1)
    cookies = {cookie['name']: cookie['value'] for cookie in driver.get_cookies()}
    try:
        element = driver.find_element(By.CSS_SELECTOR, "#content > div:nth-child(2) > span > a")
        if element.get_attribute("download"):
            pool.apply_async(file_download, args=(element.get_attribute("href"), element.get_attribute("innerText")[9:], driver, cookies))
    except:
        pass

    try:
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        driver.switch_to.frame(iframes[1])
        driver.switch_to.frame(driver.find_element(By.TAG_NAME, "iframe"))
        src = driver.page_source
        if "onYouTubeIframeAPIReady" in src:
            id = re.search("videoId: '(.+?)'", src)[1]
            pool.apply_async(yt_download, args=(id, ))
            return
        contentId = driver.find_element(By.NAME, "thumbnail").get_attribute("content").split("/")[-1]
        contentUrl = f"https://snu-cms-object.cdn.ntruss.com/contents/snu0000001/{contentId}/contents/media_files/screen.mp4"
        pool.apply_async(file_download, args=(contentUrl, f"{driver.title}.mp4", driver, cookies))
    except:
        pass

def main():
    options = webdriver.ChromeOptions()
    # disable this if necessary (for debugging purposes)
    options.add_argument('--headless')
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    driver = webdriver.Chrome(options = options)
    url = root + f"/courses/{args.lectureId}/modules"
    driver.get(url)
    driver.find_element(By.ID, "si_id").send_keys(args.username)
    driver.find_element(By.ID, "si_pwd").send_keys(args.password)
    driver.find_element(By.CLASS_NAME, "btn_login").click()
    driver.get(url)
    driver.implicitly_wait(5)
    args.dir /= re.sub(r'[\\/:"*?<>|]+', '', driver.find_element(By.CSS_SELECTOR, "#breadcrumbs > ul > li:nth-child(2) > a > span").get_attribute("innerText"))
    Path(args.dir).mkdir(parents=True, exist_ok=True)

    hrefs = [element.get_attribute("href") for element in driver.find_elements(By.CSS_SELECTOR, "div.module-item-title > span > a")]
    [download_page(driver, href) for href in hrefs]

    driver.quit()

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
        with Pool(MAX_THREADS) as pool:
            main()
            pool.close()
            pool.join()
    except selenium.common.exceptions.WebDriverException:
        logging.info("[!] Download chromedriver https://chromedriver.chromium.org/downloads")
        traceback.print_exc()