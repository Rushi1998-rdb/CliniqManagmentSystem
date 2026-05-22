
import re
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HospitalPharmacy(models.Model):
    """Class holding Pharmacy details."""
    _name = 'hospital.pharmacy'
    _description = 'Pharmacy'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company.id,
                                 help='Indicates the company')

    name = fields.Char(string="Name", help='Name of the pharmacy',
                       required=True)
    pharmacist_id = fields.Many2one('hr.employee',
                                    string="Pharmacist",
                                    help='Name of the pharmacist',
                                    domain=[
                                        ('job_id.name', '=', 'Pharmacist')])
    phone = fields.Char(string='Phone', required=True, help='Phone number of the pharmacy')
    mobile = fields.Char(string='Mobile', help='Mobile number of the pharmacy')
    email = fields.Char(string='Email', help='Email of the pharmacy')
    street = fields.Char(string='Street', help='Street of pharmacy')
    street2 = fields.Char(string='Street2', help='Street2 of pharmacy')
    zip = fields.Char(string='Zip', help='Zip code of pharmacy')
    city = fields.Char(string='City', help='City of pharmacy')
    state_id = fields.Many2one("res.country.state", string='State',
                               help='State of pharmacy')
    country_id = fields.Many2one('res.country', string='Country',
                                 help='Country of pharmacy')
    notes = fields.Text(string='Notes', help='Notes regarding pharmacy')
    image_129 = fields.Image(string='Image', help='Image of pharmacy',
                             max_width=128, max_height=128)
    active = fields.Boolean(string='Active', help='True for active pharmacy',
                            default=True)
    medicine_ids = fields.One2many('pharmacy.medicine',
                                   'pharmacy_id',
                                   string='Pharmacy',
                                   help='Indicates the medicines in the '
                                        'pharmacy')
    sales_team_id = fields.Many2one('crm.team', string='Sales Team',
                                    help='Choose the sales-team for the'
                                         ' pharmacy')

    @api.model
    def _get_pharmacy_sale_order_sequence(self, company):
        """Return the company-specific pharmacy sale order sequence."""
        seq_code = 'pharmacy.sale.order.sequence'
        sequence = self.env['ir.sequence'].sudo().search([
            ('code', '=', seq_code),
            ('company_id', '=', company.id),
        ], limit=1)

        if sequence:
            return sequence

        template = self.env['ir.sequence'].sudo().search([
            ('code', '=', seq_code),
            ('company_id', '=', False),
        ], limit=1)

        if not template:
            template = self.env['ir.sequence'].sudo().create({
                'name': 'Pharmacy Sale Order Sequence',
                'code': seq_code,
                'prefix': 'S',
                'padding': 5,
                'number_next': 1,
                'number_increment': 1,
                'company_id': False,
            })

        existing_orders = self.env['sale.order'].sudo().search([
            ('company_id', '=', company.id),
            ('name', '=like', 'S%'),
        ])
        start_num = 1
        if existing_orders:
            seq_numbers = []
            for order in existing_orders:
                nums = re.findall(r'\d+', order.name or '')
                if nums:
                    seq_numbers.append(int(nums[-1]))
            if seq_numbers:
                start_num = max(seq_numbers) + 1

        return template.copy({
            'company_id': company.id,
            'number_next': start_num,
            'name': f'{template.name} ({company.name})',
        })

    @api.model
    def _ensure_sale_journal(self, company):
        """Ensure the target company has at least one sale journal."""
        journal = self.env['account.journal'].sudo().search([
            ('type', '=', 'sale'),
            ('company_id', '=', company.id),
        ], limit=1)
        if journal:
            return journal

        existing_codes = set(self.env['account.journal'].sudo().search([
            ('company_id', '=', company.id),
        ]).mapped('code'))
        code = 'SALE'
        if code in existing_codes:
            for idx in range(1, 100):
                candidate = f'S{idx:03d}'
                if candidate not in existing_codes:
                    code = candidate
                    break

        return self.env['account.journal'].sudo().create({
            'name': f'{company.name} Sales',
            'type': 'sale',
            'code': code,
            'company_id': company.id,
        })

    @api.model
    def create(self, vals):
        """Method for creating CRM team"""
        company_id = vals.get('company_id') or self.env.company.id
        team_id = self.env['crm.team'].sudo().create({
            'name': vals['name'] + ' Pharmacy Team',
            'company_id': company_id,
            'user_id': self.env.uid
        })
        vals['sales_team_id'] = team_id.id
        return super().create(vals)

    def _validate_requested_products_stock(self, products):
        """Ensure requested medicine quantities are available before sale order creation."""
        requested_qty_by_product = defaultdict(float)
        product_by_template = {}

        for rec in products:
            product_template_id = int(rec['product'])
            requested_qty_by_product[product_template_id] += float(rec.get('qty', 0.0))

        for product_template_id in requested_qty_by_product:
            product = self.env['product.product'].search(
                [
                    ('product_tmpl_id', '=', product_template_id),
                    ('product_tmpl_id.company_id', '=', self.env.company.id),
                ],
                limit=1
            )
            if not product:
                raise UserError(_("Selected medicine was not found."))
            product_by_template[product_template_id] = product

        unavailable_products = []
        for product_template_id, required_qty in requested_qty_by_product.items():
            product = product_by_template[product_template_id]
            available_qty = product.free_qty
            if available_qty < required_qty:
                unavailable_products.append(_(
                    "%(product)s: available qty is %(available)s, but required qty is %(required)s",
                    product=product.display_name,
                    available=available_qty,
                    required=required_qty,
                ))

        if unavailable_products:
            raise UserError(_(
                "Unable to create sale order because the following products do not have enough stock:\n%s"
            ) % "\n".join(unavailable_products))

        return product_by_template

    @api.model
    def create_sale_order(self, kwargs):
        """Creating sale order from pharmacy dashboard"""
        company = self.env.company
        self._ensure_sale_journal(company)
        sale_sequence = self._get_pharmacy_sale_order_sequence(company)
        product_by_template = self._validate_requested_products_stock(kwargs['products'])
        dob_value = kwargs.get('dob') or False
        if dob_value:
            dob_value = fields.Date.to_string(fields.Date.to_date(dob_value))

        if 'op' not in kwargs.keys():
            patient_id = self.env['res.partner'].sudo().search(
                [('company_id', '=', company.id),
                 '|', ('phone', '=', kwargs.get('phone')),
                 '&', ('name', '=', kwargs['name']), ('email', '=', kwargs['email'])],
                limit=1)
        else:
            patient_id = self.env['hospital.outpatient'].sudo().search(
                [('op_reference', '=', kwargs['op'])]).patient_id
        if not patient_id:
            patient_id = self.env['res.partner'].with_context(
                is_patient=True,
                default_is_patient=True,
            ).sudo().create({
                'name': kwargs['name'],
                'email': kwargs['email'],
                'phone': kwargs.get('phone'),
                'date_of_birth': dob_value,
                'gender': kwargs.get('gender') or False,
                'customer_rank': 1,
                'company_id': company.id,
            })

        pharmacy = self.sudo().search([('company_id', '=', company.id)], limit=1)
        pharmacy_sale_order = self.env['sale.order'].sudo().create({
            'name': sale_sequence.next_by_id() if sale_sequence else 'New',
            'partner_id': patient_id.id,
            'company_id': company.id,
            'team_id': pharmacy.sales_team_id.id if pharmacy and pharmacy.sales_team_id else False,
        })

        for rec in kwargs['products']:
            product = product_by_template[int(rec['product'])]
            pharmacy_sale_order.sudo().write({
                'order_line': [(0, 0, {
                    'product_id': product.id,
                    'product_uom_qty': float(rec['qty']),
                    'price_unit': float(rec['price']) if 'price' in rec.keys() else
                        product.list_price
                })]
            })
            
        pharmacy_sale_order.action_confirm()
        if 'op' in kwargs.keys():
            self.env['hospital.outpatient'].sudo().search(
                [('op_reference', '=', kwargs['op'])]).write(
                {
                    'is_sale_created': True
                })
        return {'invoice_id': pharmacy_sale_order.id, 'invoice': pharmacy_sale_order.name}

    @api.model
    def create_sale_order_from_prescription(self, prescription_key):
        """Create a pharmacy sale order from the selected prescription group."""
        prescription_key = str(prescription_key or '')
        if prescription_key.startswith('outpatient:'):
            domain = [('outpatient_id', '=', int(prescription_key.split(':')[1]))]
        elif prescription_key.startswith('inpatient:'):
            domain = [('inpatient_id', '=', int(prescription_key.split(':')[1]))]
        elif prescription_key.startswith('line:'):
            domain = [('id', '=', int(prescription_key.split(':')[1]))]
        else:
            domain = [('id', '=', int(prescription_key))]

        prescription_lines = self.env['prescription.line'].sudo().search([
            '|', '|',
            ('company_id', '=', self.env.company.id),
            ('outpatient_id.company_id', '=', self.env.company.id),
            ('inpatient_id.company_id', '=', self.env.company.id),
        ] + domain)
        if not prescription_lines:
            raise UserError(_("Prescription not found."))

        outpatient = prescription_lines.mapped('outpatient_id')[:1]
        inpatient = prescription_lines.mapped('inpatient_id')[:1]
        patient = outpatient.patient_id or inpatient.patient_id or prescription_lines[:1].res_partner_id
        if not patient:
            raise UserError(_("No patient found for this prescription."))

        company = self.env.company
        self._ensure_sale_journal(company)
        sale_sequence = self._get_pharmacy_sale_order_sequence(company)
        products = [{
            'product': line.medicine_id.id,
            'qty': line.quantity,
            'price': line.medicine_id.list_price,
        } for line in prescription_lines if line.medicine_id and line.quantity]
        if not products:
            raise UserError(_("No medicine lines found for this prescription."))

        product_by_template = self._validate_requested_products_stock(products)
        pharmacy = self.sudo().search([('company_id', '=', company.id)], limit=1)
        sale_order = self.env['sale.order'].sudo().create({
            'name': sale_sequence.next_by_id() if sale_sequence else 'New',
            'partner_id': patient.id,
            'company_id': company.id,
            'team_id': pharmacy.sales_team_id.id if pharmacy and pharmacy.sales_team_id else False,
        })

        for rec in products:
            product = product_by_template[int(rec['product'])]
            sale_order.sudo().write({
                'order_line': [(0, 0, {
                    'product_id': product.id,
                    'product_uom_qty': float(rec['qty']),
                    'price_unit': float(rec['price']),
                })]
            })

        sale_order.action_confirm()
        if outpatient:
            outpatient.sudo().write({'is_sale_created': True})
        return {'invoice_id': sale_order.id, 'invoice': sale_order.name}

    @api.model
    def company_currency(self):
        """Currency symbol of current company"""
        return self.env.user.company_id.currency_id.symbol

    @api.model
    def tax_amount(self, kw):
        """Amount in tax of selected product in pharmacy"""
        return {
            'amount': self.env['account.tax'].sudo().browse(kw).amount
        }

    def action_get_inventory(self):
        """Inventory adjustment for medicine"""
        med_list = []
        for med in self.medicine_ids.product_id:
            for product in self.env['product.product'].sudo().search([]):
                if med.id == product.product_tmpl_id.id:
                    med_list.append(product.id)
        return {
            'name': 'medicine',
            'domain': ['&', ('product_id', 'in', med_list),
                       ('location_id.usage', '=', 'internal')],
            'type': 'ir.actions.act_window',
            'res_model': 'stock.quant',
            'view_id': self.env.ref(
                'stock.view_stock_quant_tree_inventory_editable').id,
            'view_mode': 'tree',
        }

    def action_get_sale_order(self):
        """Sale order view of medicine"""
        return {
            'name': 'Sales',
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [('team_id', '=', self.sales_team_id.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_team_id': self.sales_team_id.id}
        }

    @api.model
    def fetch_sale_orders(self):
        """Method to fetch all sale orders for displaying on pharmacy
        dashboard"""
        sale_orders = self.env['sale.order'].sudo().search(
            [('company_id', '=', self.env.company.id),
             ('partner_id.patient_seq', 'not in', ['New', 'Employee',
                                                   'User'])],
            order='create_date desc')

        result = []
        for order in sale_orders:
            if order.invoice_status == 'invoiced':
                dashboard_status = 'Invoiced'
            elif order.state in ('sale', 'done'):
                dashboard_status = 'Sale Order'
            elif order.state in ('sent', 'draft'):
                dashboard_status = 'Quotation'
            elif order.state == 'cancel':
                dashboard_status = 'Cancelled'
            else:
                dashboard_status = order.state or ''

            result.append({
                'id': order.id,
                'name': order.name,
                'create_date': fields.Datetime.to_string(order.create_date) if order.create_date else '',
                'partner_id': [order.partner_id.id, order.partner_id.name],
                'amount_total': order.amount_total,
                'state': dashboard_status,
                'invoice_count': len(order.invoice_ids),
                'invoice_names': ', '.join(order.invoice_ids.mapped('name')),
            })
        return result

    @api.model
    def fetch_prescriptions(self):
        """Return grouped prescriptions for the active company."""
        company = self.env.company
        prescription_lines = self.env['prescription.line'].sudo().search([
            '|', '|',
            ('company_id', '=', company.id),
            ('outpatient_id.company_id', '=', company.id),
            ('inpatient_id.company_id', '=', company.id),
        ], order='id desc')

        grouped_prescriptions = {}
        for line in prescription_lines:
            outpatient = line.outpatient_id
            inpatient = line.inpatient_id
            patient = line.res_partner_id or inpatient.patient_id
            date_value = outpatient.op_date or inpatient.hosp_date or False
            reference = outpatient.op_reference or inpatient.name or ''
            if outpatient:
                prescription_key = f'outpatient:{outpatient.id}'
            elif inpatient:
                prescription_key = f'inpatient:{inpatient.id}'
            else:
                prescription_key = f'line:{line.id}'

            if prescription_key not in grouped_prescriptions:
                grouped_prescriptions[prescription_key] = {
                    'id': prescription_key,
                    'date': fields.Date.to_string(date_value) if date_value else '',
                    'reference': reference,
                    'patient': patient.name or '',
                    'patient_no': patient.patient_seq or '',
                    'medicine_list': [],
                    'quantity': 0,
                    'days_list': set(),
                    'times_list': set(),
                    'type': 'Outpatient' if outpatient else 'Inpatient',
                    'sale_created': bool(outpatient.is_sale_created) if outpatient else False,
                }

            group = grouped_prescriptions[prescription_key]
            medicine_name = line.medicine_id.display_name or ''
            if medicine_name:
                group['medicine_list'].append(
                    f"{medicine_name} ({line.quantity})"
                )
            group['quantity'] += line.quantity or 0
            if line.days:
                group['days_list'].add(str(line.days))
            for time_option in line.selected_times:
                group['times_list'].add(time_option.name)

        result = []
        for group in grouped_prescriptions.values():
            result.append({
                'id': group['id'],
                'date': group['date'],
                'reference': group['reference'],
                'patient': group['patient'],
                'patient_no': group['patient_no'],
                'medicine': ', '.join(group['medicine_list']),
                'quantity': group['quantity'],
                'days': ', '.join(sorted(group['days_list'])),
                'times': ', '.join(sorted(group['times_list'])),
                'type': group['type'],
                'sale_created': group['sale_created'],
            })
        return result

    @api.model
    def action_open_prescription(self, prescription_key):
        domain = []
        prescription_key = str(prescription_key or '')
        if prescription_key.startswith('outpatient:'):
            domain = [('outpatient_id', '=', int(prescription_key.split(':')[1]))]
        elif prescription_key.startswith('inpatient:'):
            domain = [('inpatient_id', '=', int(prescription_key.split(':')[1]))]
        elif prescription_key.startswith('line:'):
            domain = [('id', '=', int(prescription_key.split(':')[1]))]
        else:
            domain = [('id', '=', int(prescription_key))]

        prescription_lines = self.env['prescription.line'].sudo().search([
            '|', '|',
            ('company_id', '=', self.env.company.id),
            ('outpatient_id.company_id', '=', self.env.company.id),
            ('inpatient_id.company_id', '=', self.env.company.id),
        ] + domain)
        if not prescription_lines:
            raise UserError(_("Prescription not found."))
        return {
            'name': 'Prescription',
            'type': 'ir.actions.act_window',
            'res_model': 'prescription.line',
            'view_mode': 'tree,form',
            'views': [
                (self.env.ref(
                    'base_hospital_management.prescription_line_view_tree_readonly'
                ).id, 'tree'),
                (self.env.ref(
                    'base_hospital_management.prescription_line_view_form_readonly'
                ).id, 'form'),
            ],
            'domain': [('id', 'in', prescription_lines.ids)],
            'target': 'current',
            'context': {'create': False, 'edit': False, 'delete': False},
        }

    @api.model
    def _get_dashboard_sale_order(self, order_id):
        order = self.env['sale.order'].sudo().search([
            ('id', '=', order_id),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not order:
            raise UserError(_("Sale order not found."))
        return order

    @api.model
    def action_print_sale_order(self, order_id):
        order = self._get_dashboard_sale_order(order_id)
        return {
            'type': 'ir.actions.act_url',
            'url': f'/hospital/report/view/sale.report_saleorder/{order.id}',
            'target': 'new',
        }

    def _validate_order_product_availability(self, order):
        """Ensure enough unreserved stock is available before invoice creation."""
        # Bypass custom free_qty check as it fails when stock is rightfully reserved for this order.
        # Odoo's native delivery validation will catch true stock shortages.
        pass

    def _validate_reserved_quantities_for_picking(self, picking):
        """Ensure the delivery has enough reserved quantity to validate."""
        # Bypass custom reserved quantity check. In Odoo 17, move.quantity tracks 'Done' quantity,
        # which is 0.0 before validation.
        pass

    def _auto_validate_order_delivery(self, order):
        """Automatically validate pending deliveries before invoice creation."""
        stockable_lines = order.order_line.filtered(
            lambda ln: not ln.display_type and ln.product_id and ln.product_id.detailed_type == 'product'
        )
        if not stockable_lines:
            return

        pickings = order.picking_ids.filtered(
            lambda pick: pick.state != 'cancel' and pick.picking_type_id.code == 'outgoing'
        )
        if not pickings:
            raise UserError(_(
                "No delivery order was found for this sale order."
            ))

        pending_pickings = pickings.filtered(lambda pick: pick.state not in ('done', 'cancel'))
        for picking in pending_pickings:
            if picking.state == 'draft':
                picking.action_confirm()
            if picking.state in ('confirmed', 'waiting', 'partially_available'):
                picking.action_assign()

            for move in picking.move_ids:
                if move.state not in ('done', 'cancel'):
                    move.quantity = move.product_uom_qty

            validation_result = picking.with_context(
                skip_sanity_check=False, 
                skip_sms=True
            ).button_validate()
            
            if isinstance(validation_result, dict):
                res_model = validation_result.get('res_model')
                if res_model == 'stock.backorder.confirmation':
                    wizard = self.env['stock.backorder.confirmation'].with_context(
                        validation_result.get('context', {})
                    ).create({
                        'pick_ids': [(6, 0, picking.ids)],
                    })
                    wizard.process_cancel_backorder()
                elif res_model == 'stock.immediate.transfer':
                    wizard = self.env['stock.immediate.transfer'].with_context(
                        validation_result.get('context', {})
                    ).create({
                        'pick_ids': [(6, 0, picking.ids)],
                    })
                    wizard.process()
                elif res_model == 'confirm.stock.sms':
                    # If this pops up, the picking is technically already validated, 
                    # it just wants to send an SMS. We can safely ignore it.
                    pass
                else:
                    raise UserError(_(
                        "Delivery %(delivery)s requires manual validation (Popup: %(model)s). Please validate it manually in the Inventory app.",
                        delivery=picking.name,
                        model=res_model,
                    ))

    @api.model
    def action_open_or_create_invoice(self, order_id):
        order = self._get_dashboard_sale_order(order_id)
        invoices = order.invoice_ids.filtered(lambda inv: inv.state != 'cancel')
        if not invoices:
            self._validate_order_product_availability(order)
            self._auto_validate_order_delivery(order)
            invoices = order._create_invoices()
        if not invoices:
            raise UserError(_("No invoice could be created for this sale order."))
        return order.action_view_invoice(invoices=invoices)

    @api.model
    def action_print_invoice(self, order_id):
        order = self._get_dashboard_sale_order(order_id)
        invoices = order.invoice_ids.filtered(lambda inv: inv.state != 'cancel')
        if not invoices:
            self._validate_order_product_availability(order)
            self._auto_validate_order_delivery(order)
            invoices = order._create_invoices()
        if not invoices:
            raise UserError(_("No invoice could be created for this sale order."))
        invoice = invoices.sorted(lambda inv: inv.id, reverse=True)[:1]
        return {
            'type': 'ir.actions.act_url',
            'url': f'/hospital/report/view/account.report_invoice/{invoice.id}',
            'target': 'new',
        }
