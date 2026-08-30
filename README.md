# odoo-powerbi-connector
Power BI Connector for Odoo 18
Connect your Odoo 18 data to Microsoft Power BI with secure 
token authentication, live and scheduled sync, and period filtering.

## Features

- 🔒 Secure token-based authentication
- ⚡ Live (real-time) and Scheduled (cached) sync per dataset
- 📅 Period filtering: this_month, last_month, this_year, last_30_days, etc.
- 🗂️ Dynamic dataset manager — add any Odoo model from the UI
- 📦 8 pre-built datasets installed automatically
- ✅ Works on Odoo 18 Community, Enterprise, and Odoo.sh

## Installation

1. Add this repository to your Odoo addons path
2. Install the `powerbi_connector` module from Apps
3. Go to Settings → Power BI → Generate Token
4. In Power BI Desktop → Get Data → Web → Advanced
5. Enter your endpoint URL + X-PowerBI-Token header

## Endpoints

| Dataset | URL | Mode |
|---|---|---|
| Purchase Orders | /powerbi/data/purchase_orders | Live |
| Vendor Bills | /powerbi/data/vendor_bills | Live |
| Customer Invoices | /powerbi/data/customer_invoices | Live |
| Stock Moves | /powerbi/data/stock_moves | Scheduled |
| Projects | /powerbi/data/projects | Live |
| Analytic Lines | /powerbi/data/analytic_lines | Scheduled |
| Vendors | /powerbi/data/vendors | Scheduled |
| Employees | /powerbi/data/employees | Scheduled |
