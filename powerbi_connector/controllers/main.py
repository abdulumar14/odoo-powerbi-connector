# Copyright 2026 Umar — Power BI Connector
# License OPL-1 — https://www.odoo.com/documentation/legal/licenses.html

from odoo import http
from odoo.http import request
import json
import logging
from datetime import date, datetime, timedelta

_logger = logging.getLogger(__name__)


class PowerBIController(http.Controller):
    """
    Handles all HTTP requests from Power BI.

    ENDPOINTS:
      GET  /powerbi/ping              → health check (no auth)
      GET  /powerbi/datasets          → list all datasets (auth required)
      GET  /powerbi/data/<key>        → fetch dataset data (auth required)
      POST /powerbi/sync/<key>        → trigger scheduled cache refresh (auth required)

    AUTH:
      Every request (except /ping) must include header:
        X-PowerBI-Token: <your_token>
      Token is generated from Odoo Settings → Power BI.

    PERIOD FILTERING:
      ?period=this_month              → current calendar month
      ?period=last_month              → previous calendar month
      ?period=this_year               → Jan 1 – Dec 31 current year
      ?period=last_year               → full previous year
      ?period=this_week               → Monday to Sunday this week
      ?period=last_week               → full last week
      ?period=this_quarter            → current Q1/Q2/Q3/Q4
      ?period=last_quarter            → previous quarter
      ?period=last_7_days             → rolling 7 days
      ?period=last_30_days            → rolling 30 days
      ?period=last_90_days            → rolling 90 days
      ?period=last_365_days           → rolling 365 days
      ?period=today                   → today only
      ?date_from=YYYY-MM-DD           → custom start date
      ?date_to=YYYY-MM-DD             → custom end date
      (combine date_from + date_to for a custom range)

    PAGINATION:
      ?limit=1000&offset=0            → first 1000 records
      ?limit=1000&offset=1000         → next 1000 records
    """

    # ── STATIC SERIALIZER ─────────────────────────────────────────────────

    @staticmethod
    def _clean_static(records):
        """
        Convert Odoo ORM records into JSON-safe Python dicts.

        Field type conversions:
          many2one  [42, "Name"]  →  key_id: 42, key_name: "Name"
          datetime  obj          →  "2026-01-01T10:00:00"
          date      obj          →  "2026-01-01"
          False                  →  None  (JSON null)
          many2many [1,2,3]      →  "1,2,3"
        """
        cleaned = []
        for rec in records:
            clean_rec = {}
            for key, value in rec.items():
                if key == 'id':
                    clean_rec['id'] = value
                elif isinstance(value, list):
                    if (len(value) == 2
                            and isinstance(value[0], int)
                            and isinstance(value[1], str)):
                        # many2one field
                        clean_rec[f'{key}_id'] = value[0]
                        clean_rec[f'{key}_name'] = value[1]
                    else:
                        # many2many / one2many — comma-separated IDs
                        clean_rec[key] = ','.join(str(v) for v in value) if value else None
                elif isinstance(value, datetime):
                    clean_rec[key] = value.strftime('%Y-%m-%dT%H:%M:%S')
                elif isinstance(value, date):
                    clean_rec[key] = value.strftime('%Y-%m-%d')
                elif value is False:
                    clean_rec[key] = None
                else:
                    clean_rec[key] = value
            cleaned.append(clean_rec)
        return cleaned

    # ── PRIVATE HELPERS ────────────────────────────────────────────────────

    def _get_token(self):
        return request.env['ir.config_parameter'].sudo().get_param(
            'powerbi_connector.api_token', ''
        )

    def _authenticate(self):
        incoming = request.httprequest.headers.get('X-PowerBI-Token', '')
        stored = self._get_token()
        if not stored:
            _logger.warning('PowerBI: no token configured — all requests rejected')
            return False
        return incoming == stored

    def _json_response(self, data, status=200):
        return request.make_response(
            json.dumps(data, default=str, ensure_ascii=False),
            status=status,
            headers=[
                ('Content-Type', 'application/json; charset=utf-8'),
                ('X-PowerBI-Connector', 'Odoo18'),
            ]
        )

    def _error(self, message, status=401):
        _logger.warning('PowerBI error (%s): %s', status, message)
        return request.make_response(
            json.dumps({'success': False, 'error': message}),
            status=status,
            headers=[('Content-Type', 'application/json')]
        )

    def _parse_pagination(self, kwargs):
        try:
            limit = int(kwargs.get('limit', 50000))
            offset = int(kwargs.get('offset', 0))
        except (ValueError, TypeError):
            limit, offset = 50000, 0
        return min(limit, 100000), max(offset, 0)

    def _resolve_period(self, kwargs):
        """
        Resolve ?period=xxx OR ?date_from= / ?date_to= into a
        (date_from_str, date_to_str, error_message) tuple.

        Returns (None, None, None) when no date filter is requested.
        Returns (None, None, "error msg") when an invalid period name is given.
        """
        period = kwargs.get('period', '').strip().lower()

        if period:
            today = date.today()

            if period == 'today':
                start, end = today, today

            elif period == 'this_week':
                start = today - timedelta(days=today.weekday())
                end = start + timedelta(days=6)

            elif period == 'last_week':
                start = today - timedelta(days=today.weekday() + 7)
                end = start + timedelta(days=6)

            elif period == 'this_month':
                start = today.replace(day=1)
                if today.month == 12:
                    end = today.replace(day=31)
                else:
                    end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

            elif period == 'last_month':
                first_this = today.replace(day=1)
                end = first_this - timedelta(days=1)
                start = end.replace(day=1)

            elif period == 'this_quarter':
                q = (today.month - 1) // 3
                start_month = q * 3 + 1
                start = today.replace(month=start_month, day=1)
                end_month = start_month + 2
                if end_month == 12:
                    end = today.replace(month=12, day=31)
                else:
                    end = today.replace(month=end_month + 1, day=1) - timedelta(days=1)

            elif period == 'last_quarter':
                q = (today.month - 1) // 3
                if q == 0:
                    start = today.replace(year=today.year - 1, month=10, day=1)
                    end = today.replace(year=today.year - 1, month=12, day=31)
                else:
                    start_month = (q - 1) * 3 + 1
                    end_month = start_month + 2
                    start = today.replace(month=start_month, day=1)
                    end = today.replace(month=end_month + 1, day=1) - timedelta(days=1)

            elif period == 'this_year':
                start = today.replace(month=1, day=1)
                end = today.replace(month=12, day=31)

            elif period == 'last_year':
                start = today.replace(year=today.year - 1, month=1, day=1)
                end = today.replace(year=today.year - 1, month=12, day=31)

            elif period == 'last_7_days':
                start = today - timedelta(days=7)
                end = today

            elif period == 'last_30_days':
                start = today - timedelta(days=30)
                end = today

            elif period == 'last_90_days':
                start = today - timedelta(days=90)
                end = today

            elif period == 'last_365_days':
                start = today - timedelta(days=365)
                end = today

            else:
                valid = (
                    'today, this_week, last_week, this_month, last_month, '
                    'this_quarter, last_quarter, this_year, last_year, '
                    'last_7_days, last_30_days, last_90_days, last_365_days'
                )
                return None, None, f'Unknown period "{period}". Valid values: {valid}'

            return start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'), None

        # No ?period= — check for explicit date_from / date_to
        date_from = kwargs.get('date_from', '').strip() or None
        date_to = kwargs.get('date_to', '').strip() or None
        return date_from, date_to, None

    def _apply_date_domain(self, domain, date_from, date_to, date_field):
        """Append date range conditions to an existing domain list."""
        domain = list(domain)
        if date_from:
            domain.append((date_field, '>=', date_from))
        if date_to:
            domain.append((date_field, '<=', date_to))
        return domain

    # ── ENDPOINTS ──────────────────────────────────────────────────────────

    @http.route('/powerbi/ping', type='http', auth='public', methods=['GET'], csrf=False)
    def ping(self, **kwargs):
        """Health check — no auth required. Use to confirm connector is running."""
        return self._json_response({
            'success': True,
            'message': 'Odoo Power BI Connector is running',
            'version': '18.0.1.1.0',
        })

    @http.route('/powerbi/datasets', type='http', auth='public', methods=['GET'], csrf=False)
    def list_datasets(self, **kwargs):
        """List all active datasets with their URLs and sync status."""
        if not self._authenticate():
            return self._error('Invalid or missing X-PowerBI-Token header')

        datasets = request.env['powerbi.dataset'].sudo().search([('active', '=', True)])
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url', '')

        result = []
        for ds in datasets:
            result.append({
                'name': ds.name,
                'endpoint_key': ds.endpoint_key,
                'endpoint_url': f'{base_url}/powerbi/data/{ds.endpoint_key}',
                'sync_mode': ds.sync_mode,
                'odoo_model': ds.odoo_model,
                'date_field': ds.date_field,
                'last_sync': ds.last_sync.strftime('%Y-%m-%dT%H:%M:%S') if ds.last_sync else None,
                'record_count': ds.record_count if ds.sync_mode == 'scheduled' else None,
            })

        return self._json_response({
            'success': True,
            'count': len(result),
            'datasets': result,
        })

    @http.route('/powerbi/data/<string:endpoint_key>', type='http',
                auth='public', methods=['GET'], csrf=False)
    def get_dataset_data(self, endpoint_key, **kwargs):
        """
        Main data endpoint. Power BI calls this to fetch records.

        Supported query params:
          ?period=this_month          named period filter
          ?date_from=2026-01-01       custom start date
          ?date_to=2026-06-30         custom end date
          ?limit=1000                 max records per call
          ?offset=0                   skip N records (for pagination)
        """
        # 1 — Auth
        if not self._authenticate():
            return self._error('Invalid or missing X-PowerBI-Token header')

        # 2 — Find dataset
        dataset = request.env['powerbi.dataset'].sudo().search(
            [('endpoint_key', '=', endpoint_key), ('active', '=', True)],
            limit=1
        )
        if not dataset:
            return self._error(f'Dataset "{endpoint_key}" not found or inactive', status=404)

        # 3 — Pagination
        limit, offset = self._parse_pagination(kwargs)

        # 4 — Period / date filter
        date_from, date_to, period_error = self._resolve_period(kwargs)
        if period_error:
            return self._error(period_error, status=400)

        date_field = dataset.date_field or 'date'
        period_label = kwargs.get('period') or (
            f'{date_from} → {date_to}' if (date_from or date_to) else 'all'
        )

        # 5a — LIVE mode
        if dataset.sync_mode == 'live':
            try:
                # Validate model exists
                if dataset.odoo_model not in request.env:
                    return self._error(
                        f'Model "{dataset.odoo_model}" not found. '
                        'Make sure the required Odoo module is installed.',
                        status=404
                    )

                Model = request.env[dataset.odoo_model].sudo()
                domain = self._apply_date_domain(
                    dataset.get_domain(), date_from, date_to, date_field
                )

                records = Model.search_read(
                    domain=domain,
                    fields=dataset.get_fields_list(),
                    limit=limit,
                    offset=offset,
                    order='id desc',
                )
                data = self._clean_static(records)

                return self._json_response({
                    'success': True,
                    'dataset': dataset.name,
                    'sync_mode': 'live',
                    'period': period_label,
                    'date_from': date_from,
                    'date_to': date_to,
                    'count': len(data),
                    'limit': limit,
                    'offset': offset,
                    'data': data,
                })

            except Exception as e:
                _logger.exception('PowerBI live fetch error for %s', endpoint_key)
                return self._error(str(e), status=500)

        # 5b — SCHEDULED mode
        else:
            if not dataset.cached_data:
                return self._error(
                    f'No cached data for "{dataset.name}". '
                    'Click "Sync Cache Now" in the Dataset Manager or wait for the cron job.',
                    status=503
                )
            try:
                all_data = json.loads(dataset.cached_data)

                # Apply date filter to cached data in Python
                if date_from or date_to:
                    filtered = []
                    for rec in all_data:
                        val = rec.get(date_field)
                        if not val:
                            continue
                        rec_date = str(val)[:10]  # first 10 chars = YYYY-MM-DD
                        if date_from and rec_date < date_from:
                            continue
                        if date_to and rec_date > date_to:
                            continue
                        filtered.append(rec)
                    all_data = filtered

                total = len(all_data)
                paginated = all_data[offset: offset + limit]

                return self._json_response({
                    'success': True,
                    'dataset': dataset.name,
                    'sync_mode': 'scheduled',
                    'period': period_label,
                    'date_from': date_from,
                    'date_to': date_to,
                    'last_sync': dataset.last_sync.strftime('%Y-%m-%dT%H:%M:%S') if dataset.last_sync else None,
                    'total_records': total,
                    'count': len(paginated),
                    'limit': limit,
                    'offset': offset,
                    'data': paginated,
                })

            except Exception as e:
                _logger.exception('PowerBI cache read error for %s', endpoint_key)
                return self._error(str(e), status=500)

    @http.route('/powerbi/sync/<string:endpoint_key>', type='http',
                auth='public', methods=['POST'], csrf=False)
    def trigger_sync(self, endpoint_key, **kwargs):
        """
        Manually trigger a cache refresh for a scheduled dataset.
        Useful as a webhook from Power BI scheduled refresh.
        POST /powerbi/sync/purchase_orders
        """
        if not self._authenticate():
            return self._error('Invalid or missing X-PowerBI-Token header')

        dataset = request.env['powerbi.dataset'].sudo().search(
            [('endpoint_key', '=', endpoint_key), ('active', '=', True)],
            limit=1
        )
        if not dataset:
            return self._error(f'Dataset "{endpoint_key}" not found', status=404)

        if dataset.sync_mode != 'scheduled':
            return self._error(
                f'Dataset "{dataset.name}" is in live mode — no cache sync needed.',
                status=400
            )

        dataset._refresh_cache()
        return self._json_response({
            'success': True,
            'message': f'Dataset "{dataset.name}" synced successfully.',
            'last_sync': dataset.last_sync.strftime('%Y-%m-%dT%H:%M:%S') if dataset.last_sync else None,
            'record_count': dataset.record_count,
        })
