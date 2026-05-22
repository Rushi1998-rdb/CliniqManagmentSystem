
from odoo import fields, models


class MedicineBrand(models.Model):
    """Model holding all medicine brands"""
    _name = 'medicine.brand'
    _description = 'Medicine Brand'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company.id,
                                 help='Indicates the company')

    name = fields.Char(string="Brand", help='Name of the brand')
    medicine_ids = fields.One2many('product.template',
                                   'medicine_brand_id',
                                   string='Medicine',
                                   help='All medicines belongs to this brand')
