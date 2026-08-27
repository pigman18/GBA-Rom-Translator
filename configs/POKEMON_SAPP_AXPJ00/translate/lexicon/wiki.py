### 抓取官方译名
import json
import requests
from bs4 import BeautifulSoup

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

### 抓取全国图鉴
def tj():
    # 目标页面
    url = "https://wiki.52poke.com/wiki/宝可梦列表（按全国图鉴编号）/简单版"
    resp = requests.get(url, headers=headers, timeout=15)
    soup = BeautifulSoup(resp.text, 'html.parser')
    result = {}
    tables = soup.find_all('table', class_='eplist')
    if tables:
        for table in tables[0:]:
            rows = table.find_all('tr')
            for row in rows[1:]:  # 跳过表头
                cells = row.find_all('td')
                if len(cells) >= 3:
                    # 日文在第二列，简体中文在第一列
                    jp_cell = cells[2]  # 日文假名
                    cn_cell = cells[1]  # 简体中文
                    jp_text = jp_cell.get_text(strip=True)
                    cn_text = cn_cell.get_text(strip=True)
                    if jp_text and cn_text and jp_text != cn_text:
                        result[jp_text] = cn_text
    with open('图鉴.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"图鉴抓取完成: {len(result)}")

### 抓取招式列表
def zs():
    # 目标页面
    url = "https://wiki.52poke.com/wiki/招式列表"
    resp = requests.get(url, headers=headers, timeout=15)
    soup = BeautifulSoup(resp.text, 'html.parser')
    result = {}
    tables = soup.find_all('table', class_='hvlist')
    if tables:
        for table in tables[0:]:
            rows = table.find_all('tr')
            for row in rows[1:]:  # 跳过表头
                cells = row.find_all('td')
                if len(cells) >= 3:
                    # 日文在第二列，简体中文在第一列
                    jp_cell = cells[2]  # 日文假名
                    cn_cell = cells[1]  # 简体中文
                    jp_text = jp_cell.get_text(strip=True)
                    cn_text = cn_cell.get_text(strip=True)
                    if jp_text and cn_text and jp_text != cn_text:
                        result[jp_text] = cn_text
    with open('招式.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"招式列表抓取完成: {len(result)}")

### 抓取特性列表
def tx():
    # 目标页面
    url = "https://wiki.52poke.com/wiki/特性列表"
    resp = requests.get(url, headers=headers, timeout=15)
    soup = BeautifulSoup(resp.text, 'html.parser')
    result = {}
    tables = soup.find_all('table', class_='eplist')
    if tables:
        for table in tables[0:]:
            rows = table.find_all('tr')
            for row in rows[1:]:  # 跳过表头
                cells = row.find_all('td')
                if len(cells) >= 3:
                    # 日文在第二列，简体中文在第一列
                    jp_cell = cells[2]  # 日文假名
                    cn_cell = cells[1]  # 简体中文
                    jp_text = jp_cell.get_text(strip=True)
                    cn_text = cn_cell.get_text(strip=True)
                    if jp_text and cn_text and jp_text != cn_text:
                        result[jp_text] = cn_text
    with open('特性.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"特性列表抓取完成: {len(result)}")

### 抓取道具列表
def dj():
    # 目标页面
    url = "https://wiki.52poke.com/wiki/道具列表"
    resp = requests.get(url, headers=headers, timeout=15)
    soup = BeautifulSoup(resp.text, 'html.parser')
    result = {}
    tables = soup.find_all('table', class_='hvlist')
    if tables:
        for table in tables[0:]:
            rows = table.find_all('tr')
            for row in rows[1:]:  # 跳过表头
                cells = row.find_all('td')
                if len(cells) >= 3:
                    # 日文在第二列，简体中文在第一列
                    jp_cell = cells[2]  # 日文假名
                    cn_cell = cells[1]  # 简体中文
                    jp_text = jp_cell.get_text(strip=True)
                    cn_text = cn_cell.get_text(strip=True)
                    if jp_text and cn_text and jp_text != cn_text:
                        result[jp_text] = cn_text
    with open('道具.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"道具列表抓取完成: {len(result)}")

### 抓取地点列表
def dd():
    # 目标页面
    url = "https://wiki.52poke.com/wiki/地点列表"
    resp = requests.get(url, headers=headers, timeout=15)
    soup = BeautifulSoup(resp.text, 'html.parser')
    result = {}
    tables = soup.find_all('table', class_='eplist')
    if tables:
        for table in tables[0:]:
            rows = table.find_all('tr')
            for row in rows[1:]:  # 跳过表头
                cells = row.find_all('td')
                if len(cells) >= 3:
                    # 日文在第二列，简体中文在第一列
                    jp_cell = cells[1]  # 日文假名
                    cn_cell = cells[0]  # 简体中文
                    jp_text = jp_cell.get_text(strip=True)
                    cn_text = cn_cell.get_text(strip=True)
                    if jp_text and cn_text and jp_text != cn_text:
                        result[jp_text] = cn_text
    with open('地点.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"地点列表抓取完成: {len(result)}")

### 抓取性格列表
def xg():
    # 目标页面
    url = "https://wiki.52poke.com/wiki/性格"
    resp = requests.get(url, headers=headers, timeout=15)
    soup = BeautifulSoup(resp.text, 'html.parser')
    result = {}
    tables = soup.find_all('table', class_='sortable')
    table = tables[0]
    rows = table.find_all('tr')
    for row in rows[1:]:  # 跳过表头
        cells = row.find_all()
        if len(cells) >= 3:
            # 日文在第二列，简体中文在第一列
            jp_cell = cells[1]  # 日文假名
            cn_cell = cells[0]  # 简体中文
            jp_text = jp_cell.get_text(strip=True)
            cn_text = cn_cell.get_text(strip=True)
            if jp_text and cn_text and jp_text != cn_text:
                result[jp_text] = cn_text
    with open('性格.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"性格列表抓取完成: {len(result)}")

# tj()
# zs()
# tx()
# dj()
# dd()
xg()
