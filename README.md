# Tracking Program for Accounting

A simple desktop app to track imports, inventory, sales, expenses, returns, and documents. Built with Python (Tkinter + ttk/ttkbootstrap) and SQLite/CSV.

> Note: This is my personal side project and it’s under active development.

## Highlights
- Imports, Sales, Expenses, Returns with multi‑document attachments
- FIFO batch tracking with per‑sale cost/profit and optional expense apportion
- Base currency and date‑based FX rates (Frankfurter) with local cache
- Suppliers and Customers directories (optional linkage)
- Consistent, themed UI with sortable/searchable tables
- Login with hashed passwords and audit log (admin features in UI)

## Requirements
- Python 3.10+
- macOS/Windows/Linux
- Optional: ttkbootstrap for nicer theming (falls back to ttk)

## Install
```bash
# Clone

cd Tracking_Program_for_accounting

# (Optional) create venv
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install deps
pip install -r requirements.txt
```

## Run
```bash
python main.py
```
On first launch you’ll be prompted to create an admin user.

## Data locations
- Database: `data/app.db`
- CSVs (legacy/interop): `data/sales.csv`, `data/returns.csv`, etc.
- Documents: stored as file paths; opened with the OS default app

## Core concepts
- Product IDs: year‑prefixed, category/subcategory coded (auto‑generated)
- Batch analytics: allocations from imports (FIFO) drive COGS and profit
- FX handling: amounts normalized to Base Currency using transaction‑date rate

## UI tips
- Use the toolbar or tabs (Home/Imports/Sales/Expenses/Admin)
- Buttons are themed: Primary (Save/Refresh), Secondary (Cancel/Close), Success (Edit/Confirm), Danger (Delete)
- Tables support search, sort, and CSV export (where available)

## Troubleshooting
- If the window appears small, use the window’s green maximize button (macOS) or the maximize control (Windows/Linux). Most windows set sensible minimum sizes.
- If FX fetch fails, you can enter the rate manually; cached rates are used on subsequent runs.

## Development
## Development
- Project layout:
  - `core/` – cross‑cutting utilities (e.g., FX)
  - `db/` – database and business logic
  - `ui/` – Tkinter windows and theming
  - `data/` – SQLite DB and CSV files

## License
MIT
For a full tour of every screen, see the UI and code; this README stays focused and short.
- **Expense-Only Suggestions**: Category dropdown shows only expense categories (not import categories)
- **Smart Filtering**: Maintains separate category spaces for different business areas
- **Auto-Complete**: Suggests categories as you type based on expense history

**Import Linking:**
- **Optional Connection**: Link expenses to specific import records
- **Multi-linking**: Select one or many imports to associate the expense via checkboxes
- **Live Filter**: Quickly narrow the import list by typing keywords (quick filter above the checkbox list)
- **Relationship Tracking**: Maintains connections via a dedicated link table
 - **Clean UI**: Import selection is hidden when not import-related

**Document Support:**
- **Native File Picker**: Browse and select files using system dialog
- **Path Resolution**: Automatically converts to absolute paths where possible
- **Multiple Formats**: Supports any file type (PDFs, images, spreadsheets)

#### **📋 View Expenses Window**
**Purpose**: Comprehensive expense record management and analysis

**Display Features:**
- **Complete Record View**: All expense fields in sortable table format
- **Always-visible Currency**: Currency is always shown for clarity (legacy rows may show blank)
- **Smart Sorting**: Numeric columns (amounts) sort numerically, dates chronologically
- **Search Functionality**: Real-time search across all expense fields
- **Totals Summary**: Shows filtered row count and total expense amount
 - **Readable Columns**: Date, Category, Subcategory, Amount, Currency, Notes, Document

**Document Management:**
- **📎 Attach Document**: Add or replace document for selected expense
- **📄 Open Document**: Launch attached files with system applications
- **Path Validation**: Checks file existence before attempting to open
- **Cross-Platform**: Works on Windows (startfile), macOS (open), Linux (xdg-open)

