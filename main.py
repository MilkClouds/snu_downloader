from typing import Optional
import aiohttp, asyncio, re, logging, os, subprocess
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(override=True)

root = "https://myetl.snu.ac.kr"
cookies = os.environ['cookies']
cookies = {i.split("=")[0] : i.split("=")[1] for i in cookies.split("; ")}

output_dir = "전기전자회로 (2022_80_CTL_2020_1_HSH_2022_1)"

# async def request(url: str, session: aiohttp.ClientSession):
#     logging.info(f"Fetching {url}")
#     async with session.get(root + url) as response:
#         return await response.text()
# async def download(url: str):
#     async with aiohttp.ClientSession(cookies=cookies) as session:
#         soup = BeautifulSoup(await request(url, session), 'html.parser')
#         ret = await asyncio.gather(*[request(i['href'], session) for i in soup.select("div.module-item-title > span > a") if i['href'][-1].isnumeric()])
#         for i in ret:
#             result = re.search('(".*?screen.mp4)', i)
#             with open("out.html", 'w', encoding='utf-8') as file:
#                 file.write(i)
#             return
#             # print(result)

async def file_download(url: str, name: Optional[str] = "out.mp4"):
    name = name.replace("/", "+")
    subprocess.run(f'wget.exe {url} --header "Referer: https://lcms.snu.ac.kr" -O "{name}"', cwd=output_dir, shell=True)
async def download_selenium(url: str):
    options = webdriver.ChromeOptions()
    # options.add_argument('--headless')
    driver = webdriver.Chrome(options=options)
    driver.get(root + url)
    driver.find_element(By.ID, "si_id").send_keys(os.environ["id"])
    driver.find_element(By.ID, "si_pwd").send_keys(os.environ["pw"])
    driver.find_element(By.CLASS_NAME, "btn_login").click()
    # driver.add_cookie(cookies)
    driver.get(root + url)
    driver.implicitly_wait(5)
    for href in [element.get_attribute('href') for element in driver.find_elements(By.CSS_SELECTOR, "div.module-item-title > span > a")]:
        if not href[-1].isnumeric():
            continue
        driver.get(href)
        # wait = WebDriverWait(driver, 10)
        # element = wait.until(EC.element_to_be_clickable((By.NAME, "tool_content")))
        iframes = driver.find_elements(By.TAG_NAME, 'iframe')
        driver.switch_to.frame(iframes[1])
        driver.switch_to.frame(driver.find_element(By.TAG_NAME, 'iframe'))

        num = driver.find_element(By.NAME, "thumbnail").get_attribute("content").split("/")[-1]
        # no parallelism
        await file_download(f"https://snu-cms-object.cdn.ntruss.com/contents/snu0000001/{num}/contents/media_files/screen.mp4", f"{driver.title}.mp4")

        # element = driver.find_element(By.CSS_SELECTOR, "#front-screen > div > div.vc-front-screen-btn-container > div.vc-front-screen-btn-wrapper.video1-btn > div")
        # element.click()
        # driver.switch_to.default_content()
    driver.quit()

if __name__ == "__main__":
    # asyncio.run(download("/courses/234648"))
    Path(output_dir).mkdir(exist_ok=True)
    asyncio.run(download_selenium("/courses/234648"))