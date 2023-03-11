import sys, logging, re, json, asyncio, aiohttp
from bs4 import BeautifulSoup as Soup
from tqdm.asyncio import tqdm

logging.basicConfig(level=logging.DEBUG, format='%(message)s', filename="log.txt", encoding="utf-8")

sem = asyncio.Semaphore(6)
srchOpenSchyy = 2023
srchOpenShtms = dict(
        Spring= "U000200001U000300001",
        # Summer= "U000200001U000300002",
        # Fall  = "U000200002U000300001",
        # Winter= "U000200002U000300002"
        )

async def async_range(count):
    for i in range(count):
        yield(i)
        await asyncio.sleep(0.0)

async def _fetch(page: int, srchOpenSchyy: int, srchOpenShtm: str):
    result = {}
    url = "https://sugang.snu.ac.kr/sugang/cc/cc100InterfaceSrch.action"
    data = f"workType=S&pageNo={page + 1}&srchOpenSchyy={srchOpenSchyy}&srchOpenShtm={srchOpenShtm}&srchSbjtNm=&srchSbjtCd=&seeMore=%EB%8D%94%EB%B3%B4%EA%B8%B0&srchCptnCorsFg=&srchOpenShyr=&srchOpenUpSbjtFldCd=&srchOpenSbjtFldCd=&srchOpenUpDeptCd=&srchOpenDeptCd=&srchOpenMjCd=&srchOpenSubmattCorsFg=&srchOpenSubmattFgCd1=&srchOpenSubmattFgCd2=&srchOpenSubmattFgCd3=&srchOpenSubmattFgCd4=&srchOpenSubmattFgCd5=&srchOpenSubmattFgCd6=&srchOpenSubmattFgCd7=&srchOpenSubmattFgCd8=&srchOpenSubmattFgCd9=&srchExcept=&srchOpenPntMin=&srchOpenPntMax=&srchCamp=&srchBdNo=&srchProfNm=&srchOpenSbjtTmNm=&srchOpenSbjtDayNm=&srchOpenSbjtTm=&srchOpenSbjtNm=&srchTlsnAplyCapaCntMin=&srchTlsnAplyCapaCntMax=&srchLsnProgType=&srchTlsnRcntMin=&srchTlsnRcntMax=&srchMrksGvMthd=&srchIsEngSbjt=&srchMrksApprMthdChgPosbYn=&srchIsPendingCourse=&srchGenrlRemoteLtYn=&srchLanguage=ko&srchCurrPage=1&srchPageSize=9999"
    data = {i.split("=")[0]: i.split("=")[1] for i in data.split("&")}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as res:
            assert res.status == 200
            txt = await res.text()
        soup = Soup(txt, 'html.parser')
        # logging.debug(soup)
        for element in soup.select("a.course-info-detail"):
            element = element.select("ul > li:nth-child(1) > span:nth-child(3)")[0]
            r = re.match("(.*?)\((\d+)\)", element.text)
            sbjtCd, ltNo = r[1], r[2]
            data = f"workType=+&openSchyy={srchOpenSchyy}&openShtmFg={srchOpenShtm[:10]}&openDetaShtmFg={srchOpenShtm[10:]}&sbjtCd=M3500.001500&ltNo=001&sbjtSubhCd=000&t_profPersNo="
            data = {i.split("=")[0]: i.split("=")[1] for i in data.split("&")}
            data.update(dict(sbjtCd=sbjtCd, ltNo=ltNo))
            async with session.post("https://sugang.snu.ac.kr/sugang/cc/cc101ajax.action", data=data) as res:
                r101 = await res.json(content_type=None)
            async with session.post("https://sugang.snu.ac.kr/sugang/cc/cc103ajax.action", data=data) as res:
                r103 = await res.json(content_type=None)
            result[element.text] = dict(r101=r101, r103=r103)
            # logging.debug(element.text)
    logging.info(len(result))
    return result

async def safe_fetch(*args, **kwargs):
    async with sem:
        return await _fetch(*args, **kwargs)

