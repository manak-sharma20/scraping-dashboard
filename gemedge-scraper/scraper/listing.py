"""
Module for filtering and extracting listing-level bid data from the GeM portal.
"""
import re
import asyncio
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# Constants
PORTAL_URL = "https://bidplus.gem.gov.in/all-bids"
ONGOING_LABEL = "Ongoing Bids/RA"
STATUS_LABEL = "Bid/RA Status"
AWARDED_LABEL = "Bid /RA Awarded"
NEXT_SELECTOR = "a:has-text('Next')"
CARD_SELECTOR = "div.border.card, div.well, div.post_card, .bid_card"
WAIT_TIMEOUT = 1500

async def setup_filters(page) -> bool:
    """Apply the Status and Awarded filters on the page."""
    try:
        # Navigate to portal
        await page.goto(PORTAL_URL, wait_until="networkidle")
        await page.wait_for_timeout(WAIT_TIMEOUT)

        # Uncheck "Ongoing Bids/RA"
        ongoing_chk = page.locator(f"label:has-text('{ONGOING_LABEL}')").locator("input[type='checkbox']")
        if await ongoing_chk.is_checked():
            await ongoing_chk.uncheck()
            await page.wait_for_timeout(WAIT_TIMEOUT)

        # Check "Bid/RA Status"
        status_chk = page.locator(f"label:has-text('{STATUS_LABEL}')").locator("input[type='checkbox']")
        await status_chk.check()
        await page.wait_for_timeout(WAIT_TIMEOUT)

        # Check "Bid /RA Awarded"
        awarded_chk = page.locator(f"label:has-text('{AWARDED_LABEL}')").locator("input[type='checkbox']")
        await awarded_chk.check()
        await page.wait_for_timeout(WAIT_TIMEOUT)
        return True
    except Exception as e:
        print(f"[ERROR] setup_filters: {e}")
        return False

def parse_card_field(soup, label) -> str:
    """Extract a field value by its label text in BeautifulSoup."""
    try:
        el = soup.find(string=lambda t: label in t if t else False)
        if not el:
            return None
        text = el.parent.get_text(separator=" ", strip=True)
        val = text.split(label)[-1].strip()
        return val.lstrip(":").lstrip("-").strip()
    except Exception as e:
        print(f"[ERROR] parse_card_field: {e}")
        return None

def clean_card_data(soup) -> dict:
    """Parse card HTML using BeautifulSoup and extract structured fields."""
    card_text = soup.get_text(separator=" ")
    data = {
        "bid_id": None, "bid_no": None, "ra_no": None, "category": None,
        "buyer": None, "quantity": None, "bid_value": None,
        "start_date": None, "end_date": None
    }
    try:
        # Extract Bid No and ID
        bid_no_text = parse_card_field(soup, "Bid No.:")
        if bid_no_text:
            match = re.search(r'GEM/\d{4}/B/\d+', bid_no_text)
            if match:
                data["bid_no"] = match.group(0)
                data["bid_id"] = data["bid_no"].split("/")[-1]

        # Fallback Bid No check in card text
        if not data["bid_no"]:
            matches = re.findall(r'GEM/\d{4}/B/\d+', card_text)
            if matches:
                data["bid_no"] = matches[0]
                data["bid_id"] = data["bid_no"].split("/")[-1]

        # Extract RA No
        ra_text = parse_card_field(soup, "RA NO:")
        if ra_text:
            match = re.search(r'GEM/\d{4}/R/\d+', ra_text)
            if match:
                data["ra_no"] = match.group(0)

        # Extract category, quantity, buyer
        data["category"] = parse_card_field(soup, "Items:")
        qty_text = parse_card_field(soup, "Quantity:")
        if qty_text:
            qty_match = re.search(r'\d+', qty_text)
            if qty_match:
                data["quantity"] = int(qty_match.group(0))

        data["buyer"] = parse_card_field(soup, "Department Name And Address:")
        data["start_date"] = parse_card_field(soup, "Start Date:")
        data["end_date"] = parse_card_field(soup, "End Date:")
        data["bid_value"] = parse_card_field(soup, "Bid Value:")
        
        # Extract View Bid Results link
        detail_btn = soup.find("a", string=lambda t: "View Bid Results" in t if t else False)
        if not detail_btn:
            # Search by partial text or href
            detail_btn = soup.find("a", href=lambda h: h and "bidresultdetail" in h)
        if detail_btn and detail_btn.has_attr("href"):
            href = detail_btn["href"]
            if href.startswith("/"):
                href = f"https://bidplus.gem.gov.in{href}"
            data["detail_url"] = href
        else:
            # Construct standard fallback if we have a bid_id
            if data["bid_id"]:
                data["detail_url"] = f"https://bidplus.gem.gov.in/landing/index/bidresultdetail/id/{data['bid_id']}"
            else:
                data["detail_url"] = None

        return data

    except Exception as e:
        print(f"[ERROR] clean_card_data: {e}")
        return data

async def extract_page_cards(page) -> list:
    """Extract bid cards from the current page."""
    results = []
    try:
        html = await page.content()
        soup = BeautifulSoup(html, "lxml")
        pagi_div = soup.find("div", id="pagi_content")
        if not pagi_div:
            return results

        # Bids are usually in divs inside pagi_content
        # Let's find all divs that contain "Bid No.:" text
        for div in pagi_div.find_all("div", recursive=False):
            if "Bid No.:" in div.get_text():
                card_data = clean_card_data(div)
                if card_data["bid_no"]:
                    results.append(card_data)
        return results
    except Exception as e:
        print(f"[ERROR] extract_page_cards: {e}")
        return results

async def paginate_next(page) -> bool:
    """Click the 'Next' page button and wait for page to turn."""
    try:
        next_btn = page.locator(NEXT_SELECTOR)
        if await next_btn.count() > 0 and await next_btn.is_visible():
            await next_btn.click()
            await page.wait_for_timeout(WAIT_TIMEOUT)
            await page.wait_for_load_state("networkidle")
            return True
        return False
    except Exception as e:
        print(f"[ERROR] paginate_next: {e}")
        return False

async def get_awarded_bids(n=30) -> list:
    """Launch Playwright browser, apply filters, and scrape n bid records."""
    bids = []
    playwright_ctx = None
    try:
        playwright_ctx = await async_playwright().start()
        browser = await playwright_ctx.chromium.launch(headless=True)
        page = await browser.new_page()
        
        if not await setup_filters(page):
            await browser.close()
            await playwright_ctx.stop()
            return bids

        while len(bids) < n:
            cards = await extract_page_cards(page)
            for card in cards:
                if card not in bids:
                    bids.append(card)
            if len(bids) >= n or not await paginate_next(page):
                break

        await browser.close()
        await playwright_ctx.stop()
    except Exception as e:
        print(f"[ERROR] get_awarded_bids: {e}")
        if playwright_ctx:
            await playwright_ctx.stop()
    return bids[:n]
