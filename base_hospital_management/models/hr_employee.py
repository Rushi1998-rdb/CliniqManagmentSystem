import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)
class HrEmployee(models.Model):
    """Inherited to add more fields and functions"""
    _inherit = 'hr.employee'

    doctor = fields.Boolean(string='Doctor', help='True for Doctors')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  help='Currency in which consultation fee '
                                       'is calculating',
                                  default=lambda self: self.env.user.company_id
                                  .currency_id.id,
                                  required=True)
    coach_id = fields.Many2one('hr.employee', string='Coach',
                               help='Name of the coach')
    consultancy_charge = fields.Monetary(string="Consultation Charge",
                                         help='Charge for consultation')
    consultancy_type = fields.Selection([('resident', 'Residential'),
                                         ('special', 'Specialist')],
                                        string="Consultation Type",
                                        help='Select the type of Consultation')
    time_avg = fields.Float(string='Average Time for a Patient',
                            help="Average Consultation time "
                                 "per Patient in minutes")
    degree_ids = fields.Many2many('hospital.degree',
                                  string="Degree",
                                  help='Degrees of staff')
    pharmacy_id = fields.Many2one('hospital.pharmacy',
                                  string="Pharmacy",
                                  help='Name of the pharmacy')
    specialization_ids = fields.Many2many('doctor.specialization',
                                          string="Specialization",
                                          help="Doctors specialization for"
                                               " an area")
    
    password = fields.Char(
        string='Password',
        help='Password for the employee portal/user account'
    )

    def _employee_partner_field_name(self):
        """Keep compatibility with employee models that expose different
        contact fields across Odoo versions/customizations.
        """
        self.ensure_one()
        if 'address_home_id' in self._fields:
            return 'address_home_id'
        return 'work_contact_id'

    def _employee_partner(self):
        self.ensure_one()
        return self[self._employee_partner_field_name()]

    def _set_employee_partner(self, partner):
        self.ensure_one()
        self[self._employee_partner_field_name()] = partner.id if partner else False

    def action_create_user(self):
        """Updating employee field of res user to true"""
        self.ensure_one()
        if self.user_id:
            raise ValidationError(_("This employee already has an user."))
        return {
            'name': _('Create User'),
            'type': 'ir.actions.act_window',
            'res_model': 'res.users',
            'view_mode': 'form',
            'view_id': self.env.ref('hr.view_users_simple_form').id,
            'target': 'new',
            'context': {
                'default_create_employee_id': self.id,
                'default_name': self.name,
                'default_phone': self.work_phone,
                'default_mobile': self.mobile_phone,
                'default_login': self.work_email,
                'default_partner_id': self.work_contact_id.id,
                'default_employee': True,
                'default_password': self.password,  # Pass the password
            }
        }

    @api.model
    def get_current_employee_profile(self):
        """Return the best matching employee for the logged-in user.

        This keeps the dashboard/profile logic stable in multi-company setups
        where the linkage might exist through user, partner, or work email.
        """
        user = self.env.user
        company = self.env.company
        base_domain = [('company_id', 'in', self.env.companies.ids)]
        employee = self.sudo().search(
            base_domain + [('user_id', '=', user.id), ('company_id', '=', company.id)],
            limit=1,
        )

        if not employee and user.partner_id:
            partner_field = self._employee_partner_field_name()
            employee = self.sudo().search(
                base_domain + [
                    (partner_field, '=', user.partner_id.id),
                    ('company_id', '=', company.id),
                ],
                limit=1,
            )

        if not employee and user.login:
            employee = self.sudo().search(
                base_domain + [
                    ('work_email', '=', user.login),
                    ('company_id', '=', company.id),
                ],
                limit=1,
            )

        if not employee:
            employee = self.sudo().search(
                base_domain + [('user_id', '=', user.id)],
                order='company_id',
                limit=1,
            )

        return {
            'employee_id': employee.id if employee else False,
            'company_id': employee.company_id.id if employee else False,
            'image_1920': employee.image_1920 if employee else False,
        }

    @api.model
    def get_company_doctors(self):
        """Return doctors for the active company.

        Used by receptionist-facing flows where the user may not have direct
        read access to all employee details, but still needs the current
        company's doctor list.
        """
        doctors = self.sudo().search([
            ('company_id', '=', self.env.company.id),
            ('job_id.name', '=', 'Doctor'),
        ], order='name')
        return doctors.read(['display_name'])

    def _inverse_work_contact_details(self):
        """Override to prevent creating patient while creating a staff"""
        for employee in self:
            if not employee.work_contact_id:
                employee.work_contact_id = self.env[
                    'res.partner'].sudo().create(
                    {
                        'email': employee.work_email,
                        'mobile': employee.mobile_phone,
                        'name': employee.name,
                        'image_1920': employee.image_1920,
                        'company_id': employee.company_id.id,
                        'patient_seq': 'Employee'
                    })
            else:
                employee.work_contact_id.sudo().write({
                    'email': employee.work_email,
                    'mobile': employee.mobile_phone,
                    'patient_seq': 'Employee'
                })
    
    @api.model
    def create(self, vals):
        """Create employee and optionally create user with password"""
        employee = super().create(vals)
        
        # If password is provided and user doesn't exist, create user
        if vals.get('password') and not employee.user_id:
            try:
                # Create partner if doesn't exist
                employee_partner = employee._employee_partner()
                if not employee_partner:
                    partner = self.env['res.partner'].create({
                        'name': employee.name,
                        'email': employee.work_email or employee.private_email,
                        'phone': employee.work_phone or employee.private_phone or employee.mobile_phone,
                        'mobile': employee.mobile_phone,
                        'company_id': employee.company_id.id,
                        'patient_seq': 'Employee',
                    })
                    employee._set_employee_partner(partner)
                    employee_partner = partner
                
                # Create user
                user_vals = {
                    'name': employee.name,
                    'login': employee.work_email or employee.private_email or employee.name.replace(' ', '').lower(),
                    'password': vals.get('password'),
                    'partner_id': employee_partner.id if employee_partner else False,
                    'employee_ids': [(4, employee.id)],
                }
                
                if employee.work_email:
                    user_vals['email'] = employee.work_email
                elif employee.private_email:
                    user_vals['email'] = employee.private_email
                
                user = self.env['res.users'].create(user_vals)
                employee.user_id = user.id
                
            except Exception as e:
                _logger.warning(f"Could not create user for employee {employee.name}: {str(e)}")
        
        return employee
    
    def write(self, vals):
        """Update user password when employee password is updated"""
        result = super().write(vals)
        
        if vals.get('password'):
            for employee in self:
                if employee.user_id:
                    employee.user_id.write({'password': vals['password']})

        if vals.get('user_id'):
            for employee in self:
                if employee.user_id and employee.user_id.partner_id:
                    if employee._employee_partner() != employee.user_id.partner_id:
                        employee._set_employee_partner(employee.user_id.partner_id)
        
        return result
