from bs4 import BeautifulSoup
import re
import json

def clean_text(text):
    if not text: return ""
    # 去除多余的空格和换行
    return re.sub(r'\s+', ' ', text).strip()

def parse_annual_pass_html(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 找到包含“景区目录”的目标表格
    target_table = None
    for tbl in soup.find_all('table'):
        if '2026 联合年卡 景区目录' in tbl.get_text():
            target_table = tbl
            break

    if not target_table:
        print("未找到景区目录表格！")
        return []

    # 1. 构建二维网格，完美解决 rowspan（跨行）和 colspan（跨列）导致的数据错位问题
    rows = target_table.find_all('tr')
    grid = [[] for _ in range(len(rows))]

    for i, tr in enumerate(rows):
        col_idx = 0
        for td in tr.find_all(['td', 'th']):
            # 跳过已经被跨行/跨列占据的格子
            while col_idx < len(grid[i]) and grid[i][col_idx] is not None:
                col_idx += 1
            
            rowspan = int(td.get('rowspan', 1))
            colspan = int(td.get('colspan', 1))
            
            # 将当前单元格填充到网格对应的位置中
            for r in range(rowspan):
                for c in range(colspan):
                    while len(grid[i+r]) <= col_idx + c:
                        grid[i+r].append(None)
                    grid[i+r][col_idx+c] = td
            col_idx += colspan

    # 2. 从网格中结构化提取数据
    scenic_spots = []
    current_region = "未知区域"

    for i, row_cells in enumerate(grid):
        if not row_cells: continue
        
        # 判断是否为“区域分类行”（合并了4列的行，例如“昌平区”）
        if len(set(row_cells)) == 1 and row_cells[0]:
            text = row_cells[0].get_text(strip=True)
            match = re.search(r'([^\s]+(?:区|天津|唐山|保定|承德|张家口|廊坊|石家庄|邯郸))', text)
            if match:
                current_region = match.group(1)
            continue
        
        # 判断是否为有效的数据行（至少3个不同的单元格，且跳过表头）
        if len(set(row_cells)) >= 3 and i > 2:
            td_name, td_price, td_limit, td_rules = row_cells[0], row_cells[1], row_cells[2], row_cells[3]
            
            # 过滤掉表头文字
            if not td_name or '景区名称' in td_name.get_text():
                continue
                
            # --- 清洗：景点名称与特殊说明 ---
            # 有些名称后面跟着 A级 (如 3A, 4A)，有的换行带了闭园通知 (如 2.16-2.19闭园)
            raw_name = td_name.get_text(separator='|', strip=True)
            name_parts = raw_name.split('|')
            # 提取纯净名称，剔除 A 级标识
            name = re.sub(r'\d[A|a]', '', name_parts[0]).strip() 
            notes = " ".join(name_parts[1:]).strip() if len(name_parts) > 1 else ""
            
            # --- 清洗：票价与次数 ---
            price = clean_text(td_price.get_text())
            limit = clean_text(td_limit.get_text())
            
            # --- 清洗：使用规则与日期 ---
            rules_raw = td_rules.get_text(separator='\n', strip=True)
            # 正则提取日期范围 (例如 2026.1.1-8.31，兼容网页里 026.6.1 的错别字)
            dates_found = re.findall(r'(?:2026\.|026\.)?\d{1,2}\.\d{1,2}\s*-\s*(?:2026\.)?\d{1,2}\.\d{1,2}', rules_raw)
            valid_time = " & ".join(dates_found) if dates_found else "全年/未标明"
            
            # 把日期从规则里剔除，让规则文本更纯粹
            rules_cleaned = re.sub(r'(?:2026\.|026\.)?\d{1,2}\.\d{1,2}\s*-\s*(?:2026\.)?\d{1,2}\.\d{1,2}', '', rules_raw)
            rules_cleaned = re.sub(r'\n+', ' | ', rules_cleaned).strip(' |')
            
            scenic_spots.append({
                "region": current_region,
                "name": name,
                "price": price,
                "limit": limit,
                "valid_time": valid_time,
                "rules": rules_cleaned,
                "notes": notes,
                "visited_count": 0  # 预留给日历打卡系统的字段
            })

    # 3. 导出为清晰的 JSON 文件
    with open('cleaned_parks_2026.json', 'w', encoding='utf-8') as f:
        json.dump(scenic_spots, f, ensure_ascii=False, indent=4)
    
    print(f"✅ 数据清洗完成！共成功提取 {len(scenic_spots)} 个景点信息。")

# 运行代码
parse_annual_pass_html('park.html')
