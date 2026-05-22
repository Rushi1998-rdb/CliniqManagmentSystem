
from odoo import api, fields, models


class LabMedicineLine(models.Model):
    """Class holding Lab medicines"""
    _name = 'lab.medicine.line'
    _description = 'Lab Medicine Line'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company.id,
                                 help='Indicates the company')

    lab_test_id = fields.Many2one('patient.lab.test',
                                  string='Lab Test Line',
                                  help='Lab test corresponds to the medicine')
    test_id = fields.Many2one('lab.test', string='Test',
                              help='Test corresponds to medicine')
    medicine_id = fields.Many2one('product.template',
                                  domain="['|', ('medicine_ok', '=', True), ('vaccine_ok', '=', True)]",
                                  required=True, string='Medicine',
                                  help='Medicine for the lab test')
    quantity = fields.Integer(string='Quantity', default=1,
                              help='Quantity of medicine')
    qty_available = fields.Float(string='Available', help='Available quantity',
                                 related='medicine_id.qty_available')
    price = fields.Float(string='Price', help='Price for the medicine',
                         related='medicine_id.list_price')
    sub_total = fields.Float(string='Subtotal',
                             help='Total cost of the medicine',
                             compute='_compute_sub_total')

    @api.depends('quantity', 'price')
    def _compute_sub_total(self):
        """Method for computing total amount"""
        for rec in self:
            rec.sub_total = rec.price * rec.quantity
