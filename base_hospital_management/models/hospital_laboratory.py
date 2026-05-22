
from odoo import api, fields, models


class HospitalLaboratory(models.Model):
    """Class holding laboratory details"""
    _name = 'hospital.laboratory'
    _description = 'Hospital Laboratory'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company.id,
                                 help='Indicates the company')

    notes = fields.Text(string='Notes', help='Notes regarding the laboratory')
    image_130 = fields.Image(max_width=128, max_height=128, string='Image',
                             help='Image of the laboratory')
    phone = fields.Char(string='Phone', required=True, help='Phone number of laboratory')
    mobile = fields.Char(string='Mobile', help='Mobile number of'
                                               ' laboratory')
    email = fields.Char(string='Email', help='Email of the laboratory')
    street = fields.Char(string='Street', help='Street name of lab')
    street2 = fields.Char(string='Street2', help='Street2 name of lab')
    zip = fields.Char(string='Zip', help='Zip code of lab')
    city = fields.Char(string='City', help="City of lab")
    state_id = fields.Many2one("res.country.state",
                               string='State',
                               help='State of lab')
    country_id = fields.Many2one('res.country',
                                 related='state_id.country_id',
                                 string='Country',
                                 help='Country name of lab')
    note = fields.Text(string='Note', help='Notes regarding lab')
    name = fields.Char(string='Lab Sequence', help='Sequence number for lab',
                       copy=False,
                       readonly=True, index=1, default=lambda self: 'New')
    technician_id = fields.Many2one('hr.employee',
                                    string="Lab in charge",
                                    domain=[
                                        ('job_title', '=', 'Lab Technician')],
                                    help='Name of the lab technician who has '
                                         'the in charge')

    @api.model
    def create(self, vals):
        """Method for creating lab sequence number"""
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'laboratory.sequence') or 'New'
        return super().create(vals)
