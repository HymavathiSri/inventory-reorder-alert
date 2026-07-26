# Inventory Reorder Alert System
## Overview

This project is a simple Python application that monitors inventory stock levels and identifies items that need to be reordered. It reads stock information from a CSV file, checks each item's quantity against its reorder threshold, and generates a report for low or critical stock items.

## Features

* Reads inventory data from a CSV file.
* Validates and cleans inventory records.
* Classifies items as **In Stock**, **Low**, or **Critical**.
* Suggests reorder quantities for low-stock items.
* Displays a console report.
* Exports a restock report as a CSV file.
* Generates a simulated email alert.

## Files

* **inventory_stock.csv** – Input inventory data.
* **restock_report.csv** – Generated report containing items that require restocking.
* **main Python file** – Contains the inventory processing logic.

## How It Works

1. Load inventory data from the CSV file.
2. Validate and clean the input data.
3. Check stock levels against reorder thresholds.
4. Generate stock status and reorder suggestions.
5. Display the results in the console.
6. Save the restock report.
7. Generate a simulated email notification.

## Requirements

* Python 3.x
* CSV file containing inventory data

## Purpose

The goal of this project is to demonstrate file handling, data validation, conditional logic, reporting, and basic automation concepts using Python in a simple inventory management scenario.
