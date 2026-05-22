
from odoo import fields, models


class RoomFacility(models.Model):
    """Class holding room facilities"""
    _name = 'room.facility'
    _description = 'Room Facility'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company.id,
                                 help='Indicates the company')

    name = fields.Char(string="Facilities", help='Name of room facility')
