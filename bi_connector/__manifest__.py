{
    'name': 'Power BI Connector — Live & Scheduled Sync',
    'version': '18.0.1.0.0',
    'summary': 'Connect Odoo 18 to Microsoft Power BI with secure token auth, live and scheduled sync',
    'description': """
Power BI Connector for Odoo 18
==============================
Connect your Odoo data to Microsoft Power BI in minutes.

Features:
- Secure token-based authentication
- Live (real-time) and Scheduled (cached) sync per dataset
- Dynamic dataset manager — add any Odoo model without coding
- Supports all Odoo field types including Studio custom fields
- Pagination and date filtering support
- Works on Community and Enterprise
- Endpoints: Purchase, Invoices, Inventory, Projects, HR and more
    """,
    'author': 'Abdul Umar',
    'support': 'umarsheik812@gmail.com',
    'price': 29.00,
    'currency': 'USD',
    'license': 'OPL-1',
    'category': 'Technical/Reporting',
    'depends': [
        'base',
        'purchase',
        'account',
        'stock',
        'project',
        'analytic',
        'hr',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/powerbi_dataset_views.xml',
        'data/default_datasets.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'installable': True,
    'application': True,
}