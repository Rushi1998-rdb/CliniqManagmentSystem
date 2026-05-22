
from odoo import fields, models


class PatientRoom(models.Model):
    """Class holding Patient room details"""
    _name = 'patient.room'
    _description = 'Patient Room'

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company.id,
                                 help='Indicates the company')

    name = fields.Char(string="Name", help='The name of room', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.user.company_id
                                  .currency_id.id,
                                  required=True, help='Currency in which '
                                                      'payments will be done')
    building_id = fields.Many2one('hospital.building',
                                  string="Block Name",
                                  required=True, help='Building to which '
                                                        'the room corresponds '
                                                        'to')
    nurse_ids = fields.Many2many('hr.employee', string='Nurses',
                                 domain="[('job_id.name','=','Nurse')]",
                                 help='Nurses of the room')
    bed_type = fields.Selection([('gatch', 'Gatch Bed'),
                                 ('electric', 'Electric'),
                                 ('stretcher', 'Stretcher'),
                                 ('low', 'Low Bed'),
                                 ('air', 'Low Air Loss'),
                                 ('circo', 'Circo Electric'),
                                 ('clinitron', 'Clinitron'),
                                 ], string="Bed Type", help='Select the type '
                                                            'of bed')
    rent = fields.Monetary(string='Rent', help='Rent for the room')
    state = fields.Selection([('avail', 'Available'),
                              ('reserve', 'Reserve'),
                              ('not', 'Unavailable'), ],
                             string='State', readonly=True,
                             default="avail", help='State of room')
    room_facilities_ids = fields.Many2many('room.facility',
                                           string='Facilities',
                                           help='Facilities of room')
    floor_no = fields.Integer(string="Floor No.", help='The floor to '
                                                       'which the room '
                                                       'corresponds to')

    _sql_constraints = [('unique_room', 'unique (name)',
                         'Room number should be unique!')]
