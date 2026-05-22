from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    clinic_timing = fields.Char(
        string="Clinic Timing",
        help="Example: 9:00 - 2:00 / 3:00 - 9:00"
    )

    def _get_tax_seed_company(self):
        """Return a company whose taxes can be copied to new companies."""
        self.env.cr.execute("""
            SELECT company_id
              FROM account_tax
             WHERE company_id IS NOT NULL
          GROUP BY company_id
          ORDER BY COUNT(*) DESC, company_id
             LIMIT 1
        """)
        row = self.env.cr.fetchone()
        return self.browse(row[0]) if row else self.env['res.company']

    def _seed_taxes_from_company(self, source_company=False):
        """Copy the configured tax list to companies that do not have taxes."""
        AccountTax = self.env['account.tax'].sudo().with_context(active_test=False)
        source_company = source_company or self._get_tax_seed_company()
        if not source_company:
            return

        source_taxes = AccountTax.search([('company_id', '=', source_company.id)])
        simple_taxes = source_taxes.filtered(lambda tax: not tax.children_tax_ids)
        group_taxes = source_taxes - simple_taxes
        for company in self.sudo():
            if company == source_company:
                continue
            if AccountTax.search_count([('company_id', '=', company.id)]):
                continue

            copied_taxes = {}
            for tax in simple_taxes:
                copied_taxes[tax.id] = tax.copy(self._get_tax_copy_defaults(tax, company))
            for tax in group_taxes:
                children = [
                    copied_taxes[child.id].id
                    for child in tax.children_tax_ids
                    if child.id in copied_taxes
                ]
                defaults = self._get_tax_copy_defaults(tax, company)
                defaults['children_tax_ids'] = [(6, 0, children)]
                copied_taxes[tax.id] = tax.copy(defaults)

    def _get_or_create_outstanding_account(self, code, name):
        self.ensure_one()
        Account = self.env['account.account'].sudo().with_context(
            allowed_company_ids=[self.id],
        )
        account = Account.search([
            ('code', '=', code),
            ('company_id', '=', self.id),
        ], limit=1)
        if account:
            if not account.reconcile:
                account.reconcile = True
            return account

        return Account.create({
            'name': name,
            'code': code,
            'account_type': 'asset_current',
            'reconcile': True,
            'company_id': self.id,
        })

    def _ensure_cash_manual_payment_accounts(self):
        ManualMethod = self.env['account.payment.method'].sudo()
        Journal = self.env['account.journal'].sudo()
        PaymentMethodLine = self.env['account.payment.method.line'].sudo()

        inbound_manual = ManualMethod.search([
            ('code', '=', 'manual'),
            ('payment_type', '=', 'inbound'),
        ], limit=1)
        outbound_manual = ManualMethod.search([
            ('code', '=', 'manual'),
            ('payment_type', '=', 'outbound'),
        ], limit=1)

        for company in self.sudo():
            receipts_account = company._get_or_create_outstanding_account(
                '100203',
                'Outstanding Receipts',
            )
            payments_account = company._get_or_create_outstanding_account(
                '100204',
                'Outstanding Payments',
            )
            company.write({
                'account_journal_payment_debit_account_id': receipts_account.id,
                'account_journal_payment_credit_account_id': payments_account.id,
            })

            cash_journals = Journal.search([
                ('type', '=', 'cash'),
                ('company_id', '=', company.id),
            ])
            for journal in cash_journals:
                if inbound_manual:
                    inbound_line = journal.inbound_payment_method_line_ids.filtered(
                        lambda line: line.payment_method_id == inbound_manual
                    )[:1]
                    if inbound_line:
                        inbound_line.payment_account_id = receipts_account
                    else:
                        PaymentMethodLine.with_context(
                            allowed_company_ids=[company.id],
                        ).create({
                            'name': inbound_manual.name,
                            'payment_method_id': inbound_manual.id,
                            'journal_id': journal.id,
                            'payment_account_id': receipts_account.id,
                        })

                if outbound_manual:
                    outbound_line = journal.outbound_payment_method_line_ids.filtered(
                        lambda line: line.payment_method_id == outbound_manual
                    )[:1]
                    if outbound_line:
                        outbound_line.payment_account_id = payments_account
                    else:
                        PaymentMethodLine.with_context(
                            allowed_company_ids=[company.id],
                        ).create({
                            'name': outbound_manual.name,
                            'payment_method_id': outbound_manual.id,
                            'journal_id': journal.id,
                            'payment_account_id': payments_account.id,
                        })

    def _get_tax_copy_defaults(self, tax, company):
        def repartition_commands(lines):
            return [
                (0, 0, {
                    'factor_percent': line.factor_percent,
                    'repartition_type': line.repartition_type,
                    'sequence': line.sequence,
                    'use_in_tax_closing': line.use_in_tax_closing,
                    'account_id': False,
                    'tag_ids': [(5, 0, 0)],
                })
                for line in lines
            ]

        return {
            'name': tax.name,
            'company_id': company.id,
            'children_tax_ids': [(5, 0, 0)],
            'cash_basis_transition_account_id': False,
            'invoice_repartition_line_ids': repartition_commands(
                tax.invoice_repartition_line_ids
            ),
            'refund_repartition_line_ids': repartition_commands(
                tax.refund_repartition_line_ids
            ),
        }

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        companies._seed_taxes_from_company()
        companies._ensure_cash_manual_payment_accounts()
        return companies

    @api.model
    def action_seed_missing_company_taxes(self):
        companies_without_taxes = self.sudo().search([]).filtered(
            lambda company: not self.env['account.tax'].sudo().search_count([
                ('company_id', '=', company.id),
            ])
        )
        companies_without_taxes._seed_taxes_from_company()

    @api.model
    def action_configure_cash_outstanding_accounts(self):
        companies = self.sudo().search([])
        companies._ensure_cash_manual_payment_accounts()
        return True
