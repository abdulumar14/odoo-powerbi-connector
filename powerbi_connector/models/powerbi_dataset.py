# Copyright 2026 Umar — Power BI Connector
# License OPL-1 — https://www.odoo.com/documentation/legal/licenses.html
from odoo import api, fields, models
import json
import logging

_logger = logging.getLogger(__name__)


class PowerBIDataset(models.Model):
    """
    Represents one Power BI dataset — e.g. "Purchase Orders" or "Vendor Bills".

    Each dataset has:
    - A technical endpoint key (URL slug)
    - A sync mode: 'live' or 'scheduled'
    - A date_field used for period/date filtering
    - For scheduled mode: a JSON cache + last_sync timestamp
    - Active flag to enable/disable without deleting
    """
    _name = 'powerbi.dataset'
    _description = 'Power BI Dataset'
    _order = 'name'

    name = fields.Char(
        string='Dataset Name',
        required=True,
        help='Friendly name shown in Power BI. E.g. "Purchase Orders"',
    )

    endpoint_key = fields.Char(
        string='Endpoint Key',
        required=True,
        help='URL slug for this dataset. E.g. "purchase_orders" → /powerbi/data/purchase_orders',
    )

    odoo_model = fields.Char(
        string='Odoo Model',
        required=True,
        help='Technical model name. E.g. "purchase.order"',
    )

    fields_to_export = fields.Text(
        string='Fields to Export',
        required=True,
        help='Comma-separated list of field names to include in the JSON response.',
    )

    domain_filter = fields.Text(
        string='Domain Filter',
        default='[]',
        help='Odoo domain to filter records. JSON format. E.g. [["state","=","posted"]]',
    )

    # ── DATE FIELD (used for period filtering) ────────────────────────────
    date_field = fields.Char(
        string='Date Field',
        default='date',
        help=(
            'Field used when Power BI passes ?period= or ?date_from= / ?date_to= params.\n'
            'Common values:\n'
            '  purchase.order       → date_order\n'
            '  account.move         → invoice_date\n'
            '  stock.move           → date\n'
            '  account.analytic.line → date\n'
            '  project.project      → date_start\n'
            '  hr.employee          → create_date'
        ),
    )

    sync_mode = fields.Selection(
        selection=[
            ('live', 'Live (real-time)'),
            ('scheduled', 'Scheduled (cached)'),
        ],
        string='Sync Mode',
        required=True,
        default='live',
        help=(
            'Live: every Power BI request queries Odoo directly.\n'
            'Scheduled: data is cached in DB and refreshed on a schedule. '
            'Faster for large datasets.'
        ),
    )

    active = fields.Boolean(default=True)

    # ── CACHE FIELDS (scheduled mode only) ───────────────────────────────
    cached_data = fields.Text(
        string='Cached Data',
        help='JSON cache of the last sync. Only used in Scheduled mode.',
    )
    last_sync = fields.Datetime(
        string='Last Synced',
        help='When the cache was last refreshed.',
    )
    record_count = fields.Integer(
        string='Records Cached',
        compute='_compute_record_count',
        store=False,
    )

    @api.depends('cached_data')
    def _compute_record_count(self):
        for rec in self:
            if rec.cached_data:
                try:
                    data = json.loads(rec.cached_data)
                    rec.record_count = len(data)
                except Exception:
                    rec.record_count = 0
            else:
                rec.record_count = 0

    def get_fields_list(self):
        """Parse comma-separated fields_to_export into a clean Python list."""
        return [f.strip() for f in (self.fields_to_export or '').split(',') if f.strip()]

    def get_domain(self):
        """Parse domain_filter JSON string into a Python list."""
        try:
            return json.loads(self.domain_filter or '[]')
        except Exception:
            _logger.warning('PowerBI Dataset %s: invalid domain filter, using []', self.name)
            return []

    def action_sync_now(self):
        """Manually trigger a cache refresh for this dataset."""
        for dataset in self:
            dataset._refresh_cache()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Sync Complete',
                'message': f'Dataset "{self.name}" refreshed successfully.',
                'type': 'success',
            }
        }

    def _refresh_cache(self):
        """
        Fetch fresh data from the Odoo model and store as JSON in cached_data.
        Called by action_sync_now() and the scheduled cron job.
        """
        self.ensure_one()
        _logger.info('PowerBI: refreshing cache for dataset "%s"', self.name)
        try:
            # Validate model exists before querying
            if self.odoo_model not in self.env:
                raise ValueError(f'Model "{self.odoo_model}" not found in this Odoo instance.')

            Model = self.env[self.odoo_model].sudo()
            records = Model.search_read(
                domain=self.get_domain(),
                fields=self.get_fields_list(),
            )
            from odoo.addons.powerbi_connector.controllers.main import PowerBIController
            cleaned = PowerBIController._clean_static(records)
            self.write({
                'cached_data': json.dumps(cleaned, default=str),
                'last_sync': fields.Datetime.now(),
            })
            _logger.info('PowerBI: cached %d records for "%s"', len(records), self.name)
        except Exception as e:
            _logger.error('PowerBI: cache refresh failed for "%s": %s', self.name, str(e))
            raise

    @api.model
    def cron_refresh_all_scheduled(self):
        """
        Entry point for the scheduled cron job.
        Refreshes all active datasets with sync_mode = 'scheduled'.
        """
        datasets = self.search([
            ('sync_mode', '=', 'scheduled'),
            ('active', '=', True),
        ])
        _logger.info('PowerBI cron: refreshing %d scheduled datasets', len(datasets))
        for dataset in datasets:
            try:
                dataset._refresh_cache()
            except Exception as e:
                _logger.error(
                    'PowerBI cron: skipping "%s" due to error: %s',
                    dataset.name, str(e)
                )
                continue
