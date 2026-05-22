
from odoo import fields, models


class HospitalBed(models.Model):
    """Class holding hospital bed details"""
    _name = 'hospital.bed'
    _description = 'Beds'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company.id,
                                 help='Indicates the company')

    _sql_constraints = [('unique_room', 'unique (name)',
                         'Bed number should be unique!')]
    name = fields.Char(string="Bed Number", help='Indicates the unique '
                                                 'number for a bed',
                       required=True)
    bed_type = fields.Selection([('gatch', 'Gatch Bed'),
                                 ('electric', 'Electric'),
                                 ('stretcher', 'Stretcher'),
                                 ('low', 'Low Bed'),
                                 ('air', 'Low Air Loss'),
                                 ('circo', 'Circo Electric'),
                                 ('clinitron', 'Clinitron'),
                                 ], string="Type", help='Type of bed')
    note = fields.Text(string="Notes", help='Notes regarding bed')
    ward_id = fields.Many2one('hospital.ward', string="Ward",
                              help='Indicates the ward to which the bed'
                                   ' belongs to')
    room_id = fields.Many2one('patient.room', string="Room",
                              help='Indicates the room to which the bed'
                                   ' belongs to')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  help='Currency in which bed rent calculates',
                                  default=lambda self:
                                  self.env.user.company_id.currency_id.id,
                                  required=True)
    bed_rent = fields.Monetary(string='Rent', help="The charge for the bed")
    state = fields.Selection([('avail', 'Available'), ('not', 'Unavailable')],
                             string='State', readonly=True,
                             help='State of the bed',
                             default="avail")
