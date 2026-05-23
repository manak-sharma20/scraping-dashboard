"""
Main orchestration script for the GeM portal web scraper.
"""
import asyncio
import os
import json
import pandas as pd
from playwright.async_api import async_playwright

from scraper.listing import get_awarded_bids
from scraper.detail import get_bid_detail
from scraper.evaluation import get_evaluation_details

# Constants
CSV_OUTPUT_PATH = "gemedge-scraper/data/output.csv"
JSON_OUTPUT_PATH = "gemedge-scraper/data/output.json"
SUMMARY_OUTPUT_PATH = "gemedge-scraper/data/summary.txt"

def clean_vendor_name(name) -> str:
    """Normalize vendor name to Title Case and strip whitespace."""
    if not name or pd.isna(name):
        return None
    return str(name).strip().title()

def determine_status(row, duplicate_ids) -> str:
    """Determine status_flag: duplicate, anomaly, or clean."""
    bid_id = row.get("bid_id")
    if bid_id in duplicate_ids:
        return "duplicate"
    
    # Anomaly check: if winner's rank is not L1
    rank = row.get("vendor_rank")
    vendor_name = row.get("vendor_name")
    winner_name = row.get("winner_name")
    
    if vendor_name and winner_name and vendor_name.lower().strip() == winner_name.lower().strip():
        if rank and rank != "L1":
            return "anomaly"
            
    return "clean"

def compute_summary_insights(df: pd.DataFrame) -> dict:
    """Compute summary metrics from the final DataFrame."""
    metrics = {
        "pct_gt_3_bidders": 0.0,
        "avg_l1_l2_gap": 0.0,
        "repeat_winners": []
    }
    try:
        # Group by unique bid_id
        unique_bids = df.drop_duplicates(subset=["bid_id"])
        
        # 1. % of bids where num_bidders > 3
        if len(unique_bids) > 0:
            gt_3 = unique_bids[unique_bids["num_bidders"] > 3]
            metrics["pct_gt_3_bidders"] = (len(gt_3) / len(unique_bids)) * 100.0
            
        # 2. Average price gap between L1 and L2
        gaps = []
        for bid_id, group in df.groupby("bid_id"):
            l1_row = group[group["vendor_rank"] == "L1"]
            l2_row = group[group["vendor_rank"] == "L2"]
            if not l1_row.empty and not l2_row.empty:
                l1_price = l1_row.iloc[0]["vendor_price"]
                l2_price = l2_row.iloc[0]["vendor_price"]
                if pd.notna(l1_price) and pd.notna(l2_price):
                    gaps.append(abs(l2_price - l1_price))
        if gaps:
            metrics["avg_l1_l2_gap"] = sum(gaps) / len(gaps)
            
        # 3. Repeat winners (winner_name count > 2)
        winner_counts = unique_bids["winner_name"].dropna().value_counts()
        metrics["repeat_winners"] = winner_counts[winner_counts > 2].index.tolist()
    except Exception as e:
        print(f"[ERROR] compute_summary_insights: {e}")
    return metrics

def write_summary_report(metrics: dict):
    """Write summary metrics to summary.txt."""
    try:
        os.makedirs(os.path.dirname(SUMMARY_OUTPUT_PATH), exist_ok=True)
        with open(SUMMARY_OUTPUT_PATH, "w") as f:
            f.write("=== GeM Scraper Insights Report ===\n")
            f.write(f"Percentage of bids with >3 bidders: {metrics['pct_gt_3_bidders']:.2f}%\n")
            f.write(f"Average L1/L2 price gap: {metrics['avg_l1_l2_gap']:.2f}\n")
            f.write(f"Repeat winners (>2 wins): {', '.join(metrics['repeat_winners']) if metrics['repeat_winners'] else 'None'}\n")
        print(f"[INFO] Summary report written to {SUMMARY_OUTPUT_PATH}")
    except Exception as e:
        print(f"[ERROR] write_summary_report: {e}")

async def process_bid_details(playwright_ctx, listings) -> list:
    """Visit details page for each listing and extract evaluation data."""
    flat_rows = []
    try:
        browser = await playwright_ctx.chromium.launch(headless=True)
        page = await browser.new_page()
        
        for bid in listings:
            detail_url = bid.get("detail_url")
            if not detail_url:
                continue
                
            print(f"[INFO] Drilling into details for Bid: {bid['bid_no']}")
            details = await get_bid_detail(page, detail_url)
            evals = await get_evaluation_details(page)
            
            # Combine listing info, detail info, and evaluation info
            # If no evaluations found, create a placeholder row
            if not evals:
                evals = [{"vendor_name": None, "vendor_price": None, "rank": None, "disqualified": None, "remarks": None}]
                
            for ev in evals:
                row = {**bid, **details}
                row["vendor_name"] = clean_vendor_name(ev.get("vendor_name"))
                row["vendor_price"] = ev.get("vendor_price")
                row["vendor_rank"] = ev.get("rank")
                row["disqualified"] = ev.get("disqualified")
                row["remarks"] = ev.get("remarks")
                # winner field matches winner_name
                row["winner"] = details.get("winner_name")
                flat_rows.append(row)
                
        await browser.close()
    except Exception as e:
        print(f"[ERROR] process_bid_details: {e}")
    return flat_rows

async def main():
    """Main function to run the scraping and cleaning pipeline."""
    print("[INFO] Starting GeM web scraper...")
    listings = await get_awarded_bids(30)
    print(f"[INFO] Retrieved {len(listings)} listings.")
    
    if not listings:
        print("[ERROR] No listings found. Exiting.")
        return

    async with async_playwright() as pw:
        flat_rows = await process_bid_details(pw, listings)

    if not flat_rows:
        print("[ERROR] No data extracted from detail pages. Exiting.")
        return

    # Create DataFrame
    df = pd.DataFrame(flat_rows)
    
    # Identify duplicates
    bid_counts = df.drop_duplicates(subset=["bid_id", "vendor_name"])["bid_id"].value_counts()
    duplicate_ids = set(bid_counts[bid_counts > 1].index.tolist())
    
    # Assign status_flag
    df["status_flag"] = df.apply(lambda r: determine_status(r, duplicate_ids), axis=1)
    
    # Normalize vendor name in winner
    df["winner"] = df["winner"].apply(clean_vendor_name)
    df["winner_name"] = df["winner_name"].apply(clean_vendor_name)

    # Save outputs
    os.makedirs(os.path.dirname(CSV_OUTPUT_PATH), exist_ok=True)
    df.to_csv(CSV_OUTPUT_PATH, index=False)
    df.to_json(JSON_OUTPUT_PATH, orient="records", indent=2)
    print(f"[INFO] CSV output written to {CSV_OUTPUT_PATH}")
    print(f"[INFO] JSON output written to {JSON_OUTPUT_PATH}")

    # Compute and save insights
    insights = compute_summary_insights(df)
    write_summary_report(insights)

if __name__ == "__main__":
    asyncio.run(main())
