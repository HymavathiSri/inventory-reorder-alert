# Inventory Reorder Alert System
import csv
import sys
from datetime import datetime
from pathlib import Path

# Now Configuration Setting
CRITICAL_RATIO = 0.25   # below 25% of threshold = "Critical"
TARGET_STOCK_MULTIPLIER = 1.5  # reorder up to 150% of threshold ("healthy" level)

# Step 1: # Load inventory data from the CSV file
def load_stock_data(filepath):
    """
    Reads the stock CSV and returns a list of dicts, one per row.
    Keeps the raw string values here -- cleaning/validation happens
    separately so we can report on bad rows instead of silently
    dropping them.
    """
    rows = []
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, raw_row in enumerate(reader, start=2):  # start=2: header is row 1
            raw_row["_row_number"] = i
            rows.append(raw_row)
    return rows

# Step 2: Validate and clean inventory records
def parse_item(raw_row):
    """
    Attempts to turn a raw CSV row into a clean item dict:
        {sku, item_name, quantity, threshold}

    Returns (item_dict, error_message).
    Exactly one of the two will be None.

    Handles:
      - missing/blank quantity or threshold
      - non-numeric quantity or threshold
      - negative quantity (data-entry error, e.g. a scanner glitch)
      - missing item name / sku
    """
    sku = (raw_row.get("sku") or "").strip()
    name = (raw_row.get("item_name") or "").strip()
    qty_raw = (raw_row.get("quantity") or "").strip()
    threshold_raw = (raw_row.get("threshold") or "").strip()
    row_num = raw_row.get("_row_number", "?")

    if not sku or not name:
        return None, f"Row {row_num}: missing SKU or item name -- skipped."

    if not qty_raw:
        return None, f"Row {row_num} ({sku}): missing quantity -- skipped, needs manual check."

    if not threshold_raw:
        return None, f"Row {row_num} ({sku}): missing reorder threshold -- skipped, needs manual check."

    try:
        quantity = int(float(qty_raw))
    except ValueError:
        return None, f"Row {row_num} ({sku}): quantity '{qty_raw}' is not a number -- skipped."

    try:
        threshold = int(float(threshold_raw))
    except ValueError:
        return None, f"Row {row_num} ({sku}): threshold '{threshold_raw}' is not a number -- skipped."

    corrected_negative = False
    if quantity < 0:
        # Negative stock isn't physically real -- likely a scan/count error.
        # Auto-correct it to 0 (treat as out of stock) so the item still
        # gets evaluated and included in the reorder report, rather than
        # being dropped from the scan entirely.
        quantity = 0
        corrected_negative = True

    if threshold <= 0:
        return None, f"Row {row_num} ({sku}): threshold is zero or negative -- skipped, can't evaluate."

    item = {
        "sku": sku,
        "item_name": name,
        "quantity": quantity,
        "threshold": threshold,
    }

    if corrected_negative:
        # Not a fatal error -- the item is still returned and processed --
        # but we surface a note so the bad scan gets looked at by a human.
        note = f"Row {row_num} ({sku}): negative quantity auto-corrected to 0 -- treated as out of stock, please verify count."
        return item, note

    return item, None


def clean_stock_data(raw_rows):
    """
    Splits raw rows into (good_items, warnings).
    Note: a row can produce BOTH an item and a warning -- e.g. a negative
    quantity gets auto-corrected to 0 and still processed, but also logged
    as a warning so the bad scan gets reviewed by a human.
    """
    good_items = []
    warnings = []
    for raw_row in raw_rows:
        item, note = parse_item(raw_row)
        if item:
            good_items.append(item)
        if note:
            warnings.append(note)
    return good_items, warnings

# Step 3: Conditional logic -- classify stock status + reorder suggestion
def classify_item(item):
    """
    Adds 'status' and 'suggested_reorder_qty' to an item dict based on
    quantity vs threshold.

    Status levels:
      - "In Stock": quantity >= threshold
      - "Low":      below threshold but above 25% of threshold
      - "Critical": at or below 25% of threshold (or zero)
    """
    qty = item["quantity"]
    threshold = item["threshold"]
    critical_cutoff = threshold * CRITICAL_RATIO

    if qty >= threshold:
        status = "In Stock"
        reorder_qty = 0
    elif qty <= critical_cutoff:
        status = "Critical"
    else:
        status = "Low"

    if status in ("Critical", "Low"):
        target_level = threshold * TARGET_STOCK_MULTIPLIER
        reorder_qty = max(0, round(target_level - qty))

    item["status"] = status
    item["suggested_reorder_qty"] = reorder_qty
    return item


def scan_inventory(items):
    """Runs classify_item over every item; returns the same list, enriched."""
    return [classify_item(item) for item in items]

