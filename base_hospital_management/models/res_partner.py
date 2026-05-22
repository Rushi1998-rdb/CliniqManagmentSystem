import logging
import math
import re
import base64
from datetime import date, datetime
from barcode import EAN13
from barcode.writer import ImageWriter
from dateutil.relativedelta import *
from odoo import api, fields, models
from io import BytesIO
from odoo.exceptions import ValidationError
from odoo.osv import expression

_logger = logging.getLogger(__name__)
_logger.info("RES_PARTNER MODEL LOADED SUCCESSFULLY")

class ResPartner(models.Model):
    """Inherited to add more fields and functions"""
    _inherit = 'res.partner'
    _description = 'Hospital Patients'

    @api.model
    def _format_dashboard_dob(self, dob_value):
        """Format a date value for dashboard display as dd/mm/yyyy."""
        dob_date = fields.Date.to_date(dob_value) if dob_value else False
        return dob_date.strftime('%d/%m/%Y') if dob_date else ''

    @api.model
    def _format_age_display(self, dob_value):
        dob_date = fields.Date.to_date(dob_value) if dob_value else False
        if not dob_date:
            return ''
        age_delta = relativedelta(date.today(), dob_date)
        return f"{age_delta.years} yrs {age_delta.months} months"

    def _normalize_internal_partner_company(self):
        """Keep internal system/user contacts company-neutral.

        This prevents login/chat bootstrap errors on bot and user partners
        while leaving hospital patient records company-bound.
        """
        internal_partners = self.filtered(
            lambda rec: rec.company_id and (
                rec.user_ids
                or (not rec.patient_seq and rec.name and 'bot' in rec.name.lower())
            )
        )
        if internal_partners:
            super(ResPartner, internal_partners).write({'company_id': False})

    def init(self):
        super().init()
        self.env.cr.execute(
            """
            UPDATE res_partner
               SET company_id = NULL
             WHERE company_id IS NOT NULL
               AND (
                    id IN (SELECT partner_id FROM res_users WHERE partner_id IS NOT NULL)
                    OR (patient_seq IS NULL AND LOWER(COALESCE(name, '')) LIKE '%bot%')
               )
            """
        )
        self.env.cr.execute(
            """
            UPDATE res_partner
               SET patient_seq = NULL
             WHERE patient_seq = 'New'
               AND supplier_rank > 0
            """
        )

    def _is_hospital_user(self):
        user = self.env['res.users'].sudo().browse(self.env.uid)
        return any([
            user.has_group('base_hospital_management.base_hospital_management_group_manager'),
            user.has_group('base_hospital_management.base_hospital_management_group_receptionist'),
            user.has_group('base_hospital_management.base_hospital_management_group_doctor'),
            user.has_group('base_hospital_management.base_hospital_management_group_nurse'),
            user.has_group('base_hospital_management.base_hospital_management_group_lab_assistant'),
            user.has_group('base_hospital_management.base_hospital_management_group_pharmacist'),
        ])

    def _is_supplier_context(self):
        return bool(
            self.env.context.get('default_supplier_rank', 0) > 0
            or self.env.context.get('res_partner_search_mode') == 'supplier'
            or self.env.context.get('search_default_supplier')
        )

    def check_access_rights(self, operation, raise_exception=True):
        if operation in ('read', 'create', 'write') and (
            self._is_supplier_context()
            or self._is_hospital_user()
        ):
            return True
        return super().check_access_rights(
            operation,
            raise_exception=raise_exception,
        )

    def _hospital_partner_read_bypass_domain(self):
        allowed_company_ids = self.env.companies.ids or [self.env.company.id]
        return [
            ('id', 'in', self.ids),
            '|', '|', '|', '|', '|',
            ('id', '=', self.env.company.partner_id.id),
            ('patient_seq', '=', False),
            ('user_ids.company_ids', 'in', allowed_company_ids),
            ('patient_seq', 'in', ['Employee', 'User']),
            '&', ('supplier_rank', '>', 0), ('company_id', 'in', allowed_company_ids),
            '&', ('customer_rank', '=', 0), ('company_id', 'in', allowed_company_ids),
        ]

    @api.model
    def _get_company_partner_ids(self):
        return self.env.companies.sudo().mapped('partner_id').ids

    def _get_safe_hospital_partner_ids(self):
        """Partners that hospital users may read without exposing patients."""
        allowed_company_ids = self.env.companies.ids or [self.env.company.id]
        domain = [
            ('id', 'in', self.ids),
            '|', '|', '|', '|',
            ('id', '=', self.env.user.partner_id.id),
            ('id', '=', self.env.company.partner_id.id),
            ('id', 'in', self._get_company_partner_ids()),
            ('user_ids.company_ids', 'in', allowed_company_ids),
            '&', ('supplier_rank', '>', 0),
            ('company_id', 'in', allowed_company_ids),
        ]
        return set(
            self.sudo()
            .with_context(_skip_hospital_partner_rule=True)
            .search(domain)
            .ids
        )

    def _split_hospital_patient_records(self):
        """Split current partners into actual patients vs safe generic contacts.
        Actual patients have a sequence ID and are not companies/users.
        """
        patient_records = self.browse()
        safe_records = self.browse()
        allowed_company_ids = self.env.companies.ids or [self.env.company.id]
        safe_ids = self._get_safe_hospital_partner_ids() if self.ids else set()

        for record in self.sudo().with_context(_skip_hospital_partner_rule=True):
            # A record is an actual patient if it has a patient sequence 
            # and is not a core administrative record (Employee/User/New)
            is_patient = bool(
                record.patient_seq 
                and record.patient_seq not in ('New', 'Employee', 'User')
                and not record.is_company
                and not record.parent_id
            )
            is_internal_bot = bool(
                not record.company_id
                and not record.supplier_rank
                and not record.customer_rank
                and record.name
                and 'bot' in record.name.lower()
            )
            is_company_scoped_generic = bool(
                record.company_id and record.company_id.id in allowed_company_ids
            )
            if is_patient or (
                record.id not in safe_ids
                and not is_internal_bot
                and not is_company_scoped_generic
            ):
                patient_records |= self.browse(record.id)
            else:
                safe_records |= self.browse(record.id)

        return patient_records, safe_records

    def check_access_rule(self, operation):
        if self.env.su:
            return super().check_access_rule(operation)

        is_hosp = self._is_hospital_user()
        if (
            operation == 'read'
            and self.env.context.get('_skip_hospital_partner_rule')
            and is_hosp
            and self.ids
            and set(self.ids).issubset(self._get_safe_hospital_partner_ids())
        ):
            return True

        if self.env.context.get('_skip_hospital_partner_rule'):
            return super().check_access_rule(operation)

        if not is_hosp:
            return super().check_access_rule(operation)

        is_supp = self._is_supplier_context()
        
        _logger.debug(
            "Access Check: uid=%s, op=%s, ids=%s, is_supp=%s",
            self.env.uid,
            operation,
            self.ids,
            is_supp,
        )

        if operation == 'read' and (is_supp or self.env.context.get('allow_supplier_partner_read')):
            if self.ids and set(self.ids).issubset(set(self._get_vendor_visibility_partner_ids())):
                return True
            return super(ResPartner, self.with_context(_skip_hospital_partner_rule=True)).check_access_rule(operation)

        company_partner_ids = set(self._get_company_partner_ids())
        if operation == 'read' and self.ids and set(self.ids).issubset(company_partner_ids):
            return True

        # Split records to see if we are dealing with sensitive data
        patient_records, safe_records = self._split_hospital_patient_records()

        if patient_records:
            # If we have patients, we check if they belong to allowed companies
            allowed_cos = self.env.companies.ids or [self.env.company.id]
            unauthorized_patients = patient_records.filtered(
                lambda p: p.company_id and p.company_id.id not in allowed_cos
            )
            if unauthorized_patients:
                # If there are unauthorized patients, let the standard rules decide or raise
                _logger.warning("Unauthorized Patient access attempt: %s", unauthorized_patients.ids)
                return super(ResPartner, self.with_context(_skip_hospital_partner_rule=True)).check_access_rule(operation)

        # If it's all safe records or allowed patients, we permit access
        return True

    def _filter_access_rules_python(self, operation):
        """Keep internal non-patient contacts readable for hospital users.

        Some login/discuss flows hit Python-level record-rule filtering before
        the explicit `check_access_rule` path surfaces. Mirror the same
        protected-partner allowance here so internal bot/admin contacts remain
        readable without exposing normal patient data across companies.
        """
        if operation != 'read':
            return super()._filter_access_rules_python(operation)

        if self.env.context.get('_skip_hospital_partner_rule'):
            if self._is_hospital_user():
                safe_ids = self._get_safe_hospital_partner_ids()
                safe_records = self.filtered(lambda rec: rec.id in safe_ids)
                remaining_records = self - safe_records
                if not remaining_records:
                    return safe_records
                return safe_records | super(
                    ResPartner, remaining_records
                )._filter_access_rules_python(operation)
            return super()._filter_access_rules_python(operation)

        if self.env.context.get('allow_supplier_partner_read') or self._is_supplier_context():
            vendor_ids = set(self._get_vendor_visibility_partner_ids())
            return self.filtered(lambda rec: rec.id in vendor_ids)

        company_partner_ids = set(self._get_company_partner_ids())
        if company_partner_ids:
            company_partner_records = self.filtered(lambda rec: rec.id in company_partner_ids)
            if company_partner_records:
                remaining_records = self - company_partner_records
                if not remaining_records:
                    return self
                self = remaining_records

        if not self._is_hospital_user():
            return super(
                ResPartner, self.with_context(_skip_hospital_partner_rule=True)
            )._filter_access_rules_python(operation)

        patient_records, safe_records = self._split_hospital_patient_records()
        own_partner = self.env.user.partner_id
        if own_partner and own_partner in self:
            safe_records |= self.browse(own_partner.id)
            patient_records -= own_partner
        if not patient_records:
            return safe_records

        allowed_remaining = super(
            ResPartner, patient_records.with_context(_skip_hospital_partner_rule=True)
        )._filter_access_rules_python(operation)
        return safe_records | allowed_remaining

    company_id = fields.Many2one('res.company', string='Company', index=True)
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
        current_company_partner = self.env.company.partner_id
        current_company_partner_id = self.env.company.partner_id.id
        for record in self:
            record.current_company_partner_id = current_company_partner
            record.current_company_partner_ref = current_company_partner_id

    @api.model
    def _domain_explicitly_targets_ids(self, domain, target_ids):
        """Return True when the incoming domain explicitly asks for target ids.

        This lets internal Odoo reads fetch the current user's partner or the
        active company's partner without injecting those records into normal
        vendor list results.
        """
        target_ids = {pid for pid in target_ids if pid}
        if not target_ids:
            return False

        for token in domain or []:
            if not isinstance(token, (list, tuple)) or len(token) < 3:
                continue
            field_name, operator, value = token[0], token[1], token[2]
            if field_name != 'id':
                continue
            if operator == '=' and value in target_ids:
                return True
            if operator == 'in' and any(pid in target_ids for pid in (value or [])):
                return True
        return False

    @api.model
    def _domain_targets_suppliers(self, domain):
        """Return True when a domain is clearly a vendor/supplier search."""
        for token in domain or []:
            if not isinstance(token, (list, tuple)) or len(token) < 3:
                continue
            field_name, operator, value = token[0], token[1], token[2]
            if field_name == 'supplier_rank':
                return True
            if field_name == 'parent_id.supplier_rank':
                return True
            if field_name == 'customer_rank' and operator in ('=', '!=') and value == 0:
                return True
        return False

    @api.model
    def _is_customer_context(self):
        return bool(
            self.env.context.get('default_customer_rank', 0) > 0
            or self.env.context.get('res_partner_search_mode') == 'customer'
            or self.env.context.get('search_default_customer')
        )

    @api.model
    def _domain_targets_customers(self, domain):
        """Return True when a domain is clearly a customer search."""
        for token in domain or []:
            if not isinstance(token, (list, tuple)) or len(token) < 3:
                continue
            field_name, operator, value = token[0], token[1], token[2]
            if field_name == 'customer_rank':
                if operator in ('>', '>=') and value == 0:
                    return True
                if operator == '!=' and value == 0:
                    return True
                if operator == '=' and value:
                    return True
                if operator == 'in' and any(rank for rank in (value or [])):
                    return True
            if field_name == 'parent_id.customer_rank':
                return True
        return False

    @api.model
    def _get_vendor_visibility_partner_ids(self):
        """Return partner ids visible in supplier dropdown/list contexts.

        Keep this SQL-based so res.partner._search does not add relational
        partner domains that recursively call res.partner._search again.
        """
        allowed_company_ids = self.env.companies.ids or [self.env.company.id]
        user_partner_id = self.env.user.partner_id.id
        current_company_partner_id = self.env.company.partner_id.id

        self.env.cr.execute("SELECT partner_id FROM res_company WHERE partner_id IS NOT NULL")
        company_partner_ids = [row[0] for row in self.env.cr.fetchall()]

        self.env.cr.execute(
            """
            SELECT DISTINCT p.id
              FROM res_partner p
              LEFT JOIN res_partner commercial
                     ON commercial.id = p.commercial_partner_id
              LEFT JOIN res_users u
                     ON u.partner_id = p.id
              LEFT JOIN res_company_users_rel cu
                     ON cu.user_id = u.id
             WHERE (
                    p.company_id = %(current_company_id)s
                 OR commercial.company_id = %(current_company_id)s
                 OR cu.cid = ANY(%(allowed_company_ids)s)
                 OR p.id = %(user_partner_id)s
                 OR p.id = %(current_company_partner_id)s
             )
               AND (
                    p.id = %(user_partner_id)s
                 OR p.id = %(current_company_partner_id)s
                 OR (
                        NOT COALESCE(p.id = ANY(%(company_partner_ids)s), FALSE)
                    AND NOT COALESCE(p.parent_id = ANY(%(company_partner_ids)s), FALSE)
                    AND NOT COALESCE(p.commercial_partner_id = ANY(%(company_partner_ids)s), FALSE)
                 )
             )
            """,
            {
                'current_company_id': self.env.company.id,
                'allowed_company_ids': allowed_company_ids,
                'company_partner_ids': company_partner_ids or [0],
                'user_partner_id': user_partner_id or 0,
                'current_company_partner_id': current_company_partner_id or 0,
            },
        )
        return [row[0] for row in self.env.cr.fetchall()]

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, access_rights_uid=None):
        restrict_customer_partners = (
            self._is_customer_context()
            or self._domain_targets_customers(domain)
        )
        if restrict_customer_partners and not self.env.context.get('_skip_hospital_partner_rule'):
            allowed_company_ids = self.env.companies.ids or [self.env.company.id]
            customer_visibility_domain = expression.OR([
                [('company_id', 'in', allowed_company_ids)],
                [('id', '=', self.env.user.partner_id.id)],
                [('id', 'in', self.env.companies.sudo().mapped('partner_id').ids)],
            ])
            domain = expression.AND([
                domain or [],
                customer_visibility_domain,
            ])

        restrict_supplier_partners = (
            self.env.context.get('hide_current_company_partner')
            or self._is_supplier_context()
            or self.env.context.get('allow_supplier_partner_read')
            or self._domain_targets_suppliers(domain)
        )
        if restrict_supplier_partners and not self.env.context.get('_skip_hospital_partner_rule'):
            own_partner_id = self.env.user.partner_id.id
            company_partner_id = self.env.company.partner_id.id
            requested_internal_partner = self._domain_explicitly_targets_ids(
                domain,
                [own_partner_id, company_partner_id],
            )

            vendor_visibility_domain = [('id', 'in', self._get_vendor_visibility_partner_ids())]
            if requested_internal_partner:
                vendor_visibility_domain = expression.OR([
                    [('id', 'in', [own_partner_id, company_partner_id])],
                    vendor_visibility_domain
                ])
            domain = expression.AND([
                domain or [],
                vendor_visibility_domain,
            ])
        return super()._search(
            domain,
            offset=offset,
            limit=limit,
            order=order,
            access_rights_uid=access_rights_uid,
        )

    height = fields.Char(string='Height (Inch)', help='Height of the patient in inches')
    weight = fields.Float(string='Weight (kg)', help='Weight of the patient in kilograms')
    date_of_birth = fields.Date(string='Date of Birth',
                                help='Date of birth of the patient')
    blood_group = fields.Selection(string='Blood Group',
                                   help='Blood group of the patient',
                                   selection=[('a+', 'A+'), ('a-', 'A-'),('b+', 'B+'),('b-', 'B-'),
                                              ('o+', 'O+'), ('o-', 'O-'),('ab+', 'AB+'),('ab-', 'AB-')])
    rh_type = fields.Selection(selection=[('-', '-ve'), ('+', '+ve')],
                               string='RH Type',
                               help='Rh type of the blood group')
    gender = fields.Selection(selection=[
        ('male', 'Male'), ('female', 'Female'), ('other', 'Other')
    ], string='Gender', help='Gender of the patient')
    marital_status = fields.Selection(selection=[
        ('married', 'Married'), ('unmarried', 'Unmarried'), ('widow', 'Widow'),
        ('widower', 'Widower'), ('divorcee', 'Divorcee')
    ], string='Marital Status', help='Marital status of patient')
    is_alive = fields.Selection(
        string='Status',
        selection=[('alive', 'Alive'), ('dead', 'Dead')],
        default='alive', help='True for alive patient')
    patient_seq = fields.Char(string='Patient No.',
                              help='Sequence number of the patient', copy=False,
                              readonly=True, index=True,
                              default=lambda self: 'New')
    notes = fields.Html(string='Note', help='Notes regarding the notes',
                        sanitize_style=True)
    patient_profession = fields.Char(string="Profession",
                                     help="Profession of patient")
    doctor_id = fields.Many2one('hr.employee',
                                domain=[('job_id.name', '=', 'Doctor')],
                                string="Family Doctor",
                                help='Family doctor of the patient')
    barcode = fields.Char(string='Barcode', help='Barcode for the patient')
    barcode_png = fields.Binary(string='Barcode PNG',
                                help='Image file of the barcode', readonly=True)
    group = fields.Selection(selection=[
        ('hindu', 'Hindu'), ('muslim', 'Muslim'), ('christian', 'Christian')],
        string="Ethnic Group", help="Specify your religion")
    risk = fields.Text(string="Genetic Risks",
                       help='Genetic risks of the patient')
    insurance_id = fields.Many2one('hospital.insurance',
                                   string="Insurance",
                                   help="Patient insurance")
    unique_id = fields.Char(string='Unique ID',
                            help="Unique identifier to fetch "
                                 "patient insurance data")
    family_ids = fields.One2many('hospital.family',
                                 'family_id',
                                 string="Family ID", help='Family of a patient')
    lab_test_ids = fields.One2many('patient.lab.test',
                                   'patient_id',
                                   string='Lab Test',
                                   help='Lab tests for the patient')
    prescription_ids = fields.One2many('prescription.line',
                                       'res_partner_id',
                                       string='Prescription',
                                       help='Prescription for patient')
    economic_level = fields.Selection(selection=[
        ('low', 'Lower Class'), ('middle', 'Middle Class'),
        ('upper', 'Upper Class')], string="Socioeconomic",
        help="Specify your economic status")
    education_level = fields.Selection(selection=[
        ('post', 'Post Graduation'), ('graduation', 'Graduation'),
        ('pre', 'Pre Graduation')], string="Education Level",
        help="Education status of patient")
    house_level = fields.Selection(selection=[
        ('good', 'Good'), ('bad', 'Bad'), ('poor', 'Poor')],
        string="House Condition", help="Specify your house's condition")
    work_home = fields.Boolean(string='Work At Home',
                               help='True if you are working from home')
    hours_outside = fields.Integer(string='Hours Stay Outside Home',
                                   help="Specify how many hours you stay away "
                                        "from home")
    hostile = fields.Boolean(string='Hostile Area',
                             help="Specify your house in a friendly "
                                  "neighbourhood ")
    income = fields.Monetary(string='Income', help="The in come of patient")
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  help='Currency in which invoices and payments'
                                       ' will be generated',
                                  default=lambda self: self.env.user.company_id
                                  .currency_id.id, required=True)
    sanitary = fields.Boolean('Sanitary Sewers',
                              help="A sewer or sewer system for carrying off "
                                   "wastewater, waste matter from a residence,"
                                   " business, etc")
    running = fields.Boolean(string='Running Water',
                             help="water that comes into a building through "
                                  "pipes. A cabin with hot and cold running "
                                  "water.")
    electricity = fields.Boolean(string='Electricity',
                                 help='True if you have electricity')
    gas = fields.Boolean(string='Gas Supply',
                         help='True if you have gas supply')
    trash = fields.Boolean(string='Trash Collection',
                           help='True if you have trash collection')
    home_phone = fields.Boolean(string='Telephone',
                                help='True if you have telephone')
    tv = fields.Boolean(string='Television', help='True if you have television')
    internet = fields.Boolean(string='Internet',
                              help='True if you have internet')
    help = fields.Selection([('yes', 'Yes'), ('no', 'No')],
                            string="Family Help",
                            help="Specify whether your family is willing "
                                 "to help or not")
    discussion = fields.Selection([('yes', 'Yes'), ('no', 'No')],
                                  string="Family Discussion ",
                                  help="Specify your family have a good "
                                       "discussion at home ")
    ability = fields.Selection([('very', 'Very good'), ('good', 'Good'),
                                ('bad', 'Bad'), ('poor', 'Poor')],
                               string="Family Ability",
                               help="family status of the patient")
    time_sharing = fields.Selection([('yes', 'Yes'), ('no', 'No')],
                                    string=" Family Time Sharing ",
                                    help="Specify your family share time "
                                         "at home ")
    affection = fields.Selection([('very', 'Very good'),
                                  ('good', 'Good'),
                                  ('bad', 'Bad'), ('poor', 'Poor')],
                                 string="Family Affection ",
                                 help="Specify your family's affection ")
    single = fields.Boolean(string='Single Parent Family',
                            help='Whether single parent family or not')
    violence = fields.Boolean(string='Domestic Violence',
                              help='True if you are facing any domestic '
                                   'violence')
    children = fields.Boolean(string='Working Children',
                              help='Do you have working children')
    abuse = fields.Boolean(string='Sexual Abuse',
                           help='Do you faced any sexual abuse')
    drug = fields.Boolean(string='Drug Addiction',
                          help='Do you have drug addiction')
    withdrawal = fields.Boolean(string='Withdrawal',
                                help='Do you faced any withdrawal symptoms')
    in_prison = fields.Boolean(string='Has Been In Prison',
                               help='True if you had been in prison')
    current_prison = fields.Boolean(string='Currently In Prison',
                                    help='True if you are in prison currently')
    relative_prison = fields.Boolean(string='Relative In Prison',
                                     help='True if any of your relative is '
                                          'in prison')
    hospital_vaccination_ids = fields.One2many(
        'hospital.vaccination', 'patient_id',
        string='Vaccination', help='Vaccination details of '
                                   'patient')
    fertile = fields.Boolean(string='Fertile', help="""Capable of developing 
                                             into a complete organism; 
                                             fertilized. Capable of supporting 
                                             plant life; favorable to the 
                                             growth of crops and plants.""")
    menarche_age = fields.Integer(string='Menarche Age', help="""The first 
                                     menstrual period in a female adolescent""")
    pause = fields.Boolean(string='Menopause', help="""Menopause is a point in 
                                 time 12 months after a woman's last period""")
    pause_age = fields.Integer(string='Menopause Age',
                               help='Age at which menopause occurred')
    pap = fields.Boolean(string='PAP Test',
                         help="""
                         A procedure in which a small brush is used to gently 
                         remove cells from the surface of the cervix and the 
                         area around it so they can be checked under a 
                         microscope for cervical cancer or cell changes that
                         may lead to cervical cancer.""")
    colposcopy = fields.Boolean(string='Colposcopy', help=""" test to take a
                            closer look at your cervix""")
    self = fields.Boolean(string='Self breast examination',
                          help="A breast self-exam for breast awareness is "
                               "in inspection "
                               "of your breasts that women do on your own")
    mommography = fields.Boolean(string='Mommography',
                                 help="Mammograms can be used to look for "
                                      "breast cancer")
    last_pap = fields.Date(string="Last PAP Test",
                           help='The date on which last PAP test has been done')
    last_col = fields.Date(string="Last Colposcopy",
                           help='The date on which last colposcopy has been '
                                'done')
    deceased = fields.Boolean(string='Deceased during 1st week',
                              help='The family member deceased during first '
                                   'week')
    grandiva = fields.Boolean(string='Grandiva', help='True for grandiva')
    alive = fields.Boolean(string='Born Alive', help='Whether born alive or '
                                                     'not')
    premature = fields.Integer(string='Premature',
                               help="Premature birth is birth that happens too"
                                    "soon, before 37 weeks of pregnancy")
    abortions = fields.Integer(string='No Of Abortions', help='Number of '
                                                              'abortions of '
                                                              'patient')
    place = fields.Char(string="Place")
    exercise = fields.Boolean(string='Exercise', help='True if patient doing '
                                                      'exercise regularly')
    minute = fields.Integer(string='Minute/Day', help='The duration of '
                                                      'exercise per day')
    day_sleep = fields.Boolean(string='Sleeps At Daytime', help='True if '
                                                                'sleeps at '
                                                                'daytime')
    sleep_hrs = fields.Integer(string='Sleep Hours', help='Duration of sleep')
    meals = fields.Integer(string='Meals/Day', help='Number of meals per day')
    alone = fields.Boolean(string='Eat Alone', help='True if eats alone')
    coffee = fields.Boolean(string='Coffee', help='True if you have a habit '
                                                  'of drinking coffee')
    cup = fields.Integer(string='Cups/Day', help='Number of cups of coffee '
                                                 'per day')
    drink = fields.Boolean(string='Soft Drink', help='True if you drinks soft '
                                                     'drinks')
    salt = fields.Boolean(string='Salt', help='True if you use salt')
    diet = fields.Boolean(string='Currently On Diet', help='True if you are '
                                                           'on diet currently')
    smoke = fields.Boolean(string='Smoker', help='True for smoker')
    ex_smoke = fields.Boolean(string='Ex-Smoker', help='True for ex-smoker')
    age_start = fields.Integer(string='Age of Started Smoking',
                               help='Age on which you started your smoking')
    cigarettes = fields.Integer(string='Cigarettes/Day',
                                help='Number of cigarettes per day')
    passive = fields.Boolean(string='Passive Smoker',
                             help='True for passive smokers')
    age_quit = fields.Integer(string='Age of Quitting',
                              help='Age at which you quit your smoking habit')
    alcoholic = fields.Boolean(string='Alcoholic', help='True for alcoholics')
    ex_alcoholic = fields.Boolean(string='Ex-Alcoholic', help='True for ex- '
                                                              'alcoholics')
    age_start_alco = fields.Integer(string='Age to Start Drinking',
                                    help='Age at which you started your '
                                         'drinking habit')
    beer = fields.Integer(string='Beer/Day',
                          help='Number of beers per day')
    liquor = fields.Integer(string='Liquor/Day',
                            help='Liquors per day')
    wine = fields.Integer(string='Wine/Day',
                          help='Number of wines per day')
    age_quit_alcoholic = fields.Integer(string='Age Of Quitting',
                                        help='Age at which you started your '
                                             'drinking habit')
    drugs = fields.Boolean(string='Drug User', help='True for drug users')
    ex_drugs = fields.Boolean(string='Ex-Drug User', help='True for Ex drug '
                                                          'user')
    iv_user = fields.Boolean(string='IV Drug User', help='True for IV drug '
                                                         'user')
    age_start_drug = fields.Integer(string='Age to Start Using Drugs',
                                    help='Age at which you started using drug')
    age_quit_drug = fields.Integer(string='Drug Quitting Age', help='Age of '
                                                                    'quitting '
                                                                    'drug')
    orientation = fields.Selection([('straight', 'Straight'),
                                    ('homo', 'Homosexual'),
                                    ('trans', 'Trans-Gender')],
                                   string="Orientation")
    age_sex = fields.Integer(string="Age of First Encounter",
                             help='Age of first sex encounter')
    partners = fields.Integer(string="No of Partners",
                              help='Number of sex partners')
    anti = fields.Selection(
        [('pills', 'Contraceptive Pills'), ('ring', 'Contraceptive Ring'),
         ('injection', 'Contraceptive Injection')],
        string="Contraceptive Methods", help='Choose your contraceptive method')
    oral = fields.Boolean(string='Oral Sex', help=("uttered by the mouth or in "
                                                   "words"))
    anal = fields.Boolean(string='Anal Sex', help="True if you are "
                                                  "encountering anal sex")
    prostitute = fields.Boolean(string='Prostitute', help='True for '
                                                          'prostitutes')
    prostitute_sex = fields.Boolean(string='Sex With Prostitute',
                                    help='True if you are encountered sex '
                                         'with prostitute')
    sex_notes = fields.Text(string='Notes', help='Write down the notes')
    rider = fields.Boolean(string='Motorcycle Rider', help='True for '
                                                           'motorcycle riders')
    helmet = fields.Boolean(string='Uses Helmet',
                            help='True if you regularly use helmet')
    laws = fields.Boolean(string='Obey Traffic Laws',
                          help='True if you obey traffic rules')
    revision = fields.Boolean(string='Car Revision', help='True if car '
                                                          'revision is done')
    belt = fields.Boolean(string='Seat Belt',
                          help='True if you uses seat belt regularly')
    safety = fields.Boolean(string='Car Child Safety',
                            help='True if you have car child safety')
    home = fields.Boolean(string='Home Safety', help='True for home safety')
    occupation = fields.Char(string='Occupation', help='Your occupation')
    op_history_ids = fields.One2many(
        'hospital.outpatient',
        'patient_id',
        string='Outpatient History'
    )
    age = fields.Integer(string="Age", compute="_compute_age", store=True)
    age_display = fields.Char(string="Age", compute="_compute_age")
    bp = fields.Char(string="Blood Pressure")
    temperature = fields.Float(string="Temperature (°C)")

    phone = fields.Char(string="Phone")
    vendor_phone = fields.Char(
        string="Vendor Phone",
        help="Dedicated phone number used on vendor forms.",
    )
    vendor_mobile = fields.Char(
        string="Vendor Mobile",
        help="Dedicated mobile number used on vendor forms.",
    )


    default_general_fee = fields.Monetary(
        string='Default General Fee',
        currency_field='currency_id',
        help='Default general/consultation fee for this patient'
    )
    default_injection_fee = fields.Monetary(
        string='Default Injection Fee',
        currency_field='currency_id',
        help='Default injection/additional charges for this patient'
    )
    # currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    fee_lines = fields.One2many('hospital.outpatient', 'patient_id', string='Fees', readonly=True)

    @api.constrains('phone')
    def _check_phone_length(self):
        for record in self:
            if record.phone and record._is_hospital_patient_record():
                digits = re.sub(r'\D', '', record.phone)
                if len(digits) != 10:
                    raise ValidationError("Phone number must be exactly 10 digits (only numbers 0-9).")

    @api.constrains('name')
    def _check_patient_name_length(self):
        for record in self:
            if record.name and record._is_hospital_patient_record() and len(record.name) > 60:
                raise ValidationError("Patient name cannot exceed 60 characters.")
    

    @api.depends('date_of_birth')
    def _compute_age(self):
        for record in self:
            if record.date_of_birth:
                today = date.today()
                dob = record.date_of_birth
                record.age = today.year - dob.year - (
                    (today.month, today.day) < (dob.month, dob.day)
                )
                record.age_display = record._format_age_display(dob)
            else:
                record.age = 0
                record.age_display = ''

    op_ids = fields.One2many(
        'hospital.outpatient',
        'patient_id',
        string="Outpatient Visits"
    )

    lab_result_ids = fields.One2many(
        'hospital.lab.result',
        'patient_id',
        string="Lab Results"
    )

    # @api.model
    # def create(self, vals):
    #     # Required validation
    #     if not vals.get('date_of_birth'):
    #         raise ValidationError("Date of Birth is required")

    #     if not vals.get('gender'):
    #         raise ValidationError("Gender is required")

    #     # Sequence generation
    #     if vals.get('patient_seq', 'New') == 'New':
    #         vals['patient_seq'] = self.env['ir.sequence'].next_by_code(
    #             'patient.sequence') or 'New'

    #     return super().create(vals)

    @api.model
    def _is_hospital_patient_vals(self, vals):
        if (
            vals.get('supplier_rank', 0) > 0
            or self.env.context.get('default_supplier_rank', 0) > 0
            or vals.get('is_company')
            or self.env.context.get('default_is_company')
            or vals.get('parent_id')
            or self.env.context.get('default_parent_id')
        ):
            return False

        patient_fields = [
            'blood_group', 'height', 'weight', 'patient_profession',
            'emergency_contact', 'medical_history', 'date_of_birth',
            'gender', 'rh_type'
        ]
        return any(vals.get(field) for field in patient_fields) or \
            vals.get('customer_rank', 0) > 0 or \
            self.env.context.get('is_patient') or \
            self.env.context.get('default_is_patient')

    @api.model
    def _validate_patient_required_fields(self, vals):
        if not vals.get('phone'):
            raise ValidationError("Phone is required for patients.")
        if not vals.get('gender'):
            raise ValidationError("Gender is required for patients.")

    def _is_hospital_patient_record(self):
        self.ensure_one()
        return bool(
            not self.is_company
            and not self.parent_id
            and self.patient_seq
            and self.patient_seq not in ('New', 'Employee', 'User')
        )

    @api.model
    def _is_company_style_partner(self, vals):
        return bool(
            vals.get('is_company') or
            self.env.context.get('default_is_company') or
            vals.get('parent_id') or
            self.env.context.get('default_parent_id')
        )

    @api.model
    def create(self, vals):
        vals = dict(vals)

        # CRITICAL: Check if we're in the res.users model
        if self._name == 'res.users':
            return super().create(vals)
        
        # Also check if this is being called from user creation context
        if self.env.context.get('install_lang') or self.env.context.get('create_user'):
            return super().create(vals)
        
        # Determine if this record should get a patient sequence
        is_patient = self._is_hospital_patient_vals(vals)
        is_company_style_partner = self._is_company_style_partner(vals)
        is_vendor = (
            vals.get('supplier_rank', 0) > 0
            or self.env.context.get('default_supplier_rank', 0) > 0
        )

        if is_vendor and not vals.get('company_id'):
            vals['company_id'] = self.env.company.id

        if is_vendor and vals.get('patient_seq', 'New') == 'New':
            vals['patient_seq'] = False

        # Keep hospital patients company-bound without forcing company_id on
        # generic/company contacts created by Odoo core.
        if is_patient and not is_company_style_partner and not vals.get('company_id'):
            vals['company_id'] = self.env.company.id

        # ✅ Set customer_rank if we're a patient
        if is_patient and not is_company_style_partner and 'customer_rank' not in vals:
            vals['customer_rank'] = 1

        if is_patient and not is_company_style_partner:
            self._validate_patient_required_fields(vals)

        if is_patient and not is_company_style_partner and vals.get('name') and len(vals['name']) > 60:
            raise ValidationError("Patient name cannot exceed 60 characters.")

        # ✅ Validate phone number if present
        if vals.get('phone') and is_patient and not is_company_style_partner:
            phone = vals.get('phone')
            # Remove any non-digit characters
            phone = ''.join(filter(str.isdigit, str(phone)))
            
            if len(phone) != 10:
                raise ValidationError("Phone number must be exactly 10 digits. Please enter a valid 10-digit mobile number.")
            
            # Store the cleaned phone number
            vals['phone'] = phone
        
        # Generate patient_seq if needed
        if (not vals.get('patient_seq') or vals.get('patient_seq') == 'New'):
            # Determine if this record MUST have a patient sequence
            # Trigger if we have medical fields OR if context says it's a patient
            is_hospital_patient = is_patient or \
                                 self.env.context.get('is_patient') or \
                                 self.env.context.get('default_is_patient')
            
            if is_hospital_patient and not is_company_style_partner:
                seq_code = 'patient.sequence'
                company_id = vals.get('company_id') or self.env.company.id
                
                # 1. Search for a sequence record specifically for this company
                sequence = self.env['ir.sequence'].sudo().search([
                    ('code', '=', seq_code),
                    ('company_id', '=', company_id)
                ], limit=1)
                
                if not sequence:
                    # 2. Look for the global template (company_id=False)
                    sequence = self.env['ir.sequence'].sudo().search([
                        ('code', '=', seq_code),
                        ('company_id', '=', False)
                    ], limit=1)
                    
                    if not sequence:
                        # 🔥 NUCLEAR OPTION: Programmatically recreate the missing global template
                        sequence = self.env['ir.sequence'].sudo().create({
                            'name': 'Patient sequence',
                            'code': 'patient.sequence',
                            'prefix': 'PAT',
                            'padding': 3,
                            'number_next': 1,
                            'number_increment': 1,
                            'company_id': False
                        })

                    if sequence and sequence.company_id == False:
                        # 3. Clone template for this company (keeping existing counter logic)
                        existing_patients = self.env['res.partner'].sudo().search([
                            ('company_id', '=', company_id),
                            ('patient_seq', 'ilike', 'PAT%')
                        ])
                        start_num = 1
                        if existing_patients:
                            seq_numbers = []
                            for p in existing_patients:
                                nums = re.findall(r'\d+', p.patient_seq or '')
                                if nums:
                                    seq_numbers.append(int(nums[-1]))
                            if seq_numbers:
                                start_num = max(seq_numbers) + 1
                            else:
                                start_num = len(existing_patients) + 1

                        # Create company-specific copy
                        sequence = sequence.copy({
                            'company_id': company_id,
                            'number_next': start_num,
                            'name': f"{sequence.name} ({self.env['res.company'].browse(company_id).name})"
                        })
                
                # FINAL ATTEMPT to get a number
                if sequence:
                    vals['patient_seq'] = sequence.next_by_id()
                else:
                    # Universal Fallback - IF THIS FAILS, THE DATABASE IS PREVENTING CREATION
                    vals['patient_seq'] = self.env['ir.sequence'].sudo().next_by_code(seq_code) or 'New'

        partner = super().create(vals)
        partner._normalize_internal_partner_company()
        return partner

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if (
            'company_id' in fields_list
            and not res.get('company_id')
            and (
                self.env.context.get('default_supplier_rank', 0) > 0
                or self.env.context.get('res_partner_search_mode') == 'supplier'
            )
        ):
            res['company_id'] = self.env.company.id
        return res

    def write(self, vals):
        vals = dict(vals)
        # Skip if these are user records
        for record in self:
            if record._name == 'res.users' or (hasattr(record, 'login') and record.login):
                return super().write(vals)

        if vals.get('supplier_rank', 0) > 0 and 'company_id' not in vals:
            vals['company_id'] = self.env.company.id
        if vals.get('supplier_rank', 0) > 0 and vals.get('patient_seq', 'New') == 'New':
            vals['patient_seq'] = False
        
        # For patients, validate if they're trying to clear required fields
        for record in self:
            # Only validate if this record has patient fields
            if record._is_hospital_patient_record() or record.blood_group or record.height or record.weight:
                if 'date_of_birth' in vals and not vals.get('date_of_birth'):
                    raise ValidationError("Date of Birth cannot be empty for patients")
                if 'gender' in vals and not vals.get('gender'):
                    raise ValidationError("Gender cannot be empty for patients")
                if 'phone' in vals and not vals.get('phone'):
                    raise ValidationError("Phone cannot be empty for patients")
                if 'name' in vals and vals.get('name') and len(vals['name']) > 60:
                    raise ValidationError("Patient name cannot exceed 60 characters.")
                if 'phone' in vals and vals.get('phone'):
                    phone = ''.join(filter(str.isdigit, str(vals['phone'])))
                    if len(phone) != 10:
                        raise ValidationError("Phone number must be exactly 10 digits. Please enter a valid 10-digit mobile number.")
                    vals['phone'] = phone
        
        result = super().write(vals)
        self._normalize_internal_partner_company()
        return result
    
    def action_view_invoice(self):
        """Returns patient invoice"""
        self.ensure_one()
        return {
            'name': 'Patient Invoice',
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
            'domain': [('partner_id', '=', self.id)],
            'context': "{'create':False}"
        }


    def action_print_latest_prescription(self):
        self.ensure_one()

        latest_op = self.env['hospital.outpatient'].search([
            ('patient_id', '=', self.id),
            ('state', 'in', ['op', 'invoice'])
        ], order='op_date desc', limit=1)

        if not latest_op:
            raise ValidationError("No prescription found for this patient.")

        return latest_op.action_print_prescription()
    
    def name_get(self):
        """Returns the patient name"""
        result = []
        for rec in self:
            result.append((rec.id, f'{rec.patient_seq} - {rec.name}'))
        return result

    def alive_status(self):
        """Function for setting the value of is_alive field"""
        if self.is_alive == 'alive':
            self.is_alive = 'dead'
        else:
            self.is_alive = 'alive'

    def action_schedule(self):
        """Returns form view of hospital appointment wizard"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hospital.outpatient',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'views': [[False, 'form']],
            'context': {
                'default_patient_id': self.id
            }
        }

    @api.model
    def ean_checksum(self, eancode):
        """Returns the checksum of an ean string of length 13, returns -1 if
            the string has the wrong length"""
        if len(eancode) != 13:
            return -1
        odd_sum = 0
        even_sum = 0
        ean_value = eancode
        reverse_value = ean_value[::-1]
        final_ean = reverse_value[1:]
        for i in range(len(final_ean)):
            if i % 2 == 0:
                odd_sum += int(final_ean[i])
            else:
                even_sum += int(final_ean[i])
        total = (odd_sum * 3) + even_sum
        check = int(10 - math.ceil(total % 10.0)) % 10
        return check

    def check_ean(eancode):
        """Returns True if eancode is a valid ean13 string, or null"""
        if not eancode:
            return True
        if len(eancode) != 13:
            return False
        int(eancode)
        return eancode.ean_checksum(eancode) == int(eancode[-1])

    def generate_ean(self, ean):
        """Creates and returns a valid ean13 from an invalid one"""
        if not ean:
            return "0000000000000"
        ean = re.sub("[A-Za-z]", "0", ean)
        ean = re.sub("[^0-9]", "", ean)
        ean = ean[:13]
        if len(ean) < 13:
            ean = ean + '0' * (13 - len(ean))
            return ean[:-1] + str(self.ean_checksum(ean))

    # def action_generate_patient_card(self):
    #     """Method for generating the patient card"""
    #     current_age = 0
    #     gender_caps = ''
    #     blood_caps = ''
    #     if not self.barcode:
    #         ean = self.sudo().generate_ean(str(self.id))
    #         self.sudo().write({'barcode': ean})
    #         number = self.barcode
    #         my_code = EAN13(number, writer=ImageWriter())
    #         my_code.save("code")
    #         with open('code.png', 'rb') as f:
    #             self.sudo().write({
    #                 'barcode_png': base64.b64encode(f.read())
    #             })
    #     if self.gender:
    #         gender_caps = self.gender.capitalize()
    #     if self.blood_group:
    #         blood_caps = self.blood_group.capitalize()
    #     if self.date_of_birth:
    #         today = date.today()
    #         dob = self.date_of_birth
    #         current_age = relativedelta(today, dob).years
    #     company = self.env['res.company'].sudo().search(
    #         [('id', '=', self.env.context['allowed_company_ids'])])
    #     data = {
    #         'name': self.name,
    #         'code': self.patient_seq,
    #         'age': current_age,
    #         'gender': gender_caps,
    #         'dob': self.date_of_birth,
    #         'blood': blood_caps + str(self.rh_type),
    #         'street': self.street,
    #         'street2': self.street2,
    #         'state': self.state_id.name,
    #         'country': self.country_id.name,
    #         'city': self.city,
    #         'phone': self.phone,
    #         'image': self.sudo().read(['image_1920'])[0],
    #         'barcode': self.sudo().read(['barcode_png'])[0],
    #         'company_name': company.name,
    #         'company_street': company.street,
    #         'company_street2': company.street2,
    #         'company_city': company.city,
    #         'company_state': company.state_id.name,
    #         'company_zip': company.zip,
    #     }
    #     return self.env.ref(
    #         'base_hospital_management.action_report_patient_card'
    #     ).report_action(None, data=data)



    def action_generate_patient_card(self):
        """Method for generating the patient card"""
        current_age = ''
        gender_caps = ''
        blood_caps = ''
        
        if not self.barcode:
            ean = self.sudo().generate_ean(str(self.id))
            self.sudo().write({'barcode': ean})
            number = self.barcode
            
            # Create barcode in memory without saving to disk
            buffer = BytesIO()
            my_code = EAN13(number, writer=ImageWriter())
            my_code.write(buffer)
            
            # Get the binary data and encode it
            buffer.seek(0)
            self.sudo().write({
                'barcode_png': base64.b64encode(buffer.getvalue())
            })
            buffer.close()
        
        if self.gender:
            gender_caps = self.gender.capitalize()
        if self.blood_group:
            blood_caps = self.blood_group.capitalize()
        if self.date_of_birth:
            today = date.today()
            dob = self.date_of_birth
            current_age = self._format_age_display(dob)
        
        company = self.env['res.company'].sudo().search(
            [('id', '=', self.env.context['allowed_company_ids'])])
        
        data = {
            'name': self.name,
            'code': self.patient_seq,
            'age': current_age,
            'gender': gender_caps,
            'dob': self.date_of_birth,
            'blood': blood_caps + str(self.rh_type),
            'street': self.street,
            'street2': self.street2,
            'state': self.state_id.name,
            'country': self.country_id.name,
            'city': self.city,
            'phone': self.phone,
            'image': self.sudo().read(['image_1920'])[0],
            'barcode': self.sudo().read(['barcode_png'])[0],
            'company_name': company.name,
            'company_street': company.street,
            'company_street2': company.street2,
            'company_city': company.city,
            'company_state': company.state_id.name,
            'company_zip': company.zip,
        }
        
        return self.env.ref(
            'base_hospital_management.action_report_patient_card'
        ).report_action(None, data=data)

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []

        if name:
            domain = ['|', ('phone', operator, name), ('name', operator, name)]
            partners = self.search(domain + args, limit=limit)
        else:
            partners = self.search(args, limit=limit)

        return partners.name_get()

    def name_get(self):
        result = []
        for rec in self:
            name = rec.name
            if rec.phone:
                name = f"{rec.name} ({rec.phone})"
            result.append((rec.id, name))
        return result

    @api.model
    def reception_op_barcode(self, kw):
        """Returns a patient based on the barcode"""
        values = {
            'name': '',
            'date_of_birth': '',
            'phone': '',
            'blood_group': '',
            'gender': '',
        }
        if kw['patient_data']:
            patient = self.sudo().search(
                ['|', ('id', '=', kw['patient_data']),
                 ('phone', '=', kw['patient_data'])])
            if patient:
                values = {
                    'name': patient.name,
                    'date_of_birth': patient.date_of_birth,
                    'phone': patient.phone,
                    'blood_group': patient.blood_group,
                    'gender': patient.gender,
                }
        return values

    @api.model
    def reception_op_phone(self, phone):
        """Returns a patient details having the phone number"""
        patient_phone = self.sudo().search(
            [('phone', '=', phone['patient-phone'])])
        return {
            'patient_seq': patient_phone.patient_seq,
            'name': patient_phone.name,
            'date_of_birth': patient_phone.date_of_birth,
            'blood_group': patient_phone.blood_group,
            'gender': patient_phone.gender,
        }

    @api.model
    def action_get_patient_data(self, patient_id):
        """Method which returns patient details"""
        data = self.sudo().search([
            '|', ('patient_seq', '=', patient_id),
            ('barcode', '=', patient_id)
        ])
        patient_history = []
        for rec in self.env['hospital.outpatient'].sudo().search(
                [('patient_id', '=', data.id)]):
            patient_history.append(
                [rec.op_reference, str(rec.op_date),
                 rec.doctor_id.doctor_id.name])
        values = {
            'name': data.name or 'Patient Not Found',
            'unique': data.patient_seq or '',
            'email': data.email or '',
            'phone': data.phone or '',
            'dob': data.date_of_birth or '',
            'dob_display': self._format_dashboard_dob(data.date_of_birth),
            'image_1920': data.image_1920 or '',
            'status': data.marital_status or '',
            'history': patient_history,
            'blood_group': (data.blood_group.capitalize() + (data.rh_type or '')) if data.blood_group else '',
            'gender': data.gender.capitalize() if data.gender else '',
        }
        return values

    @api.model
    def search_patients_by_phone(self, phone):
        """Return matching patients for the active company by phone number."""
        digits = ''.join(filter(str.isdigit, str(phone or '')))
        if not digits:
            return []

        patients = self.sudo().search([
            ('company_id', '=', self.env.company.id),
            ('patient_seq', 'not in', ['New', 'Employee', 'User']),
            ('phone', 'like', digits),
        ], order='name', limit=20)

        values = patients.read(['name', 'phone', 'patient_seq', 'date_of_birth', 'gender', 'age_display'])
        for value in values:
            value['dob_display'] = self._format_dashboard_dob(value.get('date_of_birth'))
        return values

    @api.model
    def get_patient_basic_details(self, patient_id):
        """Return basic patient details for the selected patient."""
        patient = self.sudo().search([
            ('id', '=', int(patient_id)),
            ('company_id', '=', self.env.company.id),
        ], limit=1)

        return {
            'id': patient.id or False,
            'name': patient.name or '',
            'unique': patient.patient_seq or '',
            'phone': patient.phone or '',
            'dob': patient.date_of_birth or '',
            'dob_display': self._format_dashboard_dob(patient.date_of_birth),
            'gender': patient.gender.capitalize() if patient.gender else '',
            'email': patient.email or '',
            'blood_group': (patient.blood_group.capitalize() + (patient.rh_type or '')) if patient.blood_group else '',
            'image_1920': patient.image_1920 or '',
        }

    @api.model
    def create_sale_order_pharmacy(self, order):
        """Method for creating sale order for medicines"""
        medicine = []
        op_record = self.env['hospital.outpatient'].sudo().search(
            [('op_reference', '=', order), '|',
             ('active', 'in', [False, True])])
        for rec in op_record.prescription_ids:
            medicine.append([rec.medicine_id.id, rec.quantity])
        sale_order_pharmacy = self.env['sale.order'].sudo().create({
            'partner_id': op_record.patient_id.id,
        })
        for new in medicine:
            self.env['sale.order.line'].sudo().create({
                'product_id': new[0],
                'product_uom_qty': new[1],
                'order_id': sale_order_pharmacy.id,
            })

    # @api.model
    # def create_patient(self, post):
    #     """Method for creating a patient"""
    #     if post and not post['patient_id']:
    #         patient = self.sudo().search([('name', '=', post['op_name'])])
    #         if not patient:
    #             patient = self.sudo().create({
    #                 'name': post['op_name'],
    #                 'blood_group': post['op_blood_group'],
    #                 'gender': post['op_gender']
    #             })
    #             if 'op_dob' in post.keys():
    #                 patient.sudo().write({'date_of_birth': post['op_dob']})
    #     else:
    #         patient = self.sudo().search([('id', '=', post['patient_id'])])
    #         out_patient = self.env['hospital.outpatient'].sudo().search([('patient_id','=', patient.id)])
    #         if not out_patient:
    #             self.env['hospital.outpatient'].sudo().create({
    #                 'patient_id': patient.id,
    #                 'op_date': post['date'],
    #                 'reason': post['reason'],
    #                 'slot': post['slot'],
    #                 'doctor_id': self.env['doctor.allocation'].sudo().browse(
    #                     post['doctor']).id
    #             })

    

    @api.model
    def create_patient(self, post):
        """Method for creating a patient and/or outpatient"""
        patient = False
        allocation = self.env['doctor.allocation'].sudo().browse(
            int(post['doctor'])
        ) if post and post.get('doctor') else False
        target_company_id = allocation.company_id.id or self.env.company.id
        partner_env = self.with_company(target_company_id).sudo()
        outpatient_env = self.env['hospital.outpatient'].with_company(
            target_company_id
        ).sudo()
        
        # ✅ Validate phone number if provided
        if post and post.get('op_phone'):
            phone = post.get('op_phone')
            # Remove any non-digit characters
            phone = ''.join(filter(str.isdigit, phone))
            
            if len(phone) != 10:
                return {
                    'success': False,
                    'message': 'Phone number must be exactly 10 digits. Please enter a valid 10-digit mobile number.'
                }
            post['op_phone'] = phone

        def _ensure_company_patient(base_patient):
            if not base_patient:
                return base_patient
            if not base_patient.company_id or base_patient.company_id.id == target_company_id:
                return base_patient

            lookup_domain = [('company_id', '=', target_company_id)]
            if base_patient.phone:
                lookup_domain.append(('phone', '=', base_patient.phone))
            else:
                lookup_domain.append(('name', '=', base_patient.name))

            company_patient = partner_env.search(lookup_domain, limit=1)
            if company_patient:
                return company_patient

            patient_vals = {
                'name': base_patient.name,
                'phone': base_patient.phone,
                'gender': base_patient.gender,
                'date_of_birth': base_patient.date_of_birth,
                'blood_group': base_patient.blood_group,
                'rh_type': base_patient.rh_type,
                'place': base_patient.place,
                'company_id': target_company_id,
                'customer_rank': 1,
            }
            return partner_env.create(patient_vals)

        # If patient_id is provided, use existing patient
        if post and post.get('patient_id'):
            patient = partner_env.browse(int(post['patient_id']))
            patient = _ensure_company_patient(patient)

        # If no patient_id but name provided, search or create new patient
        elif post and post.get('op_name'):
            domain = [
                ('name', '=', post['op_name']),
                '|',
                ('company_id', '=', False),
                ('company_id', '=', target_company_id),
            ]
            if post.get('op_phone'):
                domain = ['|', ('phone', '=', post['op_phone'])] + domain

            patient = partner_env.search(domain, limit=1)
            patient = _ensure_company_patient(patient)

            if not patient:
                patient_vals = {
                    'name': post['op_name'],
                    'blood_group': post.get('op_blood_group'),
                    'gender': post.get('op_gender'),
                    'company_id': target_company_id,
                    'customer_rank': 1,
                }
                if post.get('op_phone'):
                    patient_vals['phone'] = post['op_phone']
                if post.get('op_dob'):
                    patient_vals['date_of_birth'] = post['op_dob']

                try:
                    patient = partner_env.create(patient_vals)
                except Exception as e:
                    return {
                        'success': False,
                        'message': f'Error creating patient: {str(e)}'
                    }
        # Create outpatient record
        if patient and post.get('doctor') and post.get('date'):

            existing_op = outpatient_env.search([
                ('patient_id', '=', patient.id),
                ('op_date', '=', post['date']),
                ('doctor_id', '=', int(post['doctor']))
            ], limit=1)

            if not existing_op:

                op_vals = {
                    'patient_id': patient.id,
                    'op_date': post['date'],
                    'doctor_id': int(post['doctor']),
                    'company_id': target_company_id,
                }

                # Optional fields
                if post.get('habit_history'):
                    op_vals['habit_history'] = post['habit_history']

                if post.get('reason'):
                    op_vals['reason'] = post['reason']

                if post.get('slot'):
                    op_vals['slot'] = float(post['slot']) if post['slot'] else 0.0

                # ✅ Vitals
                if post.get('bp'):
                    op_vals['bp'] = post.get('bp')

                if post.get('temperature'):
                    op_vals['temperature'] = float(post.get('temperature'))

                if post.get('pulse'):
                    op_vals['pulse'] = int(post.get('pulse'))

                # ✅ Fix datetime format issue
                # if post.get('visit_time'):
                #     try:
                #         # Convert from HTML datetime-local format
                #         formatted_dt = datetime.strptime(
                #             post.get('visit_time'),
                #             "%Y-%m-%dT%H:%M"
                #         ).strftime("%Y-%m-%d %H:%M:%S")

                #         op_vals['visit_time'] = formatted_dt
                #     except Exception:
                #         pass
                if post.get('visit_time'):
                    op_vals['visit_time'] = post.get('visit_time')
                outpatient_env.create(op_vals)

                # return {
                #     'success': True,
                #     'message': 'Outpatient created successfully'
                # }
                return {
                    'success': True,
                    'patient_id': patient.id,
                    'message': 'Outpatient created successfully'
                }

            else:
                # return {
                #     'success': False,
                #     'message': 'Outpatient already exists for this patient today'
                # }
                return {
                    'success': False,
                    'patient_id': patient.id,
                    'message': 'Outpatient already exists for this patient today'
                }
        # return {
        #     'success': False,
        #     'message': 'Failed to create outpatient'
        # }
        return {
            'success': False,
            'patient_id': patient.id if patient else False,
            'message': 'Failed to create outpatient'
        }
        
    @api.model
    def fetch_patient_data(self):
        """Method for returning patient data"""
        return self.search_read(
            [('patient_seq', 'not in', ['Employee', 'User']),
             ('company_id', 'in', self.env.companies.ids)],
            ['id', 'name', 'patient_seq', 'phone', 'date_of_birth', 'gender', 'place', 'blood_group']
        )
