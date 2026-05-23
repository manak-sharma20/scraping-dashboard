"""
Module for drilling into bid result pages and extracting winner details.
"""
import re
from bs4 import BeautifulSoup

# Constants
VIEW_RESULTS_SELECTOR = "text=View Bid Results"
TECH_STATUS_QUALIFIED = "Qualified"
TECH_STATUS_DISQUALIFIED = "Disqualified"

def parse_num_bidders(soup) -> int:
    """Extract the total number of bidders from the technical evaluation table."""
    try:
        # Find all rows in the technical evaluation table
        # Typically, it contains rows of sellers
        tech_table = soup.find(string=lambda t: "Technical Evaluation" in t if t else False)
        if not tech_table:
            # Fallback to searching all tables
            tables = soup.find_all("table")
            if tables:
                return len(tables[0].find_all("tr")) - 1
            return 0
        
        table = tech_table.find_parent("table") or tech_table.find_next("table")
        if table:
            rows = table.find_all("tr")[1:]  # skip header
            return len(rows)
        return 0
    except Exception as e:
        print(f"[ERROR] parse_num_bidders: {e}")
        return 0

def parse_winner_financials(soup) -> tuple:
    """Extract winner name and price from the financial evaluation table."""
    winner_name, winner_price = None, None
    try:
        fin_text = soup.find(string=lambda t: "Financial Evaluation" in t if t else False)
        table = None
        if fin_text:
            table = fin_text.find_parent("table") or fin_text.find_next("table")
        
        if not table:
            # Fallback: find any table that contains 'L1' or 'Rank'
            for t in soup.find_all("table"):
                if "L1" in t.get_text():
                    table = t
                    break
        
        if table:
            for row in table.find_all("tr")[1:]:
                cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
                if cells and "L1" in cells[0]:
                    # Format: Rank | Seller Name | Offered Price
                    winner_name = cells[1] if len(cells) > 1 else None
                    price_str = cells[2] if len(cells) > 2 else None
                    if price_str:
                        # Extract digits/dots for price
                        price_match = re.search(r'[\d\.,]+', price_str)
                        if price_match:
                            winner_price = float(price_match.group(0).replace(",", ""))
                    break
        return winner_name, winner_price
    except Exception as e:
        print(f"[ERROR] parse_winner_financials: {e}")
        return None, None

def parse_details_html(html_content: str) -> dict:
    """Extract winner details and number of bidders from the page HTML."""
    soup = BeautifulSoup(html_content, "lxml")
    winner_name, winner_price = parse_winner_financials(soup)
    num_bidders = parse_num_bidders(soup)
    
    # If no bidders found in table, try to count unique seller names
    if num_bidders == 0:
        sellers = set()
        for cell in soup.find_all("td"):
            text = cell.get_text(strip=True)
            if text and not text.isdigit() and len(text) > 3:
                sellers.add(text)
        num_bidders = len(sellers)

    return {
        "winner_name": winner_name,
        "winner_price": winner_price,
        "num_bidders": num_bidders if num_bidders > 0 else None
    }

async def get_bid_detail(page, bid_url: str) -> dict:
    """Navigate to the bid detail page and extract winner details."""
    data = {"winner_name": None, "winner_price": None, "num_bidders": None}
    try:
        await page.goto(bid_url, wait_until="networkidle")
        await page.wait_for_timeout(1000)
        
        btn = page.locator(VIEW_RESULTS_SELECTOR)
        if await btn.count() > 0:
            await btn.click()
            await page.wait_for_timeout(1500)
            await page.wait_for_load_state("networkidle")
            
        html = await page.content()
        parsed = parse_details_html(html)
        data.update(parsed)
    except Exception as e:
        print(f"[ERROR] get_bid_detail: {e}")
    return data