async def fetch(srchOpenSchyy: int, srchOpenShtm: str):
    result = {}
    url = "https://sugang.snu.ac.kr/sugang/cc/cc100InterfaceSrch.action"
    data = f"workType=S&pageNo=1&srchOpenSchyy={srchOpenSchyy}&srchOpenShtm={srchOpenShtm}&srchSbjtNm=&srchSbjtCd=&seeMore=%EB%8D%94%EB%B3%B4%EA%B8%B0&srchCptnCorsFg=&srchOpenShyr=&srchOpenUpSbjtFldCd=&srchOpenSbjtFldCd=&srchOpenUpDeptCd=&srchOpenDeptCd=&srchOpenMjCd=&srchOpenSubmattCorsFg=&srchOpenSubmattFgCd1=&srchOpenSubmattFgCd2=&srchOpenSubmattFgCd3=&srchOpenSubmattFgCd4=&srchOpenSubmattFgCd5=&srchOpenSubmattFgCd6=&srchOpenSubmattFgCd7=&srchOpenSubmattFgCd8=&srchOpenSubmattFgCd9=&srchExcept=&srchOpenPntMin=&srchOpenPntMax=&srchCamp=&srchBdNo=&srchProfNm=&srchOpenSbjtTmNm=&srchOpenSbjtDayNm=&srchOpenSbjtTm=&srchOpenSbjtNm=&srchTlsnAplyCapaCntMin=&srchTlsnAplyCapaCntMax=&srchLsnProgType=&srchTlsnRcntMin=&srchTlsnRcntMax=&srchMrksGvMthd=&srchIsEngSbjt=&srchMrksApprMthdChgPosbYn=&srchIsPendingCourse=&srchGenrlRemoteLtYn=&srchLanguage=ko&srchCurrPage=1&srchPageSize=9999"
    data = {i.split("=")[0]: i.split("=")[1] for i in data.split("&")}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as res:
            assert res.status == 200
            txt = await res.text()
            pages = int(re.search('<a href="javascript:fnGotoPage\((\d+)\);" class="arrow last">', txt)[1])
    for res in await tqdm.gather(*[safe_fetch(page, srchOpenSchyy, srchOpenShtm) for page in range(pages)]):
        result.update(res)
    # async for page in tqdm(range(pages)):
    #     res = await _fetch(page, srchOpenSchyy, srchOpenShtm)
    #     result.update(res)
    return result

async def main():
    for sem, srchOpenShtm in srchOpenShtms.items():
        result = await fetch(srchOpenSchyy, srchOpenShtm)
        print(f"Fetched : {len(result)}")
        with open(f"output_{srchOpenSchyy}_{sem}.json", "w", encoding = 'utf-8') as file:
            json.dump(result, file, ensure_ascii=False)

if __name__ == "__main__":
    py_ver = int(f"{sys.version_info.major}{sys.version_info.minor}")
    if py_ver > 37 and sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    # asyncio.run(main())

    # ===================================
    for sem, srchOpenShtm in srchOpenShtms.items():
        with open(f"output_{srchOpenSchyy}_{sem}.json", "r", encoding = 'utf-8') as file:
            result = json.load(file)
        for i, j in result.items():
            if j['r101'] is None: # 2022_Fall, 457.629A(001)
                print(i)
                continue
            # =====================================================
            # 정말 절평이 꿀강일까? 궁금해서 찾아본 기록
            # 역시 교바교..
            # if j['r101']["LISTTAB01"]['mrksRelevalYn'] != "YES":
            #     # if j['r101']['LISTTAB01']['departmentKorNm'] not in ('수리과학부', '컴퓨터공학부'):
            #     if j['r101']['LISTTAB01']['departmentKorNm'] not in ('컴퓨터공학부',):
            #         continue
            #     assert j['r101']["LISTTAB01"]['mrksRelevalYn'] == 'NO'
            #     print(f'{srchOpenSchyy}_{sem}', i, j['r101']['LISTTAB01']['sbjtNm'], j['r101']['LISTTAB01']['profNm'], j['r101']['LISTTAB01']['departmentKorNm'], sep=' / ')
            # =====================================================
            if "하이브리드" in str(j) or "비대면" in str(j) or "온라인" in str(j):
                if j['r101']['LISTTAB01']['departmentKorNm']  not in ('수리과학부', '컴퓨터공학부', '데이터사이언스학과'):
                    continue
                pos = max((str(j).find("하이브리드"), str(j).find("비대면"), str(j).find("온라인")))
                print(i, j['r101']['LISTTAB01']['sbjtNm'], j['r101']['LISTTAB01']['profNm'], j['r101']['LISTTAB01']['departmentKorNm'], sep=' / ')
                print(str(j)[pos - 30 : pos + 30])