**Action Capabilities:**
- **✏️ Edit**: Comprehensive editing dialog with all fields
- **🗑️ Delete**: Remove expense records with confirmation
- **🔄 Refresh**: Reload from database
- **📂 Documents**: Add/Remove/Open multiple files per expense

**Edit Dialog Features:**
- **All Fields Editable**: Date, amount, import linking, category, notes, documents
- **Import Linking (Checkboxes)**: Easily add/remove linked imports using the same filterable list
- **Category Suggestions**: Expense-specific category auto-complete
- **Document Browse**: Update attached file paths with file picker
- **Validation**: Date format checking, numeric amount validation

---

### 🔄 **Returns Management System**

#### **📋 View Returns Window**
**Purpose**: Dedicated return record management and analysis

**Return Information Display:**
- **Return Details**: Date, Product ID, original sale information
- **Financial Data**: Original prices, refund amounts
- **Operational Info**: Restock status, return reason, documentation
- **Audit Trail**: Complete history of return processing

**Management Features:**
- **Search Function**: Find returns by any field (Product ID, date, reason)
- **Totals Analysis**: Total returns count and refund amounts
- **Edit Capability**: Modify return details (non-core fields only)
- **Delete Option**: Remove return records (with confirmation)
- **📂 Documents**: Manage multiple attachments for returns

**Edit Restrictions:**
- **Core Fields Protected**: Cannot change Product ID, original sale data
- **Modifiable Fields**: Return date, refund amount, restock status, reason, documentation
- **Data Integrity**: Maintains connection to original sale record

---

### ⚙️ **Administration System**

#### **🔧 Manage Product Codes Window**
**Purpose**: Configure the foundation of the product ID system

**Code Management:**
- **Category Codes**: 3-digit codes for product categories (001, 002, etc.)
- **Subcategory Codes**: 3-digit codes for subcategories within categories
- **Serial Management**: Next serial number for each category/subcategory pair
- **Uniqueness Enforcement**: Database-level constraints prevent code conflicts

**Interface Features:**
- **Sortable List**: View all current code mappings
- **Add New Codes**: Create category/subcategory code pairs
- **Edit Existing**: Modify codes and serial numbers
- **Reset Serials**: Change next serial number for ID generation
- **Delete Codes**: Remove unused category/subcategory mappings

**Validation Rules:**
- **Category Consistency**: Each category must have exactly one code
- **Code Uniqueness**: No code can be used by multiple categories
- **Subcategory Rules**: Within a category, each subcategory needs unique code
- **Serial Management**: Serial numbers must be positive integers

**Code Format:**
- **Auto-Padding**: Codes automatically zero-padded to 3 digits
- **Range**: Supports 001-999 for maximum flexibility
- **Display**: Shows as zero-padded for consistency

---

#### 🏭 Manage Suppliers Window
**Purpose**: Maintain an optional supplier directory and see purchase totals

**Features:**
- Add/Edit/Delete suppliers (name, contact info, address, payment terms, notes)
- Auto-link imports: typing a supplier name on Record Import finds/creates it
- Stats per supplier: Import count, Total purchases, Last purchase date

**How to open:** Administration → Manage Suppliers

---

#### 👥 Manage Customers Window
**Purpose**: Maintain an optional customer directory tied to sales

**Features:**
- Add/Edit/Delete customers (name, contact info, address, notes)
- Sales summary: sales count, total revenue, last sale
- Optional linkage: entering a customer name in Record Sale auto-creates/links

**How to open:** Administration → Manage Customers

---

#### 📆 Monthly/Yearly Analysis
**Purpose**: High-level financial overview by month and year

**Monthly Overview:**
- Revenue, COGS, Gross Profit, Expenses, Net Profit, Imports Value (in base currency), Items Sold, and Items Returned per month (Jan–Dec)
- Totals row and color-coding for quick signals

**Yearly Summary:**
- Revenue, COGS, Gross Profit, Expenses, Net Profit, Imports Value (in base currency), Items Sold, Items Returned

