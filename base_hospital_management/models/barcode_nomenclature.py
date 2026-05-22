from odoo import fields, models


class BarcodeNomenclature(models.Model):
    """Extend barcode.nomenclature to add multi-company support."""
    _inherit = 'barcode.nomenclature'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
    )
