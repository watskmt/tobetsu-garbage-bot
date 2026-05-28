"""
PDFの中身を確認するデバッグスクリプト
最初にこれを実行してPDFの構造を把握する

実行: python debug_pdf.py
"""
import pdfplumber
import requests
import io

BASE_URL = "https://www.town.tobetsu.hokkaido.jp"
DISTRICT_PDFS = {
    1: "/uploaded/attachment/29812.pdf",
    2: "/uploaded/attachment/29813.pdf",
    3: "/uploaded/attachment/29814.pdf",
    4: "/uploaded/attachment/29815.pdf",
}

def debug_district(district: int):
    url = BASE_URL + DISTRICT_PDFS[district]
    print(f"\n地区{district} PDF: {url}")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
        print(f"総ページ数: {len(pdf.pages)}")
        for i, page in enumerate(pdf.pages[:3]):  # 最初の3ページのみ確認
            print(f"\n{'='*60}")
            print(f"ページ {i+1}")
            print(f"{'='*60}")

            text = page.extract_text()
            print("--- テキスト抽出 ---")
            print(text or "(テキストなし → 画像PDFの可能性あり)")

            tables = page.extract_tables()
            print(f"\n--- テーブル抽出 ({len(tables)}個) ---")
            for j, table in enumerate(tables):
                print(f"テーブル {j+1} ({len(table)}行 x {len(table[0]) if table else 0}列):")
                for row in table:
                    print(row)


if __name__ == "__main__":
    # まず3地区で試す（白樺町・下川町エリア）
    debug_district(3)