Notes:
- Both imports value and expenses are displayed in Base Currency (converted by date)
- Tables show return impact fields and include a drill‑down for monthly return details

**How to open:** Administration → Monthly/Yearly Analysis

---

### 🗃️ Data Storage Overview
- **SQLite (data/app.db)**
  - imports, inventory, expenses, product_codes
  - users (login), audit_log (history)
  - import_batches (batches) and sale_batch_allocations (sales-to-batch links)
- **CSV (data/)**
  - sales.csv, returns.csv
  - customers.csv (optional), suppliers.csv (optional)

This hybrid model keeps analytics consistent and still allows lightweight CSV exports.

CSV compatibility:
- Sales header field `SellingPriceBase` is preferred; legacy `SellingPriceUSD` is still supported for backward compatibility


### 🧠 Tips
- On Record Import and Record Sale, type in Supplier/Customer fields to see live suggestions.
- If a category/subcategory is new, the app will ask for 3‑digit codes once, then auto-generate IDs.
- Expenses can be linked to imports; documents can be attached and opened via the app.

### 📊 Batch Analytics (Reports → Batch Analytics)
**Purpose:** Deep dive into utilization and profitability by import batch and by product

**Key features:**
- Batch Utilization view with used %, cost allocated, revenue, and profit
- Sale Profit Analysis view grouped by product with totals and margin
- Allocation Details view for precise FIFO tracing per sale
- New toggle: “Include import-related expenses in costs”
  - When enabled, expenses linked to an import are converted to base currency (by date), apportioned evenly per unit across that import’s total original quantity, and added to the effective unit cost
  - Affects batch cost allocated, product total cost, profits, and margins

### 🎨 **User Interface Features**

#### **🎛️ Advanced Filtering System**
**Search Capabilities:**
- **Real-Time Search**: Results update as you type
- **Multi-Field Search**: Searches across multiple columns simultaneously
- **Case-Insensitive**: Finds matches regardless of capitalization
- **Partial Matching**: Finds partial word matches within fields

**Specialized Filters:**
- **Warranty Year Filter**: Uses product ID year prefix for warranty tracking
- **Return Status Filter**: Shows all, returned only, or non-returned items
- **Date Range Options**: Filter by specific time periods (if implemented)

#### **📊 Column Sorting System**
**Smart Sorting Logic:**
- **Date Intelligence**: Recognizes YYYY-MM-DD format for chronological sorting
- **Numeric Sorting**: Properly sorts numbers (10 comes after 9, not after 1)
- **Text Sorting**: Alphabetical sorting for text fields
- **Toggle Direction**: Click again to reverse sort order

**Visual Indicators:**
- **Sort State Memory**: Remembers sort direction per column
- **Column Highlighting**: Visual feedback on sorted column (if implemented)

---

### 💾 **Data Management System**

#### **🗄️ Database Architecture**
**SQLite Tables:**
- **imports**: Supplier relationships, pricing, quantities, dates
- **inventory**: Real-time stock calculation from import/sale transactions
- **expenses**: Business costs with optional import linking and documents
- **product_codes**: Category/subcategory code mappings and serial management

**CSV Files:**
- **sales.csv**: Individual item records with generated product IDs
- **returns.csv**: Return processing records with restock information

#### **🔄 Data Synchronization**
**Automatic Updates:**
- **Inventory Recalculation**: Updates when imports or sales change
- **Product ID Generation**: Maintains sequential numbering automatically
- **Cross-Reference Integrity**: Maintains relationships between related records

**Migration Support:**
- **Schema Updates**: Automatically adds new columns to existing databases
- **CSV Header Migration**: Updates file formats transparently
- **Backward Compatibility**: Handles data from previous versions

This comprehensive functionality guide covers every feature, interaction, and capability in your Product Tracking Program, providing users with complete understanding of how to leverage all aspects of the system for their business management needs.