# from odoo import api, fields, models, _
# from odoo.exceptions import ValidationError


# class HrEmployee(models.Model):
#     """Inherited to add more fields and functions"""
#     _inherit = 'hr.employee'

#     doctor = fields.Boolean(string='Doctor', help='True for Doctors')
#     currency_id = fields.Many2one('res.currency', string='Currency',
#                                   help='Currency in which consultation fee '
#                                        'is calculating',
#                                   default=lambda self: self.env.user.company_id
#                                   .currency_id.id,
#                                   required=True)
#     coach_id = fields.Many2one('hr.employee', string='Coach',
#                                help='Name of the coach')
#     consultancy_charge = fields.Monetary(string="Consultation Charge",
#                                          help='Charge for consultation')
#     consultancy_type = fields.Selection([('resident', 'Residential'),
#                                          ('special', 'Specialist')],
#                                         string="Consultation Type",
#                                         help='Select the type of Consultation')
#     time_avg = fields.Float(string='Average Time for a Patient',
#                             help="Average Consultation time "
#                                  "per Patient in minutes")
#     degree_ids = fields.Many2many('hospital.degree',
#                                   string="Degree",
#                                   help='Degrees of staff')
#     pharmacy_id = fields.Many2one('hospital.pharmacy',
#                                   string="Pharmacy",
#                                   help='Name of the pharmacy')
#     specialization_ids = fields.Many2many('doctor.specialization',
#                                           string="Specialization",
#                                           help="Doctors specialization for"
#                                                " an area")

#     def action_create_user(self):
#         """Updating employee field of res user to true"""
#         self.ensure_one()
#         if self.user_id:
#             raise ValidationError(_("This employee already has an user."))
#         return {
#             'name': _('Create User'),
#             'type': 'ir.actions.act_window',
#             'res_model': 'res.users',
#             'view_mode': 'form',
#             'view_id': self.env.ref('hr.view_users_simple_form').id,
#             'target': 'new',
#             'context': {
#                 'default_create_employee_id': self.id,
#                 'default_name': self.name,
#                 'default_phone': self.work_phone,
#                 'default_mobile': self.mobile_phone,
#                 'default_login': self.work_email,
#                 'default_employee': True
#             }
#         }

#     def _inverse_work_contact_details(self):
#         """Override to prevent creating patient while creating a staff"""
#         for employee in self:
#             if not employee.work_contact_id:
#                 employee.work_contact_id = self.env[
#                     'res.partner'].sudo().create(
#                     {
#                         'email': employee.work_email,
#                         'mobile': employee.mobile_phone,
#                         'name': employee.name,
#                         'image_1920': employee.image_1920,
#                         'company_id': employee.company_id.id,
#                         'patient_seq': 'Employee'
#                     })
#             else:
#                 employee.work_contact_id.sudo().write({
#                     'email': employee.work_email,
#                     'mobile': employee.mobile_phone,
#                     'patient_seq': 'Employee'
#                 })

#     password = fields.Char(
#         string='Password',
#         help='Password for the employee portal/user account'
#     )
    
#     @api.model
#     def create(self, vals):
#         """Create employee and optionally create/create user with password"""
#         employee = super().create(vals)
        
#         # If password is provided and user doesn't exist, create user
#         if vals.get('password') and not employee.user_id:
#             try:
#                 # Create partner if doesn't exist
#                 if not employee.address_home_id:
#                     partner = self.env['res.partner'].create({
#                         'name': employee.name,
#                         'email': employee.work_email or employee.email,
#                         'phone': employee.phone or employee.mobile_phone,
#                     })
#                     employee.address_home_id = partner.id
                
#                 # Create user
#                 user_vals = {
#                     'name': employee.name,
#                     'login': employee.work_email or employee.email or employee.name.replace(' ', '').lower(),
#                     'password': vals.get('password'),
#                     'partner_id': employee.address_home_id.id if employee.address_home_id else False,
#                     'employee_ids': [(4, employee.id)],
#                 }
                
#                 if employee.work_email:
#                     user_vals['email'] = employee.work_email
#                 elif employee.email:
#                     user_vals['email'] = employee.email
                
#                 user = self.env['res.users'].create(user_vals)
#                 employee.user_id = user.id
                
#             except Exception as e:
#                 pass  # Don't block employee creation if user creation fails
        
#         return employee
    
#     def write(self, vals):
#         """Update user password when employee password is updated"""
#         result = super().write(vals)
        
#         if vals.get('password'):
#             for employee in self:
#                 if employee.user_id:
#                     employee.user_id.write({'password': vals['password']})
        
#         return result
