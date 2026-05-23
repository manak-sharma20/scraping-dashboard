# GeM Portal Bid Results Scraper

A modular Python-based web scraper that filters, paginates, and extracts awarded procurement bid data from the Government e-Marketplace (GeM) portal (https://bidplus.gem.gov.in/all-bids).

## Project Structure
```text
gemedge-scraper/
├── scraper/
│   ├── __init__.py
│   ├── listing.py       # Apply filters & extract bid lists with pagination
│   ├── detail.py        # Extract bid winner price, name, and bidder counts
│   └── evaluation.py   # Extract seller-wise ranking & disqualification logs
├── data/
│   ├── output.csv       # Flattened output data in CSV format
│   ├── output.json      # Flattened output data in JSON format
│   └── summary.txt      # Automated insights report
├── main.py              # Scraper orchestration, cleaning, and metric compilation
├── requirements.txt     # Python library dependencies
├── README.md            # Execution and architecture guide
└── writeup.md           # Implementation write-up and design decisions
```

## Setup & Installation

1. **Python Environment**:
   Ensure you have Python 3.10+ installed on your system.

2. **Install Dependencies**:
   Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Playwright Browsers**:
   Download the Chromium binaries needed for Playwright execution:
   ```bash
   python -m playwright install chromium
   ```

## How to Run

Execute the main scraper script to start the extraction pipeline:
```bash
python main.py
```

## Output Features
- **CSV/JSON Datasets (`data/output.csv`, `data/output.json`)**: Contains flattened records containing:
  - `bid_id`, `bid_no`, `ra_no`, `category`, `buyer`, `quantity`, `bid_value`, `start_date`, `end_date`
  - `winner_name`, `winner_price`, `num_bidders`
  - `vendor_name`, `vendor_rank`, `vendor_price`, `disqualified`, `remarks`
  - `status_flag` (`anomaly` if L1 was not the winner, `duplicate` if repeated, else `clean`)
- **Automated Summary Report (`data/summary.txt`)**: Stores metrics detailing:
  - Percentage of bids with >3 participating bidders
  - Average price gap between L1 and L2 bidders
  - Repeating winner names (sellers with more than 2 wins)
