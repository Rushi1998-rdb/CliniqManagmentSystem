from datetime import datetime, time, timedelta

from odoo import api, fields, models


class HospitalOutpatientReportDashboard(models.Model):
    _inherit = 'hospital.outpatient'

    lab_test_charge = fields.Monetary(
        string="Lab Charges",
        currency_field='currency_id',
        compute="_compute_lab_test_charge",
        store=True
    )

    @api.depends('lab_result_ids.lab_test_charge')
    def _compute_lab_test_charge(self):
        for rec in self:
            rec.lab_test_charge = sum(rec.lab_result_ids.mapped('lab_test_charge'))

    @api.depends('general_fee', 'lab_test_charge', 'charge_ids.amount')
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = (
                (rec.general_fee or 0.0)
                + (rec.lab_test_charge or 0.0)
                + sum(rec.charge_ids.mapped('amount'))
            )

    @api.model
    def _report_company_domain(self):
        return [('company_id', '=', self.env.company.id)]

    @api.model
    def _get_period_dates(self, period_key):
        today = fields.Date.context_today(self)
        if period_key == 'last_7_days':
            return today - timedelta(days=6), today
        if period_key == 'month':
            return today.replace(day=1), today
        if period_key == 'year':
            return today.replace(month=1, day=1), today
        return today, today

    @api.model
    def _get_previous_period_dates(self, period_key):
        current_start, current_end = self._get_period_dates(period_key)
        if period_key == 'last_7_days':
            previous_end = current_start - timedelta(days=1)
            return previous_end - timedelta(days=6), previous_end
        if period_key == 'month':
            previous_end = current_start - timedelta(days=1)
            return previous_end.replace(day=1), previous_end
        if period_key == 'year':
            previous_end = current_start - timedelta(days=1)
            return previous_end.replace(month=1, day=1), previous_end
        previous_day = current_start - timedelta(days=1)
        return previous_day, previous_day

    @api.model
    def _format_period_caption(self, start_date, end_date):
        if start_date == end_date:
            return start_date.strftime('%d %b %Y')
        return f"{start_date.strftime('%d %b')} - {end_date.strftime('%d %b')}"

    @api.model
    def _format_money(self, amount):
        currency = self.env.company.currency_id
        return f"{currency.symbol} {amount:,.2f}"

    @api.model
    def _growth_percentage(self, current_amount, previous_amount):
        if not previous_amount:
            return 100.0 if current_amount else 0.0
        return ((current_amount - previous_amount) / previous_amount) * 100.0

    @api.model
    def _selection_label(self, field_name, value):
        selection = dict(self._fields[field_name].selection)
        return selection.get(value, value or '')

    @api.model
    def _service_definitions(self):
        return [
            ('consultation', 'Consultation'),
            ('injection', 'Injection'),
            ('dressing', 'Dressing'),
            ('lab_test', 'Lab Test'),
            ('others', 'Others'),
        ]

    @api.model
    def _get_charge_service_group(self, charge_name):
        """Map dynamic charge names to dashboard service group keys."""
        name_lower = (charge_name or '').lower()
        if 'consultation' in name_lower:
            return 'consultation'
        if 'injection' in name_lower:
            return 'injection'
        if 'dressing' in name_lower:
            return 'dressing'
        if 'lab' in name_lower:
            return 'lab_test'
        return 'others'

    @api.model
    def _base_transaction_vals(self, outpatient, service_key, service_name, amount, tx_date):
        visit_time = outpatient.visit_time_local or ''
        raw_datetime = outpatient.visit_time or datetime.combine(tx_date, time.min)
        doctor_name = ''
        if outpatient.doctor_id:
            doctor_name = outpatient.doctor_id.doctor_id.name or outpatient.doctor_id.name or ''
        return {
            'date': fields.Date.to_string(tx_date),
            'op_number': outpatient.op_reference or '',
            'patient_number': outpatient.patient_id.patient_seq or '',
            'patient_name': outpatient.patient_id.name or '',
            'type': self._selection_label('patient_queue_type', outpatient.patient_queue_type),
            'doctor': doctor_name,
            'service': service_name,
            'service_group': service_key,
            'record_key': f"op:{outpatient.id}",
            'amount': amount,
            'amount_display': self._format_money(amount),
            'time': visit_time,
            'sort_datetime': fields.Datetime.to_string(raw_datetime),
        }

    @api.model
    def _base_lab_test_transaction_vals(self, lab_result):
        tx_date = lab_result.ordered_date or fields.Date.context_today(self)
        outpatient = lab_result.outpatient_id
        visit_time = outpatient.visit_time_local if outpatient else ''
        raw_datetime = (
            outpatient.visit_time
            if outpatient and outpatient.visit_time
            else datetime.combine(tx_date, time.min)
        )
        doctor_name = ''
        patient_type = 'Lab Test'
        if outpatient:
            patient_type = self._selection_label(
                'patient_queue_type', outpatient.patient_queue_type
            )
            if outpatient.doctor_id:
                doctor_name = (
                    outpatient.doctor_id.doctor_id.name
                    or outpatient.doctor_id.name
                    or ''
                )
        return {
            'date': fields.Date.to_string(tx_date),
            'op_number': outpatient.op_reference if outpatient else '',
            'patient_number': lab_result.patient_id.patient_seq or '',
            'patient_name': lab_result.patient_id.name or '',
            'type': patient_type,
            'doctor': doctor_name,
            'service': 'Lab Test',
            'service_group': 'lab_test',
            'record_key': (
                f"op:{outpatient.id}" if outpatient else f"lab:{lab_result.id}"
            ),
            'amount': lab_result.lab_test_charge,
            'amount_display': self._format_money(lab_result.lab_test_charge),
            'time': visit_time,
            'sort_datetime': fields.Datetime.to_string(raw_datetime),
        }

    @api.model
    def _build_service_transactions(self, start_date, end_date):
        transactions = []
        outpatients = self.search(
            self._report_company_domain() + [
                ('op_date', '>=', start_date),
                ('op_date', '<=', end_date),
                ('state', '=', 'done'),
            ],
            order='op_date desc, visit_time desc, id desc',
        )

        for outpatient in outpatients:
            if outpatient.general_fee:
                transactions.append(self._base_transaction_vals(
                    outpatient, 'consultation', 'Consultation',
                    outpatient.general_fee, outpatient.op_date
                ))
            for charge in outpatient.charge_ids:
                if charge.amount:
                    service_group = self._get_charge_service_group(charge.charge_type_id.name)
                    transactions.append(self._base_transaction_vals(
                        outpatient, service_group, charge.charge_type_id.name,
                        charge.amount, outpatient.op_date
                    ))
            if outpatient.lab_test_charge:
                transactions.append(self._base_transaction_vals(
                    outpatient, 'lab_test', 'Lab Test',
                    outpatient.lab_test_charge, outpatient.op_date
                ))

        # Also pick up lab results that are NOT linked to an outpatient
        # to ensure the dashboard reflects ALL lab revenue.
        lab_results = self.env['hospital.lab.result'].search([
            ('company_id', '=', self.env.company.id),
            ('ordered_date', '>=', start_date),
            ('ordered_date', '<=', end_date),
            ('lab_test_charge', '>', 0),
            ('outpatient_id', '=', False),
        ], order='ordered_date desc, id desc')
        for lab_result in lab_results:
            transactions.append(self._base_lab_test_transaction_vals(lab_result))
        return transactions

    @api.model
    def _base_op_transaction_group(self, outpatient, tx_date):
        visit_time = outpatient.visit_time_local or ''
        raw_datetime = outpatient.visit_time or datetime.combine(tx_date, time.min)
        doctor_name = ''
        if outpatient.doctor_id:
            doctor_name = outpatient.doctor_id.doctor_id.name or outpatient.doctor_id.name or ''
        return {
            'date': fields.Date.to_string(tx_date),
            'op_number': outpatient.op_reference or '',
            'patient_number': outpatient.patient_id.patient_seq or '',
            'patient_name': outpatient.patient_id.name or '',
            'type': self._selection_label('patient_queue_type', outpatient.patient_queue_type),
            'doctor': doctor_name,
            'services': [],
            'amount': 0.0,
            'time': visit_time,
            'sort_datetime': fields.Datetime.to_string(raw_datetime),
        }

    @api.model
    def _build_report_transactions(self, start_date, end_date):
        transactions = []
        grouped_transactions = {}
        for service_tx in self._build_service_transactions(start_date, end_date):
            key = service_tx.get('record_key') or service_tx['op_number']
            if key not in grouped_transactions:
                outpatient = self.search([
                    ('op_reference', '=', service_tx['op_number']),
                    ('company_id', '=', self.env.company.id),
                ], limit=1)
                if outpatient:
                    grouped_transactions[key] = self._base_op_transaction_group(
                        outpatient, fields.Date.to_date(service_tx['date'])
                    )
                else:
                    grouped_transactions[key] = {
                        'date': service_tx['date'],
                        'op_number': service_tx['op_number'],
                        'patient_number': service_tx['patient_number'],
                        'patient_name': service_tx['patient_name'],
                        'type': service_tx['type'],
                        'doctor': service_tx['doctor'],
                        'services': [],
                        'amount': 0.0,
                        'time': service_tx['time'],
                        'sort_datetime': service_tx['sort_datetime'],
                    }
            grouped_transactions[key]['services'].append(service_tx['service'])
            grouped_transactions[key]['amount'] += service_tx['amount']

        for item in grouped_transactions.values():
            if not item['services'] or not item['amount']:
                continue
            transactions.append({
                'date': item['date'],
                'op_number': item['op_number'],
                'patient_number': item['patient_number'],
                'patient_name': item['patient_name'],
                'type': item['type'],
                'doctor': item['doctor'],
                'service': '+'.join(item['services']),
                'amount': item['amount'],
                'amount_display': self._format_money(item['amount']),
                'time': item['time'],
                'sort_datetime': item['sort_datetime'],
            })

        transactions.sort(
            key=lambda tx: (
                tx.get('date') or '',
                tx.get('sort_datetime') or '',
                tx.get('op_number') or '',
            ),
            reverse=True,
        )
        for tx in transactions:
            tx.pop('sort_datetime', None)
        return transactions

    @api.model
    def _breakdown_from_transactions(self, transactions):
        labels = dict(self._service_definitions())
        totals = {
            key: {'service_key': key, 'service': label, 'count': 0, 'amount': 0.0}
            for key, label in self._service_definitions()
        }
        for tx in transactions:
            item = totals.get(tx['service_group'])
            if not item:
                continue
            item['count'] += 1
            item['amount'] += tx['amount']

        ordered = []
        for key, _label in self._service_definitions():
            item = totals[key]
            item['amount_display'] = self._format_money(item['amount'])
            ordered.append(item)
        return ordered

    @api.model
    def _sum_transaction_amount(self, start_date, end_date):
        return sum(tx['amount'] for tx in self._build_service_transactions(start_date, end_date))

    @api.model
    def fetch_report_dashboard_data(self, breakdown_period='today', revenue_period='month',
                                    transaction_start=None, transaction_end=None):
        today = fields.Date.context_today(self)

        breakdown_start, breakdown_end = self._get_period_dates(breakdown_period)
        revenue_start, revenue_end = self._get_period_dates(revenue_period)

        tx_start = fields.Date.to_date(transaction_start) if transaction_start else today
        tx_end = fields.Date.to_date(transaction_end) if transaction_end else today

        today_start, today_end = self._get_period_dates('today')
        week_start, week_end = self._get_period_dates('last_7_days')
        month_start, month_end = self._get_period_dates('month')
        year_start, year_end = self._get_period_dates('year')

        yesterday_start, yesterday_end = self._get_previous_period_dates('today')
        prev_week_start, prev_week_end = self._get_previous_period_dates('last_7_days')
        prev_month_start, prev_month_end = self._get_previous_period_dates('month')
        prev_year_start, prev_year_end = self._get_previous_period_dates('year')

        card_specs = [
            ('today', 'Today Collection', today_start, today_end, yesterday_start, yesterday_end, 'vs Yesterday'),
            ('last_7_days', 'Last 7 Days', week_start, week_end, prev_week_start, prev_week_end, 'vs Previous Week'),
            ('month', 'This Month', month_start, month_end, prev_month_start, prev_month_end, 'vs Last Month'),
            ('year', 'This Year', year_start, year_end, prev_year_start, prev_year_end, 'vs Last Year'),
        ]

        cards = []
        for key, title, start_date, end_date, prev_start, prev_end, compare_label in card_specs:
            current_amount = self._sum_transaction_amount(start_date, end_date)
            previous_amount = self._sum_transaction_amount(prev_start, prev_end)
            cards.append({
                'key': key,
                'title': title,
                'caption': self._format_period_caption(start_date, end_date),
                'amount': current_amount,
                'amount_display': self._format_money(current_amount),
                'growth': round(self._growth_percentage(current_amount, previous_amount), 1),
                'compare_label': compare_label,
            })

        breakdown_transactions = self._build_service_transactions(breakdown_start, breakdown_end)
        breakdown = self._breakdown_from_transactions(breakdown_transactions)
        breakdown_total = sum(item['amount'] for item in breakdown)

        revenue_transactions = self._build_service_transactions(revenue_start, revenue_end)
        revenue_breakdown = self._breakdown_from_transactions(revenue_transactions)
        revenue_total = sum(item['amount'] for item in revenue_breakdown)
        revenue_chart = []
        for item in revenue_breakdown:
            percentage = (item['amount'] / revenue_total * 100.0) if revenue_total else 0.0
            revenue_chart.append({
                'service_key': item['service_key'],
                'service': item['service'],
                'amount': item['amount'],
                'amount_display': item['amount_display'],
                'percentage': round(percentage, 1),
            })

        today_outpatients = self.search(
            self._report_company_domain() + [('op_date', '=', today)]
        )
        detailed_transactions = self._build_report_transactions(tx_start, tx_end)

        return {
            'cards': cards,
            'breakdown': breakdown,
            'breakdown_total': self._format_money(breakdown_total),
            'breakdown_period': breakdown_period,
            'revenue_chart': revenue_chart,
            'revenue_total': self._format_money(revenue_total),
            'revenue_period': revenue_period,
            'quick_stats': {
                'total_patients_today': len(today_outpatients),
                'new_patients': len(today_outpatients.filtered(lambda op: op.patient_queue_type == 'new')),
                'follow_ups': len(today_outpatients.filtered(lambda op: op.patient_queue_type in ('revisit', 'seen'))),
                'completed': len(today_outpatients.filtered(lambda op: op.state == 'done')),
            },
            'transactions': detailed_transactions,
            'transaction_start': fields.Date.to_string(tx_start),
            'transaction_end': fields.Date.to_string(tx_end),
            'currency_symbol': self.env.company.currency_id.symbol,
            'company_name': self.env.company.name,
        }

    @api.model
    def action_open_report_period(self, period_key='today'):
        start_date, end_date = self._get_period_dates(period_key)
        return {
            'name': 'Collected Outpatients',
            'type': 'ir.actions.act_window',
            'res_model': 'hospital.outpatient',
            'view_mode': 'tree,form',
            'views': [[False, 'tree'], [False, 'form']],
            'target': 'current',
            'domain': [
                ('company_id', '=', self.env.company.id),
                ('state', '=', 'done'),
                ('op_date', '>=', start_date),
                ('op_date', '<=', end_date),
            ],
            'context': {},
        }
