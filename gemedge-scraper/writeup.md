# GemEdge Web Scraping Assignment Write-Up

## Overview & Architecture
This scraper is designed to extract procurement data from the Government e-Marketplace (GeM) portal (https://bidplus.gem.gov.in/all-bids). The objective is to gather historical records of awarded tenders, map out the participating sellers, capture their technical and financial evaluations, and detect bidding anomalies.

The scraper follows a modular, pipeline-oriented architecture:
1. **Listing Module (`listing.py`)**: Uses Playwright to launch a headless browser, navigate to the portal, and apply filters. It handles checking "Bid/RA Status" to load evaluation filters, checking "Bid /RA Awarded", paginating results, and parsing cards using BeautifulSoup.
2. **Detail Module (`detail.py`)**: Responsible for navigating to the details/results pages for each tender and extracting the number of bidders and the winner's details.
3. **Evaluation Module (`evaluation.py`)**: Extracts the detailed breakdown of the technical and financial evaluation tables, listing every seller, their qualification status, rank, bid prices, and buyer remarks.
4. **Main Entrypoint (`main.py`)**: Orchestrates the modules, flattens the multi-layered evaluation rows into a unified schema, normalizes inputs, detects anomalies, and outputs CSV/JSON structures.

## Design Decisions & Technical Solutions
- **Dynamic Content & Filters**: The portal uses AJAX and dynamic client-side rendering. To capture this accurately, Playwright is used to manipulate checkboxes (Ongoing Bids/RA, Bid/RA Status, and Bid /RA Awarded) and wait for the table rows under `#pagi_content` to reload.
- **Robust Field Extraction**: In lists and detail views, dynamic layouts can interleave text across columns if simple string concatenation is used. To resolve this, the scraper maps text elements directly to labels in the DOM, searching for strings like `"Bid No.:"`, `"Items:"`, and `"Quantity:"`, and then traversing to parent/adjacent nodes.
- **Unified Seller-Tender Model**: Instead of maintaining separate entities, the model flattens the details. For each tender, every vendor represents one row. Qualified vendors map to their rank and offered price, while disqualified ones maintain their disqualification flag and buyer remarks.
- **Data Anomaly Identification**: The script normalizes seller names to title case and flags bids. If a bidder with a rank other than "L1" is designated as the winner, the row is flagged as an `anomaly`. Repeated `bid_id` entries are marked as `duplicate`.

## Insights & Lessons Learned
- **Anti-Bot and Robustness**: Public procurement websites like GeM implement rate limits and anti-bot measures. The code incorporates timeouts (`wait_for_timeout`) and try/except wrappers around all network interactions to prevent crashes.
- **Modularity**: Dividing extraction into listing, detail, and evaluation modules ensures that modifications to listing table styling do not affect evaluation table parsers.