### 📦 Import Management
**Recording Imports:**
- **Auto-suggestions**: Previous categories and subcategories suggested
- **Code Prompting**: System requests codes for new categories
- **Inventory Integration**: Stock automatically updated on save
- **Supplier Tracking**: Record supplier information and notes

**Validation:**
- Date format validation (YYYY-MM-DD)
- Numeric validation for prices and quantities
- Category code consistency enforcement

### 💰 Sales Processing
**Smart Sales Recording:**
- **Inventory Integration**: Categories populated from current stock
- **Platform Suggestions**: Previous platforms suggested (Amazon, Etsy, etc.)
- **Quantity Validation**: Must be positive integers for ID generation
- **Inventory Reduction**: Optional automatic stock decrement

**Product ID Generation:**
- One ID per item sold (quantity 5 = 5 unique IDs)
- Year prefix from sale date
- Sequential serial numbers
- Format: `YYCCCSSSSSSSS` (Year-Category-Subcategory-Serial)

### 📊 Advanced Filtering & Search
**View Sales Filters:**
- **Warranty Filter**: Filter by year prefix (25, 24, etc.)
- **Return Status**: All / Not Returned / Returned
- **Text Search**: Search across dates, categories, platforms, IDs

**Sorting:**
- Click any column header to sort
- Smart type detection (dates, numbers, text)
- Toggle ascending/descending with repeated clicks

### 🔄 Returns Management
**Marking Returns:**
1. Select sale in "View Sales"
2. Click "Mark Returned"
3. Enter return details:
   - Return date
   - Refund amount (optional)
   - Restock checkbox (with confirmation)
   - Reason and documentation

**Return Effects:**
- Product ID marked as "(Returned)" in sales view
- Original sale becomes read-only
- Optional inventory restocking with confirmation
- Separate returns tracking and management

### 📄 Document Attachments
**Supported Operations:**
- **Attach**: Use "Browse..." buttons in record/edit forms
- **Open**: Click "Open Document" buttons in viewers
- **Cross-Platform**: Works on Windows, macOS, and Linux

**File Management:**
- Absolute path storage when possible
- Native system file picker integration
- System default application launching

## 🗂️ Data Management

### Database Structure
**SQLite Tables:**
- `imports`, `inventory`, `expenses`, `product_codes`
- `users` (authentication), `audit_log` (history)
- `import_batches`, `sale_batch_allocations` (FIFO cost tracking)

**CSV Files:**
- `data/sales.csv` (sales records, product IDs)
- `data/returns.csv` (returns with restock & refund info)
- `data/customers.csv`, `data/suppliers.csv` (optional linkage directories)

### Data Location
```
Tracking_Program_for_accounting/
├── data/
│   ├── app.db
│   ├── sales.csv
│   ├── returns.csv
│   ├── customers.csv (optional)
│   └── suppliers.csv (optional)
├── db/
├── core/
├── ui/
└── main.py
```

### Backup & Migration
**Manual Backup:**
1. Copy entire `data/` folder
2. Store in safe location
3. Restore by replacing `data/` folder

### Reset Options
**Clear Suggestions:**
```python
# In Python console or script
import db.db as db
db.reset_all_tables(clear_product_codes=False)  # Keep codes
# or
db.delete_database_file()  # Complete reset
```

### Data & Currency Migrations
- Allocation unit cost zero bug fixed; historical allocations have been backfilled and profit/unit recomputed where needed
- Sales CSV header migrated to `SellingPriceBase`; the app still reads `SellingPriceUSD` for older files


## 📝 Development

### Project Structure
```
main.py               # Application entry point
db/db.py              # Database + business logic
core/fx_rates.py      # FX retrieval & caching
core/crypto_utils.py  # Optional encryption helpers
ui/theme.py           # UI theming and styling
ui/*_window.py        # Form & management windows
ui/view_*.py          # Data viewing windows
data/                 # SQLite DB + CSV data files
```

## 📄 License

This project is licensed under the MIT License - see below for details:

```
MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
```

---

*Last updated: October 2025 | Version 1.0*