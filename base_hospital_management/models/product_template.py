
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    """Inherited to add more fields and functions"""
    _inherit = 'product.template'

    medicine_ok = fields.Boolean(string='Medicine', help='True for medicines')
    vaccine_ok = fields.Boolean(string="Vaccine", help='True for vaccines')
    pharmacy_id = fields.Many2one('hospital.pharmacy',
                                  string='Pharmacy',
                                  help='Name of the pharmacy')
    medicine_brand_id = fields.Many2one('medicine.brand',
                                        string='Brand',
                                        help='Indicates the brand of medicine '
                                             'or vaccine')
    medicine_type = fields.Selection([
        ('tablet', 'Tablet'),
        ('syrup', 'Syrup'),
        ('capsule', 'Capsule'),
        ('injection', 'Injection'),
        ('cream', 'Cream/Ointment'),
        ('drops', 'Drops'),
        ('other', 'Other')
    ], string='Medicine Type', default='tablet', help='Type of medicine')
    
    volume_per_bottle = fields.Float(
        string='Volume/Qty per Bottle', 
        default=1.0,
        help='Total volume or quantity in one stock unit (e.g., 100 for a 100ml bottle)'
    )
    
    dosage_uom = fields.Selection([
        ('unit', 'Unit (Tab/Cap/Inj)'),
        ('ml', 'ml'),
        ('mg', 'mg'),
        ('drops', 'Drops'),
        ('gram', 'Gram')
    ], string='Dosage Unit', default='unit', help='Unit for dosage calculation')
    low_stock_threshold = fields.Float(
        string='Low Stock Threshold',
        default=10.0,
        help='Show a low stock warning when medicine stock goes below this quantity.',
    )
    low_stock_warning = fields.Boolean(
        string='Low Stock Warning',
        compute='_compute_low_stock_warning',
        help='Technical field used to highlight medicines that need restocking.',
    )

    @api.depends('medicine_ok', 'qty_available', 'low_stock_threshold')
    def _compute_low_stock_warning(self):
        for record in self:
            record.low_stock_warning = (
                record.medicine_ok
                and record.qty_available < record.low_stock_threshold
            )

    @api.model_create_multi
    def create(self, vals_list):
        normalized_vals_list = []
        for vals in vals_list:
            vals = dict(vals)
            if not vals.get('company_id'):
                vals['company_id'] = self.env.company.id
            normalized_vals_list.append(vals)
        return super().create(normalized_vals_list)

    def write(self, vals):
        result = super().write(vals)
        if vals.get('medicine_ok') or vals.get('vaccine_ok'):
            self.filtered(lambda rec: not rec.company_id).sudo().write({
                'company_id': self.env.company.id,
            })
        return result

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'company_id' in fields_list and not res.get('company_id'):
            res['company_id'] = self.env.company.id
        return res

    @api.model
    def action_assign_shared_products_to_current_company(self):
        """Make old shared products company-bound so they stop showing globally."""
        ProductProduct = self.env['product.product'].sudo()
        StockMove = self.env['stock.move'].sudo()
        StockQuant = self.env['stock.quant'].sudo()
        for template in self.sudo().search([('company_id', '=', False)]):
            company = self.env['res.company']
            variant_ids = ProductProduct.search([
                ('product_tmpl_id', '=', template.id),
            ]).ids
            if variant_ids:
                move_companies = StockMove.search([
                    ('product_id', 'in', variant_ids),
                    ('company_id', '!=', False),
                ]).mapped('company_id')
                if len(move_companies) > 1:
                    _logger.warning(
                        "Skipping shared product %s because it has stock moves in multiple companies: %s",
                        template.display_name,
                        ", ".join(move_companies.mapped('name')),
                    )
                    continue
                company = move_companies[:1]

            if not company and variant_ids:
                quant_companies = StockQuant.search([
                    ('product_id', 'in', variant_ids),
                    ('company_id', '!=', False),
                ]).mapped('company_id')
                if len(quant_companies) > 1:
                    _logger.warning(
                        "Skipping shared product %s because it has stock quantities in multiple companies: %s",
                        template.display_name,
                        ", ".join(quant_companies.mapped('name')),
                    )
                    continue
                company = quant_companies[:1]

            if not company:
                company = template.create_uid.company_id
            if not company:
                company = self.env.company
            try:
                template.write({'company_id': company.id})
            except UserError as error:
                _logger.warning(
                    "Skipping shared product %s during company cleanup: %s",
                    template.display_name,
                    error,
                )
        return True

    @api.model
    def action_get_medicine_data(self):
        """Returns medicine list to the pharmacy dashboard"""
        medicines = []
        for rec in self.env['product.template'].search([
            ('medicine_ok', '=', True),
            ('company_id', '=', self.env.company.id),
        ]):
            medicines.append(
                [rec.name, rec.list_price, rec.qty_available, rec.image_1920, rec.id,
                 rec.low_stock_threshold])
        return medicines

    @api.model
    def action_get_vaccine_data(self):
        """Returns vaccine list to the pharmacy dashboard"""
        vaccines = []
        for rec in self.env['product.template'].search([
            ('vaccine_ok', '=', True),
            ('company_id', '=', self.env.company.id),
        ]):
            vaccines.append(
                [rec.name, rec.list_price, rec.qty_available, rec.image_1920])
        return vaccines


class ProductProduct(models.Model):
    """Expose medicine low-stock fields on product variants for variant views."""
    _inherit = 'product.product'

    low_stock_threshold = fields.Float(
        related='product_tmpl_id.low_stock_threshold',
        readonly=False,
    )
    low_stock_warning = fields.Boolean(
        related='product_tmpl_id.low_stock_warning',
    )
