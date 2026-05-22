import re

from odoo import Command, api, fields, models, _
from odoo.addons.purchase.models.purchase_order import PurchaseOrder as PurchaseOrderCore
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    current_company_partner_id = fields.Many2one(
        'res.partner',
        compute='_compute_current_company_partner_id',
        compute_sudo=True,
    )
    current_company_partner_ref = fields.Integer(
        compute='_compute_current_company_partner_id',
        compute_sudo=True,
    )

    def _compute_current_company_partner_id(self):
        for order in self:
            company = order.company_id or self.env.company
            order.current_company_partner_id = company.partner_id
            order.current_company_partner_ref = company.partner_id.id

    def onchange(self, values, field_names, fields_spec):
        return super(
            PurchaseOrder,
            self.with_context(
                allow_supplier_partner_read=True,
                res_partner_search_mode='supplier',
                default_supplier_rank=1,
            ),
        ).onchange(values, field_names, fields_spec)

    def _has_net_received_qty(self):
        self.ensure_one()
        return any(
            not float_is_zero(
                line.qty_received,
                precision_rounding=line.product_uom.rounding,
            )
            for line in self.order_line
        )

    def button_cancel(self):
        for order in self:
            active_bills = order.invoice_ids.filtered(
                lambda inv: inv.state not in ('cancel', 'draft')
            )
            if active_bills:
                raise UserError(_(
                    "Unable to cancel purchase order %s. "
                    "You must first reverse or cancel the related vendor bills."
                ) % order.name)

            done_moves = order.order_line.mapped('move_ids').filtered(
                lambda move: move.state == 'done'
            )
            if done_moves and order._has_net_received_qty():
                raise UserError(_(
                    "Unable to cancel purchase order %s as some receptions have already been done."
                ) % order.name)

            if order.state in ('draft', 'sent', 'to approve', 'purchase'):
                for order_line in order.order_line:
                    order_line.move_ids.filtered(
                        lambda move: move.state != 'done'
                    )._action_cancel()
                    if order_line.move_dest_ids:
                        move_dest_ids = order_line.move_dest_ids.filtered(
                            lambda move: move.state != 'done' and not move.scrapped
                        )
                        moves_to_unlink = move_dest_ids.filtered(
                            lambda move: len(move.created_purchase_line_ids.ids) > 1
                        )
                        if moves_to_unlink:
                            moves_to_unlink.created_purchase_line_ids = [
                                Command.unlink(order_line.id)
                            ]
                        move_dest_ids -= moves_to_unlink
                        if order_line.propagate_cancel:
                            move_dest_ids._action_cancel()
                        else:
                            move_dest_ids.write({'procure_method': 'make_to_stock'})
                            move_dest_ids._recompute_state()

            for picking in order.picking_ids.filtered(
                lambda picking: picking.state not in ('cancel', 'done')
            ):
                picking.action_cancel()

            order.order_line.write({'move_dest_ids': [(5, 0, 0)]})

        result = PurchaseOrderCore.button_cancel(self)
        self.sudo()._activity_cancel_on_sale()
        return result

    @api.model
    def _get_company_purchase_sequence(self, company):
        sequence = self.env['ir.sequence'].sudo().search([
            ('code', '=', 'purchase.order'),
            ('company_id', '=', company.id),
        ], limit=1)
        if sequence:
            return sequence

        template = self.env['ir.sequence'].sudo().search([
            ('code', '=', 'purchase.order'),
            ('company_id', '=', False),
        ], limit=1)
        if not template:
            template = self.env['ir.sequence'].sudo().create({
                'name': 'Purchase Order Sequence Template',
                'code': 'purchase.order',
                'prefix': 'P',
                'padding': 5,
                'number_next': 1,
                'number_increment': 1,
                'company_id': False,
            })

        existing_orders = self.sudo().search([
            ('company_id', '=', company.id),
            ('name', '=ilike', 'P%'),
        ])
        next_number = 1
        sequence_numbers = []
        for order in existing_orders:
            match = re.search(r'P(\d+)$', order.name or '')
            if match:
                sequence_numbers.append(int(match.group(1)))
        if sequence_numbers:
            next_number = max(sequence_numbers) + 1

        return template.copy({
            'name': f"Purchase Order Sequence ({company.name})",
            'company_id': company.id,
            'prefix': 'P',
            'padding': 5,
            'number_next': next_number,
        })

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            company = self.env['res.company'].browse(
                vals.get('company_id') or self.env.company.id
            )
            vals.setdefault('company_id', company.id)
            if vals.get('name', 'New') == 'New':
                sequence = self._get_company_purchase_sequence(company)
                vals['name'] = sequence.with_company(company).next_by_id()
        return super().create(vals_list)
