# 📦 Product Tracking Program

A comprehensive desktop application for managing imports, inventory, sales, expenses, and returns with automated product ID generation and document management.

![Version](https://img.shields.io/badge/version-1.5-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-brightgreen.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## 🚀 Features

### ✨ What's new (Oct 2025)
- Login & Roles: User accounts with PBKDF2 hashing, role-based admin actions
- Audit Log Viewer: Filterable/sortable audit history with CSV export
- Backup/Restore: One-click DB backup and admin-only restore with auto-backup
- FIFO Batch Tracking with per-sale cost and profit (import batches + allocations)
- Currency & FX overhaul:
  - Single FX provider (frankfurter.app) with on-disk cache for rates
  - Configurable Base Currency in Settings (affects analytics and displays)
  - Defaults for import, sale, and expense currencies (override per record)
  - All allocations/analytics computed in Base Currency using transaction-date rates
- Expense dialogs now support linking to multiple imports with a filterable checkbox list (Select All / Clear)
- Monthly/Yearly Analysis window (Revenue, COGS, Gross Profit, Expenses, Net)
- Suppliers directory (CSV-backed) + Manage Suppliers window and import linking
- Customers optional linkage for sales (CSV-backed) + Manage Customers window
- Accessibility upgrades (larger fonts, higher-contrast text) and superhero theme
- Keyboard-friendly dropdown suggestions for Supplier (Imports) and Customer (Sales)
- Modern UI overhaul: ttkbootstrap “Superhero” theme with centralized COLORS/FONTS
- Menubar (File / Reports / Help) + tabbed navigation (Home/Imports/Sales/Expenses/Admin)
- Status bar with DB path and auto-updating current-year Net Profit
- Multi-document managers for Sales, Returns, and Expenses (attach many files)

New in this update:
- Sales CSV header migrated to `SellingPriceBase` (backward-compatible with legacy `SellingPriceUSD`)
- Expenses now have a Currency field; default expense currency in Settings; View Expenses always shows Currency and uses a human-friendly column order
- Refunds integrated into analytics: revenue net of refunds; items returned tracked; restocked returns reverse COGS using exact per-unit allocation cost
- Monthly/Yearly Analysis UI: added Return Impact and Items Returned columns, drill-down for monthly return impact, and a “Net of returns applied” badge
- Batch Analytics: new toggle to “Include import-related expenses in costs,” which apportions linked expenses to imports per unit (in base currency) and adjusts unit cost and profit accordingly
- Fixed allocation unit cost zero bug; historical allocations backfilled and profit/unit recomputed where needed

### 📊 **Complete Business Management**
- **Import Tracking**: Record and manage product imports with supplier details
- **Inventory Management**: Real-time stock tracking with automatic updates
- **Sales Processing**: Record sales with automatic product ID generation
- **Expense Management**: Track business expenses with optional document attachments
- **Returns Handling**: Manage product returns with restock options

### 💹 **Batch Tracking & Profitability**
- **Import Batches (FIFO)**: Every import creates a batch with remaining quantity
- **Sales Allocations**: Each sold item is allocated to specific batch(es)
- **Accurate COGS & Profit**: Per-sale revenue, cost and profit analytics
- **Base-currency analytics**: All costs and revenues normalized to your Base Currency using frankfurter.app rates cached per date
- **Returns Aware**: Optional restock back to original batch(es) with audit trail

### 🏷️ **Smart Product ID System**
- **Automatic ID Generation**: Year-prefixed product IDs (e.g., 25001002-0001)
- **Category Coding**: Unique 3-digit codes for categories and subcategories
- **Serial Management**: Automatic serial number incrementing
- **Warranty Tracking**: Filter by warranty year from product ID prefix

### 📄 **Document Management**
- **Multi-Document Attachments**: Attach multiple files per sale/return/expense
- **Document Manager Dialogs**: Add/Remove/Open selected or all, then Save
- **Native File Picker**: Easy document selection and attachment
- **Cross-Platform Opening**: Open documents with system default applications
- **Path Management**: Automatic absolute path resolution

### 🎛️ **Advanced UI Features**
- **Modern Interface**: Clean, professional design with themed styling
- **Superhero Theme**: ttkbootstrap "Superhero" with ttk fallback; centralized COLORS/FONTS
- **Menubar & Tabs**: Desktop-style menubar plus a notebook with Home/Imports/Sales/Expenses/Admin
- **Status Bar**: Shows DB path and current-year Net Profit (auto-refreshes)
- **Accessible Defaults**: Larger default fonts and higher-contrast text for readability
- **Smart Filtering**: Search, warranty status, and return status filters
- **Column Sorting**: Click headers to sort by any column (dates, numbers, text)
- **Visual Indicators**: Color-coded rows and status indicators
- **Zebra Striping**: Alternating row colors for better readability
 - **Keyboard-friendly Suggestions**: Live dropdowns for Supplier (Imports) and Customer (Sales)
 - **Consistent Window Sizes**: Sensible geometry and minimum sizes across windows so all controls are visible without manual resizing
 - **CSV Export**: Export visible rows from tables with one click
 - **Rounded, Themed Controls**: Consistent buttons and dialogs (ttkbootstrap or styled ttk)

### 🌐 Currency & FX
- Single FX source via frankfurter.app with a local cache to minimize network calls
- Settings window lets you set the Base Currency and defaults for Import, Sale, and Expense currencies
- Amounts are converted at the transaction date; analytics and allocations are stored/derived in Base Currency for consistency
- Sales CSV uses `SellingPriceBase` to make the currency explicit; legacy `SellingPriceUSD` is still read for compatibility

### 🔗 **Directories (Optional Linkage)**
- **Customers (CSV)**: Optional CustomerID on sales; manage in "Manage Customers"
- **Suppliers (CSV)**: Optional supplier linkage from imports; manage in "Manage Suppliers"

## 📋 Requirements

### System Requirements
- **Python**: 3.8 or higher
- **Operating System**: Windows, macOS, or Linux
- **RAM**: 512MB minimum
- **Storage**: 100MB for application and data

### Python Dependencies
```bash
# Core dependencies (built-in)
tkinter          # GUI framework
sqlite3          # Database management
csv              # CSV file handling
pathlib          # Path management
datetime         # Date/time operations
subprocess       # System operations

# Optional theme (recommended)
ttkbootstrap     # Beautiful themes (falls back to ttk if not installed)
```

## 🛠️ Installation

### 1. **Download or Clone**
```bash
git clone <repository-url>
cd Tracking_Program_for_accounting
```

### 2. **Set Up Python Environment** (Optional but recommended)
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. **Install Dependencies**
```bash
pip install -r requirements.txt
```

### 4. **Run the Application**
```bash
python py/main.py
```

## 🧹 Linting (Optional for Development)

Static analysis helps keep the codebase clean and catch issues early. This project supports both Ruff (fast, all‑in‑one) and Flake8.

### 1. Install Dev Dependencies
```bash
pip install -r requirements-dev.txt
```

### 2. Run Ruff (Preferred)
```bash
ruff check py
```
Auto-fix simple issues (unused imports, formatting tweaks):
```bash
ruff check --fix py
```

### 3. (Optional) Run Flake8
```bash
flake8 py
```

Configuration lives in `ruff.toml`. Adjust `select` / `ignore` or add per‑file ignores there as needed.


## 🎯 Quick Start Guide

### First Launch
1. **Start Application**: Run `python py/main.py` (you'll be prompted to create an admin on first run)
2. **Set Up Product Codes**: Go to "Manage Product Codes" to define category codes
3. **Record First Import**: Add your first product import
4. **Make First Sale**: Record a sale to see ID generation in action

### Basic Workflow
1. **📦 Record Import** → Updates inventory automatically
2. **💰 Record Sale** → Generates product IDs, optionally reduces inventory
3. **💳 Record Expense** → Track business costs with documents
4. **↩️ Handle Returns** → Mark sales as returned, optional restocking
5. **🏭 Manage Suppliers** → Optional supplier directory and linking for imports
6. **👥 Manage Customers** → Optional customers directory and linking for sales
7. **📆 Monthly/Yearly Analysis** → Review Revenue/COGS/Profit/Expenses/Net

### Where to find new modules
- Administration → Manage Suppliers
- Administration → Manage Customers
- Administration → Monthly/Yearly Analysis
 - Administration → Audit Log
 - Administration → Backup/Restore

## � Complete Functionality Guide

### 🏠 **Main Dashboard & Navigation**
**Purpose**: Central hub for accessing all application modules
**Location**: First window that opens when starting the application

**Features:**
- **Menubar**: File (Exit), Reports (Batch Analytics, Monthly/Yearly Analysis), Help (About)
- **Tabbed Notebook**: Home / Imports / Sales / Expenses / Admin
- **Status Bar**: DB path on left, current year Net Profit on right
- **Quick Stats Bar**: Displays overview information and recent activity
- **Sectioned Navigation**: Organized into logical business areas:
  - 📦 **Imports & Inventory**: Product procurement and stock management
  - 💰 **Sales & Returns**: Revenue generation and customer returns
  - 💳 **Expenses**: Business cost tracking
  - ⚙️ **Administration**: System configuration and settings
- **Visual Hierarchy**: Primary actions (Record) highlighted, secondary actions (View) subdued
- **Modern Interface**: Clean design with icons and professional styling

**User Actions:**
- Click any button to open the corresponding module
- Access different sections based on current business needs
- Quick navigation between related functions

---

### 📦 **Import Management System**

#### **� Record Import Window**
**Purpose**: Add new product imports to inventory and track supplier relationships

**Input Fields:**
- **Date**: Import date (YYYY-MM-DD format, defaults to today)
- **Category**: Product category (with auto-suggestions from previous imports)
- **Subcategory**: Product subcategory (optional, with auto-suggestions)
- **Ordered Price**: Cost per unit from supplier
- **Quantity**: Number of units imported
- **Supplier**: Vendor/supplier name
- **Notes**: Additional information or specifications

**Smart Features:**
- **Auto-Suggestions**: Dropdown suggestions appear as you type categories/subcategories
- **Product Code Integration**: Automatically prompts for 3-digit codes for new categories
- **Validation**: Ensures proper date format, numeric values for prices/quantities
- **Inventory Integration**: Automatically updates stock levels upon saving

**Workflow:**
1. Enter import details
2. System checks for existing product codes
3. If new category/subcategory, prompts for unique 3-digit codes
4. Saves import record to database
5. Automatically updates inventory quantities
6. Ready for next import entry

#### **📋 View Imports Window**
**Purpose**: Review, search, edit, and delete import records

**Display Features:**
- **Sortable Columns**: Click any header to sort (ID, Date, Category, Price, Quantity, Supplier)
- **Search Function**: Real-time text search across all fields
- **Zebra Striping**: Alternating row colors for easy reading
- **Totals Bar**: Shows total rows, quantities, and costs for filtered results

**Actions Available:**
- **🔄 Refresh**: Reload data from database
- **✏️ Edit**: Modify existing import records
- **🗑️ Delete**: Remove import records (rebuilds inventory)
- **Export**: Save filtered results to CSV (if implemented)

**Edit Functionality:**
- Modify any field in existing import records
- Automatic inventory recalculation when quantities change
- Maintains data integrity and audit trail

---

### 📊 **Inventory Management**

#### **📦 View Inventory Window**
**Purpose**: Monitor current stock levels across all categories and subcategories

**Display Information:**
- **Category**: Product category name
- **Subcategory**: Product subcategory (if applicable)
- **Quantity**: Current stock level (calculated from all imports minus sales)
- **Last Updated**: Timestamp of most recent inventory change

**Features:**
- **Real-Time Updates**: Reflects changes from imports and sales immediately
- **Search Function**: Find specific categories or subcategories quickly
- **Stock Totals**: Summary of total items across all categories
- **Automatic Calculation**: No manual entry required - computed from transactions

**Use Cases:**
- Check stock before making sales
- Identify low-stock items for reordering
- Verify inventory accuracy after imports
- Plan purchasing decisions based on current levels

---

### 💰 **Sales Management System**

#### **🆕 Record Sale Window**
**Purpose**: Process sales transactions with automatic product ID generation

**Form Layout:**
- **Date**: Sale date (defaults to today, YYYY-MM-DD format)
- **Category**: Select from available inventory categories
- **Subcategory**: Auto-populated based on selected category
- **Quantity**: Number of items sold (must be positive integer)
- **Unit Price**: Price per individual item
- **Platform**: Sales channel (Amazon, Etsy, etc. with suggestions)
- **Inventory Reduction**: Checkbox to automatically reduce stock

**Product ID Generation:**
- **Format**: `YYCCCSSSSSSSS` (Year-Category-Subcategory-Serial)
- **Example**: `25001002-0001` (2025, Category 001, Subcategory 002, Serial 0001)
- **Per-Item IDs**: Each sold item gets unique ID (quantity 5 = 5 different IDs)
- **Sequential Numbering**: Automatic serial increment per category/subcategory

**Smart Features:**
- **Inventory Integration**: Categories populated from current stock
- **Stock Validation**: Warns if sale would create negative inventory
- **Platform Memory**: Remembers and suggests previously used platforms
- **Code Management**: Prompts for new category codes when needed

**Workflow:**
1. Select category/subcategory from inventory
2. Enter quantity and pricing
3. Choose platform (with auto-suggestions)
4. System generates individual product IDs
5. Optionally reduces inventory stock
6. Saves one record per item sold
7. Displays generated ID range confirmation

#### **📋 View Sales Window**
**Purpose**: Comprehensive sales record management with advanced filtering

**Advanced Filtering:**
- **Warranty Filter**: Filter by year prefix (25 for 2025, 24 for 2024, etc.)
- **Return Status**: All / Not Returned / Returned items
- **Text Search**: Search across dates, categories, platforms, product IDs
- **Real-Time Updates**: Filters apply immediately as you type

**Table Features:**
- **Professional Layout**: Proper column sizing and alignment
- **Sortable Columns**: Click headers for ascending/descending sort
- **Return Indicators**: Returned items marked with "(Returned)" suffix
- **Document Icons**: Visual indicators for attached documents
- **Totals Display**: Shows filtered item count and total selling price

**Action Buttons:**
- **✏️ Edit**: Modify sale details (blocked for returned items)
- **🔄 Refresh**: Reload data from files
- **� Documents**: Manage multiple attachments (add/remove/open)
- **↩️ Mark Returned**: Process returns with optional restocking
- **🗑️ Delete**: Remove sale records

**Edit Functionality:**
- **Full Field Access**: Modify date, category, pricing, platform, product ID
- **Document Management**: Update attached file paths
- **Return Protection**: Cannot edit sales that have been returned
- **Validation**: Ensures data integrity during modifications

#### **↩️ Mark Returned Functionality**
**Purpose**: Process customer returns with comprehensive tracking

**Return Dialog Fields:**
- **Return Date**: Date of return (defaults to today)
- **Refund Amount**: Optional refund value (can differ from original price)
- **Restock Option**: Checkbox to add item back to inventory
- **Reason**: Text field for return reason (defective, customer change, etc.)
- **Return Document**: Attach return receipt, RMA, or related paperwork

**Smart Restock Logic:**
- **Default Off**: Restock checkbox defaults to unchecked
- **Confirmation Required**: Asks "Product may be broken. Proceed with restock?"
- **Inventory Integration**: If confirmed, adds 1 unit back to inventory
- **Audit Trail**: Records whether item was restocked in returns database

**Return Effects:**
- **Visual Marking**: Product ID shows "(Returned)" suffix in sales view
- **Edit Protection**: Original sale becomes read-only
- **Return Tracking**: Separate return record created for reporting
- **Optional Restocking**: Inventory updated only if explicitly confirmed

#### 📉 Analytics Impact of Returns
- Refunds are netted against revenue in Monthly/Yearly analytics
- Items Returned are tracked and shown in tables
- If a return is restocked, COGS is reversed using the exact per-unit cost from the original sale’s batch allocations
- UI additions:
  - New “Return Impact” and “Items Returned” columns in Monthly/Yearly views
  - Double‑click a month to see a drill-down of refunds and COGS reversals
  - A subtle “Net of returns applied” badge under the tables

---

### 💳 **Expense Management System**

#### **🆕 Record Expense Window**
**Purpose**: Track business expenses with document attachment support

**Input Fields:**
- **Date**: Expense date (YYYY-MM-DD format)
- **Amount**: Expense amount (numeric validation)
- **Currency**: Expense currency (defaults from Settings; required)
- **Import-Related**: Checkbox to enable linking the expense to imports
- **Link to Import(s)**: Scrollable checkbox list of recent imports with live filter and Select All/Clear
- **Category**: Expense category with auto-suggestions from previous expenses
- **Notes**: Additional details or descriptions
- **Attach Document**: Optional receipt, invoice, or supporting documentation

**Category Intelligence:**
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

---

### ♿ Accessibility & Theme
- Larger default fonts and increased contrast for better readability
- ttkbootstrap "superhero" theme if installed; falls back to ttk gracefully
- Treeviews use consistent sizing and zebra striping; color tags highlight states
- Click-to-sort headers and CSV export on all modernized tables
- Themed dialogs replace system prompts for dark-mode legibility

---

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

#### **🎨 Visual Design System**
**Color Coding:**
- **Status Indicators**: Different colors for different item states
- **Return Marking**: Returned items highlighted in warning colors
- **Document Indicators**: Visual cues for items with attachments
- **Low Stock Alerts**: Color coding for inventory concerns (if implemented)

**Layout Features:**
- **Responsive Design**: Adapts to different window sizes
- **Professional Spacing**: Consistent margins and padding
- **Button Hierarchy**: Visual distinction between primary and secondary actions
- **Modern Typography**: Clear, readable fonts with appropriate sizing

#### **📱 Cross-Platform Compatibility**
**File Operations:**
- **Windows**: Uses `os.startfile()` for document opening
- **macOS**: Uses `open` command via subprocess
- **Linux**: Uses `xdg-open` for system default applications
- **Path Handling**: Proper path resolution across operating systems

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
- `imports`: Import records with supplier and pricing data
- `inventory`: Current stock levels by category/subcategory
- `expenses`: Business expenses with optional document paths
- `product_codes`: Category/subcategory code mappings

**CSV Files:**
- `data/sales.csv`: Sales records with generated product IDs
- `data/returns.csv`: Return records with restock information

### Data Location
```
Tracking_Program_for_accounting/
├── data/
│   ├── app.db           # SQLite database
│   ├── sales.csv        # Sales records
│   └── returns.csv      # Returns records
├── py/                  # Application code
└── README.md           # This file
```

### Backup & Migration
**Manual Backup:**
1. Copy entire `data/` folder
2. Store in safe location
3. Restore by replacing `data/` folder

**CSV Export:** Use "Export CSV" buttons in viewers (if implemented)

## ⚡ Performance & Optimization

### Recommended Limits
- **Imports**: 10,000+ records (excellent performance)
- **Sales**: 50,000+ individual items (good performance)
- **Categories**: 100+ categories (no performance impact)
- **File Attachments**: Any size (paths stored, not file contents)

### Performance Tips
- Regular database maintenance (vacuum/analyze)
- Periodic data archiving for very large datasets
- Use filters to limit displayed results in large datasets

## 🔧 Troubleshooting

### Common Issues

**🚫 "Category code already used"**
- Each category must have a unique code
- Check existing mappings in "Manage Product Codes"
- Delete conflicting entry or choose different code

**📁 "File not found" on document open**
- File may have been moved or deleted
- Use "Attach Document" to update path
- Check file permissions and accessibility

**🔢 Product ID generation fails**
- Ensure category/subcategory codes are defined
- Check quantity is positive integer
- Verify database connectivity

**💾 Database locked errors**
- Close other instances of the application
- Restart application
- Check file permissions on `data/app.db`

### Reset Options
**Clear Suggestions:**
```python
# In Python console or script
import py.db as db
db.reset_all_tables(clear_product_codes=False)  # Keep codes
# or
db.delete_database_file()  # Complete reset
```

### Data & Currency Migrations
- Allocation unit cost zero bug fixed; historical allocations have been backfilled and profit/unit recomputed where needed
- Sales CSV header migrated to `SellingPriceBase`; the app still reads `SellingPriceUSD` for older files

## 🎨 Customization

### Themes & Styling
The application uses a modern theme system in `py/ui/theme.py`:
- **Colors**: Modify color palette for different branding
- **Fonts**: Adjust font sizes and families
- **Spacing**: Customize padding and margins
- **Button Styles**: Create custom button appearances

### Adding Features
**Extending Functionality:**
1. **New Modules**: Follow existing patterns in `py/ui/`
2. **Database Changes**: Update `py/db.py` with new tables/columns
3. **UI Integration**: Add buttons to `py/main.py`

## 📝 Development

### Project Structure
```
py/
├── main.py              # Application entry point
├── db.py               # Database operations
└── ui/
    ├── theme.py        # UI theming and styling
    ├── *_window.py     # Individual window modules
    └── view_*.py       # Data viewing modules
```

### Code Standards
- **Python 3.8+** compatibility
- **Type hints** where applicable
- **Error handling** with try/except blocks
- **Consistent styling** following established patterns

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

## 🤝 Support

### Getting Help
1. **Check Troubleshooting** section above
2. **Review Error Messages** for specific guidance
3. **Backup Data** before attempting fixes
4. **Test with Small Dataset** to isolate issues



---

*Last updated: October 2025 | Version 1.0*