# Step 4: Reporting
def print_console_report(items, warnings):
    flagged = [i for i in items if i["status"] != "In Stock"]
    critical = [i for i in flagged if i["status"] == "Critical"]
    low = [i for i in flagged if i["status"] == "Low"]

    print("=" * 60)
    print("  RESTOCK NEEDED REPORT")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    if not flagged:
        print("\nAll items are sufficiently stocked. No action needed.\n")
    else:
        if critical:
            print(f"\n CRITICAL ({len(critical)} item(s) -- reorder immediately)")
            print("-" * 60)
            for i in critical:
                print(f"  [{i['sku']}] {i['item_name']}")
                print(f"      Current: {i['quantity']}  |  Threshold: {i['threshold']}  "
                      f"|  Suggested reorder: +{i['suggested_reorder_qty']} units")

        if low:
            print(f"\n LOW ({len(low)} item(s) -- reorder soon)")
            print("-" * 60)
            for i in low:
                print(f"  [{i['sku']}] {i['item_name']}")
                print(f"      Current: {i['quantity']}  |  Threshold: {i['threshold']}  "
                      f"|  Suggested reorder: +{i['suggested_reorder_qty']} units")

    if warnings:
        print(f"\n DATA WARNINGS ({len(warnings)} row(s) flagged -- needs manual review)")
        print("-" * 60)
        for w in warnings:
            print(f"  - {w}")

    in_stock_count = len(items) - len(flagged)
    print("\n" + "-" * 60)
    print(f"Summary: {len(items)} items scanned | "
          f"{in_stock_count} in stock | {len(low)} low | {len(critical)} critical | "
          f"{len(warnings)} row(s) flagged for data issues")
    print("=" * 60 + "\n")


def write_csv_report(items, output_path):
    """Writes only the flagged (Low/Critical) items to a CSV report."""
    flagged = [i for i in items if i["status"] != "In Stock"]
    # Sort so Critical items are on top -- most actionable first.
    flagged.sort(key=lambda i: (i["status"] != "Critical", i["item_name"]))

    fieldnames = ["sku", "item_name", "quantity", "threshold", "status", "suggested_reorder_qty"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i in flagged:
            writer.writerow({k: i[k] for k in fieldnames})
    return len(flagged)


def build_email_alert(items):
    """
    Formats the restock report as a simulated email (subject + body).
    In a real system this would be sent via smtplib / an email API --
    here we just build and print the text, mimicking that output.
    """
    flagged = [i for i in items if i["status"] != "In Stock"]
    critical = [i for i in flagged if i["status"] == "Critical"]
    low = [i for i in flagged if i["status"] == "Low"]

    if not flagged:
        subject = "Inventory Check: All Stock Levels Healthy"
        body_lines = ["Good news -- today's inventory scan found no items below threshold."]
    else:
        subject = f"Restock Alert: {len(critical)} Critical, {len(low)} Low Item(s)"
        body_lines = [
            f"Automated inventory scan for {datetime.now().strftime('%B %d, %Y')}.",
            "",
            "The following items need attention:",
            "",
        ]
        if critical:
            body_lines.append("CRITICAL:")
            for i in critical:
                body_lines.append(
                    f"  - {i['item_name']} ({i['sku']}): {i['quantity']} left, "
                    f"reorder {i['suggested_reorder_qty']} units"
                )
            body_lines.append("")
        if low:
            body_lines.append("LOW:")
            for i in low:
                body_lines.append(
                    f"  - {i['item_name']} ({i['sku']}): {i['quantity']} left, "
                    f"reorder {i['suggested_reorder_qty']} units"
                )
            body_lines.append("")
        body_lines.append("Please review and place purchase orders as needed.")

    body = "\n".join(body_lines)
    return subject, body


def print_email_alert(subject, body):
    print("=" * 60)
    print("  SIMULATED EMAIL ALERT")
    print("=" * 60)
    print(f"To: warehouse-manager@example.com")
    print(f"From: inventory-bot@example.com")
    print(f"Subject: {subject}")
    print("-" * 60)
    print(body)
    print("=" * 60 + "\n")


# Main
def main():
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "inventory_stock.csv"

    if not csv_path.exists():
        print(f"Error: could not find stock file at '{csv_path}'")
        sys.exit(1)

    raw_rows = load_stock_data(csv_path)
    clean_items, warnings = clean_stock_data(raw_rows)
    scanned_items = scan_inventory(clean_items)

    print_console_report(scanned_items, warnings)

    output_path = Path(__file__).parent / "restock_report.csv"
    flagged_count = write_csv_report(scanned_items, output_path)
    print(f"Restock report written to: {output_path}  ({flagged_count} item(s))\n")

    subject, body = build_email_alert(scanned_items)
    print_email_alert(subject, body)


if __name__ == "__main__":
    main()
