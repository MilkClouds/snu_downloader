import requests, logging, re, json
from bs4 import BeautifulSoup as Soup

logging.basicConfig(level=logging.INFO, format='%(message)s', filename="log.txt", encoding="utf-8")

def fetch(page: int):
    url = "https://sugang.snu.ac.kr/sugang/cc/cc100InterfaceSrch.action"
    data = f"workType=S&pageNo={page + 1}&srchOpenSchyy=2022&srchOpenShtm=U000200002U000300002&srchSbjtNm=&srchSbjtCd=&seeMore=%EB%8D%94%EB%B3%B4%EA%B8%B0&srchCptnCorsFg=&srchOpenShyr=&srchOpenUpSbjtFldCd=&srchOpenSbjtFldCd=&srchOpenUpDeptCd=&srchOpenDeptCd=&srchOpenMjCd=&srchOpenSubmattCorsFg=&srchOpenSubmattFgCd1=&srchOpenSubmattFgCd2=&srchOpenSubmattFgCd3=&srchOpenSubmattFgCd4=&srchOpenSubmattFgCd5=&srchOpenSubmattFgCd6=&srchOpenSubmattFgCd7=&srchOpenSubmattFgCd8=&srchOpenSubmattFgCd9=&srchExcept=&srchOpenPntMin=&srchOpenPntMax=&srchCamp=&srchBdNo=&srchProfNm=&srchOpenSbjtTmNm=&srchOpenSbjtDayNm=&srchOpenSbjtTm=&srchOpenSbjtNm=&srchTlsnAplyCapaCntMin=&srchTlsnAplyCapaCntMax=&srchLsnProgType=&srchTlsnRcntMin=&srchTlsnRcntMax=&srchMrksGvMthd=&srchIsEngSbjt=&srchMrksApprMthdChgPosbYn=&srchIsPendingCourse=&srchGenrlRemoteLtYn=&srchLanguage=ko&srchCurrPage=1&srchPageSize=9999"
    data = {i.split("=")[0]: i.split("=")[1] for i in data.split("&")}
    r = requests.post(url, data)
    assert(r.status_code == 200)
    soup = Soup(r.text, 'html.parser')
    logging.info(soup)
    result = {}
    for element in soup.select("a.course-info-detail"):
        element = element.select("ul > li:nth-child(1) > span:nth-child(3)")[0]
        r = re.match("(.*?)\((\d+)\)", element.text)
        sbjtCd, ltNo = r[1], r[2]
        data = "workType=+&openSchyy=2022&openShtmFg=U000200002&openDetaShtmFg=U000300002&sbjtCd=M3500.001500&ltNo=001&sbjtSubhCd=000&t_profPersNo="
        data = {i.split("=")[0]: i.split("=")[1] for i in data.split("&")}
        data.update(dict(sbjtCd=sbjtCd, ltNo=ltNo))
        r101 = requests.post("https://sugang.snu.ac.kr/sugang/cc/cc101ajax.action", data)
        r103 = requests.post("https://sugang.snu.ac.kr/sugang/cc/cc103ajax.action", data)
        result[element.text] = dict(r101= r101.json(), r103=r103.json())
        logging.info(element.text)
    print(len(result))
    return result

if __name__ == "__main__":
    # # Un-comment below lines to crowl
    # result = {}
    # for page in range(29):
    #     result.update(fetch(page))
    # print(f"Fetched : {len(result)}")
    # with open("output.json", "w", encoding = 'utf-8') as file:
    #     json.dump(result, file, ensure_ascii=False)

    # ===================================
    with open("output.json", encoding='utf-8') as file:
        result = json.load(file)
    for i, j in result.items():
        if "하이브리드" in str(j) or "비대면" in str(j):
            print(i, j['r101']['LISTTAB01']['sbjtNm'], j['r101']['LISTTAB01']['profNm'], j['r101']['LISTTAB01']['departmentKorNm'], sep=' / ')