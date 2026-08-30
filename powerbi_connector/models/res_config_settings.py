# Copyright 2026 Umar — Power BI Connector
# License OPL-1 — https://www.odoo.com/documentation/legal/licenses.html
import secrets
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    """
    Extends Odoo's Settings page to add Power BI configuration.

    WHY TransientModel?
    Settings in Odoo are always TransientModel — they are temporary records
    that read/write to ir.config_parameter (a permanent key-value store).
    The 'config_parameter' attribute on each field handles this automatically.
    """
    _inherit = 'res.config.settings'

    powerbi_api_token = fields.Char(
        string='API Token',
        config_parameter='powerbi_connector.api_token',
        readonly=True,
        help='Secret token Power BI uses to authenticate. Never share publicly.',
    )

    powerbi_base_url = fields.Char(
        string='Base URL',
        compute='_compute_base_url',
        help='The base URL of your Odoo instance — prefix all endpoints with this.',
    )

    powerbi_cache_ttl = fields.Integer(
        string='Cache Duration (minutes)',
        config_parameter='powerbi_connector.cache_ttl',
        default=60,
        help='How long cached data is kept before the next scheduled sync re-fetches it.',
    )

    @api.depends()
    def _compute_base_url(self):
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        for rec in self:
            rec.powerbi_base_url = base

    def action_generate_token(self):
        """Generate a cryptographically secure random token (256-bit entropy)."""
        token = secrets.token_hex(32)
        self.env['ir.config_parameter'].sudo().set_param(
            'powerbi_connector.api_token', token
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Token Generated',
                'message': 'New API token created. Copy it from the settings page.',
                'type': 'success',
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

    def action_revoke_token(self):
        """Revoke the current token. All Power BI connections will fail until a new one is generated."""
        self.env['ir.config_parameter'].sudo().set_param(
            'powerbi_connector.api_token', ''
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Token Revoked',
                'message': 'API token revoked. Generate a new one to reconnect.',
                'type': 'warning',
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }
