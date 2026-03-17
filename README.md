# SNU eTL Batch Downloader
Downloads all lecture materials from SNU eTL (Canvas).

- Support downloading lecture video (including snu-cms, youtube-embedded lectures)
- Support downloading lecture materials (files) (ppt, pdf, ...)
- Support semester filtering (e.g. download only 2026-1 courses)


# Prerequisites

## Python 3.11+ and uv
```
pip install uv
uv sync
```

## Chrome
A Chromium-based browser (e.g. Chrome, Edge) is required.
ChromeDriver is managed automatically by Selenium.


# How to use

## Login
Login is done via the SNU SSO page in a browser window.
When the program starts, a Chrome window will open — log in with your SNU account (including MFA) and the program will proceed automatically.

## Usage
```
uv run python main.py -h
usage: main.py [-h] [-d DIR] -l LECTUREID [-s SEMESTER]

SNU eTL Batch Downloader

options:
  -h, --help    show this help message and exit
  -d DIR        Directory to save files
  -l LECTUREID  Lecture ID or 'all'
  -s SEMESTER   Semester filter (e.g. '2026-1')
```

The `lectureId` can be found using the URL of the lecture. e.g. (https://myetl.snu.ac.kr/courses/123456)

## Examples
Download a specific lecture:
```
uv run python main.py -l 123456
```

Download all lectures from a specific semester:
```
uv run python main.py -l all -s "2026-1"
```

Download all lectures:
```
uv run python main.py -l all
```


# Disclaimer
```
==============================================================================================================================
DISCLAIMER: This program is not affiliated with SNU. Use at your own risk.
==============================================================================================================================
The information provided by SNU eTL Batch Downloader ("we," "us," or "our") on our application is for general
informational purposes only. All information on our application is provided in good faith, however we make no
representation or warranty of any kind, express or implied, regarding the accuracy, adequacy, validity, reliability,
availability, or completeness of any information on our application. UNDER NO CIRCUMSTANCE SHALL WE HAVE ANY LIABILITY
TO YOU FOR ANY LOSS OR DAMAGE OF ANY KIND INCURRED AS A RESULT OF THE USE OF OUR APPLICATION OR RELIANCE ON ANY
INFORMATION PROVIDED ON OUR APPLICATION. YOUR USE OF OUR APPLICATION AND YOUR RELIANCE ON ANY INFORMATION ON OUR
APPLICATION IS SOLELY AT YOUR OWN RISK.
==============================================================================================================================
본 프로그램에 의해 제공된 모든 정보는 일반적인 목적으로만 사용할 수 있습니다. 이 프로그램의/으로 만들어진 모든 정보는 공익을
위한 것이나, 개발자는 프로그램의 안정성, 적법성, 정확성, 정밀성, 의존성, 가용성, 완전성에 대하여 그 어떤 보증을 보장하지도,
함의하지도 않습니다. 이러한 조건 하에 개발자는 이 프로그램의 사용이나 생성된 정보로 인한 그 어떤 피해나 행위에 관해서도 책임을
지지 않습니다. 이 프로그램을 사용하는 것은 상기 내용에 동의하였으며, 프로그램의 사용으로 인한 책임은 전부 사용자에게 있습니다.
==============================================================================================================================
By using this program, you agree to the above terms.
==============================================================================================================================
```

# Credit
- [junukwon7](https://github.com/junukwon7)
