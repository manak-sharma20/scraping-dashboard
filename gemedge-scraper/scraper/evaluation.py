"""
Module for extracting detailed vendor evaluation and ranking information from results.
"""
import re
from bs4 import BeautifulSoup

# Constants
EVAL_DETAILS_SELECTOR = "text=Evaluation Details"
STATUS_DISQUALIFIED = "disqualified"

def parse_tech_rows(soup) -> list:
    """Parse the Technical Evaluation table rows."""
    vendors = []
    try:
        # Find the technical evaluation table
        tech_header = soup.find(string=lambda t: "Technical Evaluation" in t if t else False)
        table = None
        if tech_header:
            table = tech_header.find_parent("table") or tech_header.find_next("table")
        
        if not table:
            # Fallback to the first table
            tables = soup.find_all("table")
            if tables:
                table = tables[0]

        if table:
            for row in table.find_all("tr")[1:]:
                cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
                if len(cells) >= 3:
                    # columns: S.No | Seller Name | Status | Remarks/Reason
                    name = cells[1]
                    status = cells[2].lower()
                    disqualified = STATUS_DISQUALIFIED in status or "reject" in status
                    remarks = cells[3] if len(cells) > 3 else None
                    vendors.append({
                        "vendor_name": name,
                        "disqualified": disqualified,
                        "remarks": remarks,
                        "vendor_price": None,
                        "rank": None
                    })
    except Exception as e:
        print(f"[ERROR] parse_tech_rows: {e}")
    return vendors

def parse_fin_ranks(soup) -> dict:
    """Parse the Financial Evaluation table and map names to prices and ranks."""
    ranks = {}
    try:
        fin_header = soup.find(string=lambda t: "Financial Evaluation" in t if t else False)
        table = None
        if fin_header:
            table = fin_header.find_parent("table") or fin_header.find_next("table")
        
        if not table:
            # Fallback to secondary table
            tables = soup.find_all("table")
            if len(tables) > 1:
                table = tables[1]

        if table:
            for row in table.find_all("tr")[1:]:
                cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
                if len(cells) >= 3:
                    # columns: Rank | Seller Name | Offered Price
                    rank = cells[0]
                    name = cells[1]
                    price_str = cells[2]
                    price = None
                    price_match = re.search(r'[\d\.,]+', price_str)
                    if price_match:
                        price = float(price_match.group(0).replace(",", ""))
                    ranks[name] = {"rank": rank, "vendor_price": price}
    except Exception as e:
        print(f"[ERROR] parse_fin_ranks: {e}")
    return ranks

def merge_evaluation_data(html_content: str) -> list:
    """Extract and merge Technical and Financial Evaluation tables."""
    soup = BeautifulSoup(html_content, "lxml")
    vendors = parse_tech_rows(soup)
    fin_ranks = parse_fin_ranks(soup)
    
    # Merge financial rank and price back to qualified vendors
    for v in vendors:
        name = v["vendor_name"]
        # Match using fuzzy or exact lookup
        match_info = fin_ranks.get(name)
        if not match_info:
            # Fuzzy check (e.g. if names differ by whitespace/case)
            for k, val in fin_ranks.items():
                if k.lower().strip() == name.lower().strip():
                    match_info = val
                    break
        if match_info:
            v.update(match_info)
            
    # If no vendors were parsed, try to extract any rank elements directly
    if not vendors and fin_ranks:
        for name, info in fin_ranks.items():
            vendors.append({
                "vendor_name": name,
                "disqualified": False,
                "remarks": None,
                "vendor_price": info["vendor_price"],
                "rank": info["rank"]
            })
            
    return vendors

async def get_evaluation_details(page) -> list:
    """Click 'Evaluation Details' and extract vendor rank/price data."""
    results = []
    try:
        btn = page.locator(EVAL_DETAILS_SELECTOR)
        if await btn.count() > 0:
            await btn.click()
            await page.wait_for_timeout(1500)
            await page.wait_for_load_state("networkidle")
            
        html = await page.content()
        results = merge_evaluation_data(html)
    except Exception as e:
        print(f"[ERROR] get_evaluation_details: {e}")
    return results
