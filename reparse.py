"""
特定地区のキャッシュを削除して再解析する
使い方: python reparse.py 3   （3地区を再解析）
        python reparse.py all （全地区を再解析）
"""
import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

if len(sys.argv) < 2:
    print("使い方: python reparse.py <地区番号 or all>")
    sys.exit(1)

arg = sys.argv[1]
cache_dir = Path("cache")

if arg == "all":
    targets = [1, 2, 3, 4]
else:
    targets = [int(arg)]

# キャッシュ削除
for d in targets:
    f = cache_dir / f"district_{d}.json"
    if f.exists():
        f.unlink()
        print(f"地区{d} キャッシュ削除")

# 再解析
from calendar_parser import GarbageCalendar
cal = GarbageCalendar()

# 結果確認
from datetime import date, timedelta
today = date.today()
print("\n=== 今日から7日間のプレビュー ===")
for d in targets:
    print(f"\n【地区{d}】")
    for i in range(7):
        print(cal._format_day(d, today + timedelta(days=i)))
