# SNU eTL Batch Downloader

Download lecture files, videos, and assignment info from SNU eTL (Canvas LMS).

## Features

- **Files**: Download all files in a course, preserving the eTL folder structure
- **Videos**: SNU-CMS lecture videos and YouTube-embedded videos
- **Assignments**: Save assignment details (due date, points, submission type) as HTML
- **Semester filter**: Download only courses matching a specific semester (e.g. `2026-1`)
- **Incremental**: Skips already-downloaded files on re-run
- **Session caching**: Login once, reuse the session until it expires (`--logout` to clear)

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- A Chromium-based browser (Chrome, Edge, etc.) — ChromeDriver is managed automatically

## Setup

```
git clone https://github.com/MilkClouds/snu_downloader.git
cd snu_downloader
uv sync
```

## Usage

```
uv run python main.py [options]
```

| Flag | Description | Default |
|------|-------------|---------|
| `-s`, `--semester` | Filter by semester (e.g. `2026-1`) | all semesters |
| `-l`, `--lecture` | Course ID or `all` | `all` |
| `-d`, `--dir` | Output directory | `./downloads` |
| `-y`, `--yes` | Skip disclaimer prompt | |
| `--logout` | Clear saved session and exit | |

On first run, a Chrome window opens for SNU SSO login (MFA supported). Subsequent runs reuse the saved session.

The course ID can be found in the eTL URL: `https://myetl.snu.ac.kr/courses/<id>`

### Examples

```bash
# Download all courses from 2026 spring semester
uv run python main.py -s 2026-1

# Download a single course
uv run python main.py -l 123456

# Download to a custom directory, skip disclaimer
uv run python main.py -s 2026-1 -d ~/lectures -y
```

### Output structure

```
downloads/
  <course name>/
    lecture.pdf
    <subfolder>/
      slides.pptx
    _assignments/
      <assignment>.html
    _videos/
      <lecture>.mp4
```

## Disclaimer

This program is not affiliated with Seoul National University. Use at your own risk. Your credentials are only used for eTL authentication and are not stored or transmitted elsewhere.

## Libraries Under Consideration

- [SeleniumBase](https://github.com/seleniumbase/SeleniumBase) — Selenium-based browser automation framework
- [Vibium](https://github.com/VibiumDev/vibium) — Browser automation tool
- [Helium](https://github.com/mherrmann/helium) — Lightweight Selenium wrapper

## Credit

- [junukwon7](https://github.com/junukwon7)
