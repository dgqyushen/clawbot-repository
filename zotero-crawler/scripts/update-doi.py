#!/usr/bin/env python3
"""
补充已导入论文的DOI到Zotero
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from pyzotero import zotero

# Zotero配置
library_id = "14021209"
api_key = "1lio7Ai65J0B1wsmBRAXL0ju"

# 论文DOI映射 (item_key -> DOI)
papers_with_doi = {
    'FPD6ERD7': '10.1016/j.est.2026.121182',  # Si-SiOx-C nanofiber
    '5MSGMXCK': '10.1016/j.jpowsour.2026.239654',  # Cu-Fe-modified silicon nanowire
    'MX2CX4X9': '10.1016/j.est.2026.121108',  # Femtosecond laser Si/C
}

zot = zotero.Zotero(library_id, 'user', api_key)

for item_key, doi in papers_with_doi.items():
    try:
        # 获取当前条目
        item = zot.item(item_key)
        if not item:
            print(f"❌ Item {item_key} not found")
            continue
            
        # 更新DOI
        item['data']['DOI'] = doi
        
        # 保存更新
        zot.update_item(item)
        title = item['data'].get('title', 'Unknown')[:50]
        print(f"✅ Updated {item_key}: {title}...")
        print(f"   DOI: {doi}")
        
    except Exception as e:
        print(f"❌ Failed to update {item_key}: {e}")

print("\nDone!")
