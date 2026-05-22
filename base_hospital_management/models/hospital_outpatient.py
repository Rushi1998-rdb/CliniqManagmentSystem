from odoo import api, fields, models
import base64
from odoo.exceptions import ValidationError
from odoo import api
from datetime import datetime
import logging
from odoo import tools
_logger = logging.getLogger(__name__)
logging.getLogger('odoo.addons.base_hospital_management').setLevel(logging.INFO)
class HospitalOutpatient(models.Model):
    """Class holding Outpatient details"""
    _name = 'hospital.outpatient'
    _description = 'Hospital Outpatient'
    _rec_name = 'op_reference'
    _inherit = 'mail.thread'
    
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company.id,
                                 help='Indicates the company')
    # _order = "visit_time_minutes asc"
    _order = "sort_priority asc, visit_time_minutes asc"

    # @api.model
    # def _generate_order_by(self, order_spec, query):
    #     """Force visit_time_minutes to ALWAYS be the primary sort key.
    #     If the user clicks 'Visit Time (Local)' in the UI, map it directly 
    #     to visit_time_minutes so the AM/PM float mapping sorts properly."""
    #     custom_order = "visit_time_minutes asc"
    #     if order_spec:
    #         # Map frontend column click to the backend database metric
    #         if 'visit_time_local' in order_spec:
    #             order_spec = order_spec.replace('visit_time_local', 'visit_time_minutes')
            
    #         if 'visit_time_minutes' not in order_spec:
    #             order_spec = f"{custom_order}, {order_spec}"
    #     else:
    #         order_spec = custom_order
    #     return super()._generate_order_by(order_spec, query)
    @api.model
    def _generate_order_by(self, order_spec, query):
        """Force sort_priority to ALWAYS be the primary sort key.
        This ensures 'Done' records always sink to the bottom.
        If the user clicks 'Visit Time (Local)', map it to visit_time_minutes."""
        if order_spec:
            # Map frontend column click to the backend database metric
            if 'visit_time_local' in order_spec:
                order_spec = order_spec.replace('visit_time_local', 'visit_time_minutes')
            
            # Unconditionally ensure sort_priority is the first rule
            if 'sort_priority' not in order_spec:
                order_spec = f"sort_priority asc, {order_spec}"
            
            # Also ensure visit_time_minutes is included as a fallback if not present
            if 'visit_time_minutes' not in order_spec:
                order_spec = f"{order_spec}, visit_time_minutes asc"
        else:
            order_spec = "sort_priority asc, visit_time_minutes asc"
        
        return super()._generate_order_by(order_spec, query)

    diagnosis = fields.Text(string="Medical History")
    suggestion = fields.Text(string="Suggestions")

    next_followup_datetime = fields.Datetime(
        string="Next Follow-up"
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='doctor_id.doctor_id.currency_id',
        
        readonly=True
    )
    queue_state_priority = fields.Integer(
        compute="_compute_queue_state_priority",
        store=True
    )

    blood_group = fields.Selection(
        string="Blood Group",
        related="patient_id.blood_group",
        readonly=True,
        store=False,
        compute_sudo=True
    )
    # blood_group_display = fields.Char(
    #     string="Blood Group",
    #     compute="_compute_blood_group_display",
    #     store=False,
    #     readonly=True
    # )
    # def _compute_blood_group_display(self):
    #     for rec in self:
    #         if rec.patient_id:
    #             blood_group = rec.patient_id.blood_group or ''
    #             rh_type = rec.patient_id.rh_type or ''
    #             if blood_group and rh_type:
    #                 rec.blood_group_display = f"{blood_group.upper()}{rh_type}"
    #             elif blood_group:
    #                 rec.blood_group_display = blood_group.upper()
    #             else:
    #                 rec.blood_group_display = ''
    #         else:
    #             rec.blood_group_display = ''

    patient_birthdate = fields.Date(
        string="Date of Birth",
        related="patient_id.date_of_birth",
        readonly=True,
        store=False,
        compute_sudo=True
    )

    patient_phone = fields.Char(
        string="Phone Number",
        related="patient_id.phone",
        readonly=True,
        store=False,
        compute_sudo=True
    )
    patient_gender = fields.Selection(
        string="Gender",
        related="patient_id.gender",
        readonly=True,
        store=False,
        compute_sudo=True
    )
    patient_age = fields.Integer(
        string="Age",
        related="patient_id.age",
        readonly=True,
        store=False,
        compute_sudo=True
    )

    patient_details = fields.Char(
        string="Patient Details",
        compute="_compute_patient_details",
        store=False,
        readonly=True,
        compute_sudo=True
    )
    visit_time = fields.Datetime(
        string="Visit Time"
    )
    visit_time_local = fields.Char(
        string="Visit Time (Local)",
        compute="_compute_visit_time_local",
        store=True
    )

    visit_time_minutes = fields.Integer(
        string="Visit Time (Minutes)",
        compute="_compute_visit_time_minutes",
        store=True,
        help="Time-of-day in local minutes (0-1439) used for ascending sort within queue groups"
    )

    sort_priority = fields.Integer(
        string="Sorting Priority",
        compute="_compute_sort_priority",
        store=True
    )

    @api.depends('state')
    def _compute_sort_priority(self):
        for rec in self:
            # Active records (waiting, op) get 0, Done gets 1.
            # This forces Done records to the bottom in an ascending sort.
            rec.sort_priority = 1 if rec.state == 'done' else 0


    def _compute_patient_details(self):
        for rec in self:
            patient = rec.sudo().patient_id
            if patient:
                details = []
                if patient.phone:
                    details.append(f"Phone {patient.phone}")
                if patient.date_of_birth:
                    details.append(
                        f"DOB {patient.date_of_birth.strftime('%d/%m/%Y')}"
                    )
                if patient.age:
                    details.append(f"({patient.age} yrs)")
                if patient.gender:
                    details.append(patient.gender.title())
                rec.patient_details = " | ".join(details)
            else:
                rec.patient_details = ""
        return
        for rec in self:
            if rec.patient_id:
                details = []
                if rec.patient_id.phone:
                    details.append(f"📞 {rec.patient_id.phone}")
                if rec.patient_id.date_of_birth:
                    dob = rec.patient_id.date_of_birth.strftime('%d/%m/%Y')
                    details.append(f"🎂 {dob}")
                if rec.patient_id.age:
                    details.append(f"({rec.patient_id.age} yrs)")
                if rec.patient_gender:
                    gender_icon = "👨" if rec.patient_gender == 'male' else "👩" if rec.patient_gender == 'female' else "👤"
                    details.append(f"{gender_icon} {rec.patient_gender.title()}")
                
                rec.patient_details = " | ".join(details)
            else:
                rec.patient_details = ""

                
    def _auto_init(self):
        """Backfill visit_time_minutes, queue_state_priority, and sort_priority for ALL existing
        records on every upgrade via direct SQL — no ORM recompute queue needed."""
        result = super()._auto_init()
        try:
            # ── visit_time_minutes: time-of-day in IST minutes (0-1439) ──────────
            self.env.cr.execute("""
                UPDATE hospital_outpatient
                SET visit_time_minutes = (
                    EXTRACT(HOUR FROM (
                        visit_time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata'
                    )) * 60 +
                    EXTRACT(MINUTE FROM (
                        visit_time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata'
                    ))
                )::integer
                WHERE visit_time IS NOT NULL
            """)
            self.env.cr.execute("""
                UPDATE hospital_outpatient
                SET visit_time_minutes = 9999
                WHERE visit_time IS NULL
            """)
            
            # ── queue_state_priority: seen=2 (bottom), everything else=1 ─────────
            self.env.cr.execute("""
                UPDATE hospital_outpatient
                SET queue_state_priority = CASE
                    WHEN patient_queue_type = 'seen' THEN 2
                    ELSE 1
                END
            """)
            
            self.env.cr.execute("""
                UPDATE hospital_outpatient
                SET sort_priority = CASE
                    WHEN state = 'done' THEN 1
                    ELSE 0
                END
            """)
            
        except Exception as e:
            _logger.error(f"Backfill failed in _auto_init: {e}")
        return result

    @api.depends('patient_queue_type')
    def _compute_queue_state_priority(self):
        """Two-bucket priority:
        - new + revisit  → 1  (shown together, sorted by visit_time ASC)
        - seen           → 2  (always at the bottom)"""
        for rec in self:
            if rec.patient_queue_type == 'seen':
                rec.queue_state_priority = 2
            else:  # 'new' or 'revisit'
                rec.queue_state_priority = 1


    general_fee = fields.Monetary(
        related='doctor_id.doctor_id.consultancy_charge',
        string="General Fee",
        currency_field='currency_id',
        readonly=True
    )



    total_amount = fields.Monetary(
        string="Total Amount",
        currency_field='currency_id',
        compute="_compute_total_amount",
        store=True
    )

    invoice_due_amount = fields.Monetary(
        string="Invoice Due Amount",
        currency_field='currency_id',
        compute="_compute_invoice_due_amount",
        store=False
    )

    total_due_amount = fields.Monetary(
        string="Total Due Amount",
        currency_field='currency_id',
        compute="_compute_total_due_amount",
        store=False
    )

    @api.depends('invoice_id', 'invoice_id.amount_residual')
    def _compute_invoice_due_amount(self):
        for rec in self:
            if rec.invoice_id:
                rec.invoice_due_amount = rec.invoice_id.amount_residual
            else:
                rec.invoice_due_amount = 0.0

    def _compute_total_due_amount(self):
        for rec in self:
            if rec.patient_id:
                invoices = self.env['account.move'].search([
                    ('partner_id', '=', rec.patient_id.id),
                    ('move_type', '=', 'out_invoice'),
                    ('state', '=', 'posted'),
                    ('payment_state', 'in', ['not_paid', 'partial'])
                ])
                rec.total_due_amount = sum(invoices.mapped('amount_residual'))
            else:
                rec.total_due_amount = 0.0


    op_reference = fields.Char(string="OP Reference", readonly=True,
                               default='New',
                               help='Op reference number of the patient')
    patient_id = fields.Many2one('res.partner',
                                 domain=[('patient_seq', 'not in',
                                          ['New', 'Employee', 'User'])],
                                 string='Patient ID', help='Id of the patient',
                                 required=True)
    # doctor_id = fields.Many2one('doctor.allocation',
    #                             string='Doctor',
    #                             help='Select the doctor',
    #                             required=True,
    #                             domain=[('slot_remaining', '>', 0),
    #                                     ('date', '=', fields.date.today()),
    #                                     ('state', '=', 'confirm')])
    doctor_id = fields.Many2one('doctor.allocation',
                                string='Doctor',
                                help='Select the doctor',
                                required=True,
                                domain="[('slot_remaining', '>', 0), "
                                       "('date', '>=', datetime.now().date()), "
                                       "('state', '=', 'confirm'), "
                                       "('company_id', '=', company_id)]")


    op_date = fields.Date(default=fields.Date.today(), string='Date',
                          help='Date of OP')
    habit_history = fields.Text(string='Habit History', help='Habits of the patient')
    reason = fields.Text(string='Reason', help='Reason for the visit')
    test_count = fields.Integer(string='Test Created',
                                help='Number of tests created for the patient',
                                compute='_compute_test_count')
    test_ids = fields.One2many('lab.test.line', 'op_id',
                               string='Tests',
                               help='Tests for the patient')
    # state = fields.Selection(
    #     [('draft', 'Draft'), ('op', 'OP'), ('inpatient', 'In Patient'),
    #      ('invoice', 'Invoiced'), ('cancel', 'Canceled')],
    #     default='draft', string='State', help='State of the outpatient')
    # state = fields.Selection(
    #     [('draft', 'Draft'),
    #     ('op', 'Ongoing'),
    #     ('inpatient', 'In Patient'),
    #     ('done', 'Done'),
    #     ('cancel', 'Canceled')],
    #     default='draft',
    #     string='State',
    # )
    op_date_display = fields.Char(
        string="Date Display",
        compute="_compute_op_date_display",
        store=False,
        help="Formatted date for display with count"
    )

    @api.model
    def get_op_dates_for_filter(self):
        """Get unique OP dates with counts for filter dropdown"""
        company_ids = tuple(self.env.companies.ids)
        if not company_ids:
            return []

        # Execute raw SQL to get unique dates with counts in descending order
        query = """
            SELECT 
                op_date,
                COUNT(id) as count
            FROM 
                hospital_outpatient
            WHERE 
                active = true
                AND (company_id IS NULL OR company_id IN %s)
            GROUP BY 
                op_date
            ORDER BY 
                op_date DESC
        """
        
        self.env.cr.execute(query, [company_ids])
        results = self.env.cr.fetchall()
        
        # Return list of tuples (display_string, domain_filter)
        date_filters = []
        for date, count in results:
            if date:
                display = f"{date.strftime('%d %b %Y')} ({count})"
                domain = [('op_date', '=', date)]
                date_filters.append((display, domain))
        
        return date_filters
    

    
    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=None, lazy=True):
        """Override read_group to ensure dates are sorted descending when grouping"""
        if groupby and any(group.startswith('op_date') for group in groupby):
            if orderby:
                if 'op_date' not in orderby:
                    orderby = f'op_date desc, {orderby}'
            else:
                orderby = 'op_date desc'
        return super(HospitalOutpatient, self).read_group(domain, fields, groupby, offset, limit, orderby, lazy)
    

    def _compute_op_date_display(self):
        """Compute display string for date with count"""
        for rec in self:
            # Count records for this date
            count = self.search_count([
                ('op_date', '=', rec.op_date),
                '|',
                ('company_id', '=', False),
                ('company_id', 'in', self.env.companies.ids),
            ])
            if rec.op_date:
                # Format date as "09 Apr 2026 (2)"
                rec.op_date_display = f"{rec.op_date.strftime('%d %b %Y')} ({count})"
            else:
                rec.op_date_display = False

    state = fields.Selection(
        [
            ('waiting', 'Waiting'),
            ('op', 'Ongoing'),
            ('done', 'Done'),
        ],
        default='waiting',
        string='State',
    )

    display_patient_name = fields.Char(
        string="Patient",
        compute="_compute_display_patient_name",
        store=False,
        compute_sudo=True
    )

    @api.depends('patient_id', 'patient_queue_type')
    def _compute_display_patient_name(self):
        for rec in self:
            patient = rec.sudo().patient_id
            if not patient:
                rec.display_patient_name = ""
                continue

            if rec.patient_queue_type == 'new':
                rec.display_patient_name = f"New {patient.name}"
            elif rec.patient_queue_type == 'revisit':
                rec.display_patient_name = f"Follow-up {patient.name}"
            else:
                rec.display_patient_name = patient.name
        return
        for rec in self:
            if not rec.patient_id:
                rec.display_patient_name = ""
                continue

            if rec.patient_queue_type == 'new':
                rec.display_patient_name = f"🟢 New {rec.patient_id.name}"
            elif rec.patient_queue_type == 'revisit':
                rec.display_patient_name = f"🟣 Follow-up {rec.patient_id.name}"
            else:
                rec.display_patient_name = rec.patient_id.name

    def action_receive_payment(self):
        for rec in self:
            rec.state = 'done'

    patient_queue_type = fields.Selection(
        [
            ('new', 'New'),
            ('revisit', 'Revisit'),
            ('seen', 'Seen'),
        ],
        compute="_compute_patient_queue_type",
        store=True
    )

    # ------------------------
    # A. Chief Complaint
    # ------------------------
    chief_complaint = fields.Text(string="Chief Complaint",help='Reason for Visit')

    # ------------------------
    # B. Duration
    # ------------------------
    # Temporary fix for Selection -> Char transition error
    class CharField(fields.Char):
        ondelete = {}

    duration = CharField(string="Duration")

    duration_note = fields.Char(string="Duration Note")

    patient_place = fields.Char(
        string="Place",
        related="patient_id.place",
        store=True,
        compute_sudo=True
    )

    # ------------------------
    # C. Vitals
    # ------------------------
    temperature = fields.Float(string="Temperature")
    bp = fields.Char(string="Blood Pressure")
    pulse = fields.Integer(string="Pulse")
    spo2 = fields.Integer(string="SpO₂")
    weight = fields.Float(string="Weight")
    height = fields.Char(string="Height")

    # ------------------------
    # D. Aggravating Factor
    # ------------------------
    aggravating_factor = fields.Text(string="Aggravating Factor")

    # ------------------------
    # E. Clinical Notes
    # ------------------------
    clinical_notes = fields.Text(string="Diagnosis")
    on_examination = fields.Text(string="Symptoms")

    # ------------------------
    # F. Diagnosis
    # ------------------------
    diagnosis = fields.Text(string="Medical History")

    # ------------------------
    # G. Differential Diagnosis
    # ------------------------
    differential_diagnosis = fields.Text(string="Family History")

    # ------------------------
    # H. Case Type
    # ------------------------
    case_type = fields.Selection([
        ('new', 'New'),
        ('follow_up', 'Follow-up'),
        ('chronic', 'Chronic'),
    ], string="Case Type")

    payment_mode = fields.Selection([
        ('cash', 'Cash'),
        ('online', 'Online')
    ], string="Payment Mode")

    def _get_text_line_count(self, value, chars_per_line=50):
        if not value:
            return 0
        line_count = 0
        for line in value.splitlines() or ['']:
            line_count += max(1, (len(line) + chars_per_line - 1) // chars_per_line)
        return line_count

    @api.constrains(
        'chief_complaint',
        'on_examination',
        'clinical_notes',
        'diagnosis',
        'differential_diagnosis'
    )
    def _check_clinical_text_line_limits(self):
        chars_per_line = 50
        line_limits = {
            'chief_complaint': ('Chief Complaint', 5),
            'on_examination': ('Symptoms', 5),
            'clinical_notes': ('Diagnosis', 10),
            'diagnosis': ('Medical History', 5),
            'differential_diagnosis': ('Family History', 5),
        }
        for rec in self:
            for field_name, (label, max_lines) in line_limits.items():
                line_count = rec._get_text_line_count(
                    rec[field_name],
                    chars_per_line=chars_per_line
                )
                if line_count > max_lines:
                    raise ValidationError(
                        "%s can contain only %s lines, approximately %s characters."
                        % (label, max_lines, max_lines * chars_per_line)
                    )

    def action_receive_payment(self):
        for rec in self:
            if not rec.payment_mode:
                raise ValidationError("Please select Payment Mode first.")
            rec.state = 'done'


    @api.onchange('patient_id')
    def _onchange_patient_id(self):
        if self.patient_id:
            self.temperature = self.patient_id.temperature
            self.bp = self.patient_id.bp
            self.weight = self.patient_id.weight
            self.height = self.patient_id.height
    # @api.depends('patient_id', 'state', 'op_date')
    # def _compute_patient_queue_type(self):
    #     today = fields.Date.today()

    #     for rec in self:

    #         # Count previous OPs BEFORE this record
    #         previous_op_count = self.env['hospital.outpatient'].search_count([
    #             ('patient_id', '=', rec.patient_id.id),
    #             ('id', '!=', rec.id),
    #         ])

    #         # 1️⃣ If today's patient AND Done → Seen
    #         if rec.op_date == today and rec.state == 'invoice':
    #             rec.patient_queue_type = 'seen'

    #         # 2️⃣ If has previous visits → Revisit
    #         elif previous_op_count > 0:
    #             rec.patient_queue_type = 'revisit'

    #         # 3️⃣ Otherwise → New
    #         else:
    #             rec.patient_queue_type = 'new'

    @api.depends('patient_id', 'state', 'op_date')
    def _compute_patient_queue_type(self):
        today = fields.Date.today()

        for rec in self:
            if not rec.patient_id:
                rec.patient_queue_type = 'new'
                continue

            # Count previous visits BEFORE this OP date
            previous_visits = self.env['hospital.outpatient'].search_count([
                ('patient_id', '=', rec.patient_id.id),
                ('op_date', '<', rec.op_date),
            ])

            # 1️⃣ Seen (Today's completed patients)
            if rec.op_date == today and rec.state == 'done':
                rec.patient_queue_type = 'seen'

            # 2️⃣ Revisit (Had visits before today)
            elif previous_visits > 0:
                rec.patient_queue_type = 'revisit'

            # 3️⃣ New (First ever visit)
            else:
                rec.patient_queue_type = 'new'



    prescription_ids = fields.One2many('prescription.line',
                                       'outpatient_id',
                                       string='Prescription',
                                       help='Prescription for the patient')
    invoice_id = fields.Many2one('account.move', copy=False,
                                 string='Invoice',
                                 help='Invoice of the patient')
    invoice_state = fields.Selection(
        related='invoice_id.state', string="Invoice State", store=True
    )
    payment_state = fields.Selection(
        related='invoice_id.payment_state', string="Payment State", store=True
    )

    def action_create_invoice(self):
        for rec in self:
            if not rec.patient_id:
                raise ValidationError("Patient is required to create an invoice.")
            if rec.invoice_id:
                raise ValidationError("Invoice already exists for this record.")
            
            # Search for a dedicated Doctor journal
            journal = self.env['account.journal'].sudo().search([
                ('type', '=', 'sale'), 
                ('code', '=', 'DOC'), 
                ('company_id', '=', rec.company_id.id)
            ], limit=1)
            
            if not journal:
                journal = self.env['account.journal'].sudo().create({
                    'name': 'Doctor Invoices',
                    'type': 'sale',
                    'code': 'DOC',
                    'company_id': rec.company_id.id,
                })
                
            income_account = journal.default_account_id
            if not income_account:
                income_account = self.env['account.account'].sudo().search([
                    ('account_type', 'in', ['income', 'income_other']), 
                    ('company_id', '=', rec.company_id.id)
                ], limit=1)
                
            if not income_account:
                # Automatically create an income account so the user isn't blocked
                try:
                    income_account = self.env['account.account'].sudo().create({
                        'name': 'Consultation Income',
                        'code': '400100',
                        'account_type': 'income',
                        'company_id': rec.company_id.id,
                    })
                except Exception:
                    # Fallback code if 400100 somehow conflicts
                    try:
                        income_account = self.env['account.account'].sudo().create({
                            'name': 'Consultation Income',
                            'code': '400999',
                            'account_type': 'income',
                            'company_id': rec.company_id.id,
                        })
                    except Exception:
                        pass

            if not income_account:
                raise ValidationError(f"Could not automatically create an Income Account for {rec.company_id.name}. Please go to Accounting -> Configuration -> Settings and install a Chart of Accounts for this company.")
                
            invoice_lines = []
            
            # 1. General Fee
            if rec.general_fee > 0:
                invoice_lines.append((0, 0, {
                    'name': 'General Consultation Fee',
                    'quantity': 1,
                    'price_unit': rec.general_fee,
                    'account_id': income_account.id if income_account else False,
                }))
                
            # 2. Additional Charges
            for charge in rec.charge_ids:
                if charge.amount > 0:
                    invoice_lines.append((0, 0, {
                        'name': charge.charge_type_id.name,
                        'quantity': 1,
                        'price_unit': charge.amount,
                        'account_id': income_account.id if income_account else False,
                    }))
                    
            if not invoice_lines:
                raise ValidationError("There are no fees or charges to invoice.")
                
            # Ensure the patient has a Receivable account set (Required for the payment_term line)
            patient = rec.patient_id.with_company(rec.company_id)
            if not patient.property_account_receivable_id:
                receivable_account = self.env['account.account'].sudo().search([
                    ('account_type', '=', 'asset_receivable'),
                    ('company_id', '=', rec.company_id.id)
                ], limit=1)
                
                if not receivable_account:
                    try:
                        receivable_account = self.env['account.account'].sudo().create({
                            'name': 'Account Receivable (Auto)',
                            'code': '100100',
                            'account_type': 'asset_receivable',
                            'reconcile': True,
                            'company_id': rec.company_id.id,
                        })
                    except Exception:
                        try:
                            receivable_account = self.env['account.account'].sudo().create({
                                'name': 'Account Receivable (Auto)',
                                'code': '100199',
                                'account_type': 'asset_receivable',
                                'reconcile': True,
                                'company_id': rec.company_id.id,
                            })
                        except Exception:
                            pass
                            
                if receivable_account:
                    patient.sudo().property_account_receivable_id = receivable_account.id
                else:
                    raise ValidationError(f"Could not automatically create a Receivable Account for {rec.company_id.name}. Please configure Chart of Accounts.")
                
            invoice_vals = {
                'move_type': 'out_invoice',
                'partner_id': rec.patient_id.id,
                'journal_id': journal.id,
                'invoice_line_ids': invoice_lines,
                'outpatient_id': rec.id,
                'company_id': rec.company_id.id,
            }
            
            # Force the sequence for the very first invoice in this journal
            existing_moves = self.env['account.move'].sudo().search([('journal_id', '=', journal.id)], limit=1)
            if not existing_moves:
                invoice_vals['name'] = 'INV/DOC/00001'
            
            invoice = self.env['account.move'].sudo().create(invoice_vals)
            rec.invoice_id = invoice.id
            invoice.sudo().action_post()
            
        return True

    def action_view_invoice(self):
        self.ensure_one()
        return {
            'name': 'Invoice',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
        }
    attachment_id = fields.Many2one('ir.attachment',
                                    string='Attachment',
                                    help='Attachments related to the'
                                         ' outpatient')
    active = fields.Boolean(string='Active', help='True for active patients',
                            default=True)
    # slot = fields.Float(string='Slot', help='Slot for the patient',
    #                     copy=False, readonly=True)
    slot = fields.Integer(string='Slot',help='Slot for the patient', required=False)
    is_sale_created = fields.Boolean(string='Sale Created',
                                     help='True if sale order created')


    consultancy_charge = fields.Monetary(
        related='doctor_id.doctor_id.consultancy_charge',
        string="Consultation Charge",
        store=True,
        readonly=True
    )

    associated_patient_ids = fields.Many2many(
        'res.partner',
        string="Associated Patients",
        compute='_compute_associated_patients'
    )

    lab_result_ids = fields.One2many(
        'hospital.lab.result',
        'outpatient_id',
        string="Lab Results"
    )

    associated_patient_count = fields.Integer(
        string="Associated Patients Count",
        compute='_compute_associated_patients'
    )
    # bp_systolic = fields.Integer(string="BP (Systolic)")
    # bp_diastolic = fields.Integer(string="BP (Diastolic)")
    # temperature = fields.Float(string="Temperature (°C)")


    # @api.onchange('doctor_id')
    # def _onchange_doctor_id(self):
    #     print("Doctor Allocation:", self.doctor_id)
    #     print("Employee:", self.doctor_id.doctor_id)
    #     print("Charge:", self.doctor_id.doctor_id.consultancy_charge)
    #     if self.doctor_id and self.doctor_id.doctor_id:
    #         self.general_fee = self.doctor_id.doctor_id.consultancy_charge
    #     else:
    #         self.general_fee = 0.0



    # @api.model
    # def create(self, vals):
    #     _logger.warning("VISIT TIME RECEIVED >>> %s", vals.get('visit_time'))
    #     if vals.get('patient_id'):
    #         patient = self.env['res.partner'].browse(vals['patient_id'])

    #         vals.setdefault('temperature', patient.temperature or 0.0)
    #         vals.setdefault('bp', patient.bp or '')
    #         vals.setdefault('weight', patient.weight or 0.0)
    #         vals.setdefault('height', patient.height or '')

    #     # OP Reference
    #     if vals.get('op_reference', 'New') == 'New':
    #         last_op = self.search([('op_reference', '!=', 'New')],
    #                             order='create_date desc',
    #                             limit=1)

    #         if last_op:
    #             last_number = int(last_op.op_reference[2:])
    #             vals['op_reference'] = f'OP{str(last_number + 1).zfill(3)}'
    #         else:
    #             vals['op_reference'] = 'OP001'

    #     return super().create(vals)
    def _parse_datetime_string(self, datetime_str):
        """Parse datetime string from various formats"""
        if not datetime_str:
            return False
        
        try:
            # First, replace T with space if present
            datetime_str = datetime_str.replace('T', ' ')
            
            # Now try different formats
            formats = [
                "%Y-%m-%d %H:%M:%S",  # With seconds
                "%Y-%m-%d %H:%M",     # Without seconds
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(datetime_str, fmt)
                except ValueError:
                    continue
            
            raise ValueError(f"Unable to parse datetime: {datetime_str}")
            
        except Exception as e:
            _logger.error(f"Error parsing datetime: {e}")
            return False
        


    # def _compute_visit_time_local(self):
    #     for rec in self:
    #         if rec.visit_time:
    #             try:
    #                 import pytz
    #                 from datetime import datetime
                    
    #                 # Get user's timezone
    #                 user_tz = self.env.user.tz or 'UTC'
    #                 user_timezone = pytz.timezone(user_tz)
                    
    #                 # Since stored datetime is naive UTC, make it timezone-aware as UTC
    #                 utc_dt = pytz.UTC.localize(rec.visit_time)
                    
    #                 # Convert to user's local timezone
    #                 local_dt = utc_dt.astimezone(user_timezone)
                    
    #                 # Format for display in 12-hour format with AM/PM
    #                 rec.visit_time_local = local_dt.strftime("%Y-%m-%d %I:%M:%S %p")
    #                 # %I = 12-hour format (01-12)
    #                 # %p = AM/PM
                    
    #             except Exception as e:
    #                 _logger.error(f"Error converting to local time: {e}")
    #                 rec.visit_time_local = str(rec.visit_time)
    #         else:
    #             rec.visit_time_local = False

    @api.depends('visit_time')
    def _compute_visit_time_local(self):
        for rec in self:
            if rec.visit_time:
                try:
                    import pytz
                    
                    user_tz = self.env.user.tz or 'UTC'
                    user_timezone = pytz.timezone(user_tz)
                    utc_dt = pytz.UTC.localize(rec.visit_time)
                    local_dt = utc_dt.astimezone(user_timezone)
                    
                    # Calculate minutes to create an invisible sorting prefix (0-1439)
                    minutes = local_dt.hour * 60 + local_dt.minute
                    
                    # Create an 11-bit invisible binary prefix using Zero Width Space ('0') and Zero Width Non-Joiner ('1').
                    # This forces the browser's alphabetical string sorter to perfectly sort chronologically behind the scenes.
                    binary_str = f"{minutes:011b}"
                    invisible_prefix = binary_str.replace('0', '\u200B').replace('1', '\u200C')
                    
                    # ✅ Invisible prefix + strict 12-hour AM/PM format
                    rec.visit_time_local = invisible_prefix + local_dt.strftime("%I:%M %p")
                    
                except Exception as e:
                    _logger.error(f"Error converting to local time: {e}")
                    rec.visit_time_local = str(rec.visit_time)
            else:
                rec.visit_time_local = False

    @api.depends('visit_time')
    def _compute_visit_time_minutes(self):
        """Compute time-of-day in minutes (0–1439) from visit_time, in local timezone.
        Used as the sort key so records inside the same queue group always
        appear in ascending clock-time order, regardless of UTC date.
        Records without a visit_time get 9999 (sorts last in the group)."""
        import pytz
        for rec in self:
            if rec.visit_time:
                try:
                    tz_name = self.env.user.tz or 'Asia/Kolkata'
                    local_dt = pytz.UTC.localize(rec.visit_time).astimezone(
                        pytz.timezone(tz_name)
                    )
                    rec.visit_time_minutes = local_dt.hour * 60 + local_dt.minute
                except Exception as e:
                    _logger.error(f"Error computing visit_time_minutes: {e}")
                    rec.visit_time_minutes = 9999
            else:
                rec.visit_time_minutes = 9999  # No time set → sort last


    def create(self, vals):
        if vals.get('visit_time') and isinstance(vals.get('visit_time'), str):
            try:
                from datetime import datetime
                import pytz

                visit_time_str = vals.get('visit_time')
                if 'T' in visit_time_str:
                    visit_time_str = visit_time_str.replace('T', ' ')
                if visit_time_str.count(':') == 1:
                    visit_time_str += ':00'

                naive_dt = datetime.strptime(visit_time_str, "%Y-%m-%d %H:%M:%S")

                # ✅ Fixed: Use Asia/Kolkata as fallback instead of broken company.tz
                user_tz = self.env.user.tz or 'Asia/Kolkata'
                user_timezone = pytz.timezone(user_tz)
                user_datetime = user_timezone.localize(naive_dt)
                utc_datetime = user_datetime.astimezone(pytz.UTC)
                vals['visit_time'] = utc_datetime.replace(tzinfo=None)

                _logger.info(f"Converted visit_time: input={visit_time_str}, tz={user_tz}, stored={vals['visit_time']}")

            except Exception as e:
                _logger.error(f"Error converting visit_time: {e}", exc_info=True)
                vals['visit_time'] = None
        
        _logger.warning("VISIT TIME RECEIVED >>> %s", vals.get('visit_time'))

        if not vals.get('company_id'):
            allocation = self.env['doctor.allocation'].browse(vals.get('doctor_id')) \
                if vals.get('doctor_id') else self.env['doctor.allocation']
            vals['company_id'] = allocation.company_id.id or self.env.company.id
        
        if vals.get('patient_id'):
            patient = self.env['res.partner'].browse(vals['patient_id'])
            vals.setdefault('temperature', patient.temperature or 0.0)
            vals.setdefault('bp', patient.bp or '')
            vals.setdefault('weight', patient.weight or 0.0)
            vals.setdefault('height', patient.height or '')

        # OP Reference
        if vals.get('op_reference', 'New') == 'New':
            last_op = self.search([('op_reference', '!=', 'New')],
                                order='create_date desc',
                                limit=1)

            if last_op:
                last_number = int(last_op.op_reference[2:])
                vals['op_reference'] = f'OP{str(last_number + 1).zfill(3)}'
            else:
                vals['op_reference'] = 'OP001'

        return super().create(vals)
    @api.model
    def create_patient(self, post):
        """Method for creating a patient and/or outpatient"""
        patient = False
        allocation = self.env['doctor.allocation'].sudo().browse(
            int(post['doctor'])
        ) if post and post.get('doctor') else False
        target_company_id = allocation.company_id.id or self.env.company.id
        partner_env = self.env['res.partner'].with_company(target_company_id).sudo()
        outpatient_env = self.with_company(target_company_id).sudo()
        
        _logger.error("=" * 50)
        _logger.error("START create_patient")
        _logger.error(f"Received post data: {post}")
        _logger.error("=" * 50)
        
        # Import pytz for timezone handling (optional, since we'll handle in create)
        try:
            import pytz
        except ImportError:
            pytz = None

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
            if patient:
                _logger.error(f"Found patient: {patient.name} (ID: {patient.id})")

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
                }
                if post.get('op_phone'):
                    patient_vals['phone'] = post['op_phone']
                if post.get('op_dob'):
                    patient_vals['date_of_birth'] = post['op_dob']

                try:
                    patient = partner_env.create(patient_vals)
                    _logger.error(f"New patient created with ID: {patient.id}")
                except Exception as e:
                    _logger.error(f"Error creating patient: {e}")
                    return {
                        'success': False,
                        'message': f'Error creating patient: {str(e)}'
                    }

        # Check for required fields
        if not patient:
            return {
                'success': False,
                'message': 'Patient not found or created'
            }
        
        if not post.get('doctor'):
            return {
                'success': False,
                'message': 'Doctor is required'
            }
        
        if not post.get('date'):
            return {
                'success': False,
                'message': 'Date is required'
            }

        # Create outpatient record
        existing_op = outpatient_env.search([
            ('patient_id', '=', patient.id),
            ('op_date', '=', post['date']),
            ('doctor_id', '=', int(post['doctor']))
        ], limit=1)

        if existing_op:
            return {
                'success': False,
                'patient_id': patient.id,
                'message': 'Outpatient already exists for this patient today'
            }

        op_vals = {
            'patient_id': patient.id,
            'op_date': post['date'],
            'doctor_id': int(post['doctor']),
            'company_id': target_company_id,
        }

        # Optional fields
        if post.get('reason'):
            op_vals['reason'] = post['reason']

        if post.get('slot'):
            op_vals['slot'] = float(post['slot']) if post['slot'] else 0.0

        # Vitals
        if post.get('bp'):
            op_vals['bp'] = post.get('bp')

        if post.get('temperature'):
            op_vals['temperature'] = float(post.get('temperature'))

        if post.get('pulse'):
            op_vals['pulse'] = int(post.get('pulse'))

        # Visit time - pass as is, the create method will handle it
        if post.get('visit_time'):
            op_vals['visit_time'] = post.get('visit_time')
            _logger.error(f"Visit time to be processed in create: {op_vals['visit_time']}")

        # Create the outpatient record - the create method will handle datetime conversion
        try:
            new_op = outpatient_env.create(op_vals)
            _logger.error(f"Outpatient created successfully with ID: {new_op.id}")
            
            return {
                'success': True,
                'patient_id': patient.id,
                'message': 'Outpatient created successfully'
            }
        except Exception as e:
            _logger.error(f"Error creating outpatient: {e}", exc_info=True)
            return {
                'success': False,
                'patient_id': patient.id,
                'message': f'Error creating outpatient: {str(e)}'
            }
        
    @api.constrains('slot', 'doctor_id', 'op_date')
    def _check_duplicate_slot(self):
        for rec in self:
            if not rec.slot:
                continue

            duplicate = self.search([
                ('id', '!=', rec.id),
                ('doctor_id', '=', rec.doctor_id.id),
                ('op_date', '=', rec.op_date),
                ('slot', '=', rec.slot),
                '|',
                ('company_id', '=', False),
                ('company_id', '=', rec.company_id.id)
            ], limit=1)

            if duplicate:
                # Format the date nicely
                date_str = rec.op_date.strftime('%d %B %Y') if rec.op_date else 'selected date'
                raise ValidationError(
                    f"Slot {rec.slot} is already assigned for this doctor on {date_str}.\n"
                    f"Please choose a different slot."
                )

    @api.depends('test_ids')
    def _compute_test_count(self):
        """Computes the value of test count"""
        self.test_count = len(self.test_ids.ids)

    # @api.onchange('op_date')
    # def _onchange_op_date(self):
    #     """Method for updating the domain of doctor_id"""
    #     self.doctor_id = False
    #     return {'domain': {'doctor_id': [('slot_remaining', '>', 0),
    #                                      ('date', '=', self.op_date),
    #                                      ('state', '=', 'confirm'), (
    #                                          'patient_type', 'in',
    #                                          [False, 'outpatient'])]}}

    charge_ids = fields.One2many(
        'hospital.outpatient.charge', 'outpatient_id',
        string="Additional Charges"
    )

    @api.onchange('op_date')
    def _onchange_op_date(self):
        """Method for updating the domain of doctor_id"""
        self.doctor_id = False
        if self.op_date:
            return {'domain': {'doctor_id': [('slot_remaining', '>', 0),
                                            ('date', '=', self.op_date),  # Keep '=' for exact date match
                                            ('state', '=', 'confirm'), 
                                            ('patient_type', 'in', [False, 'outpatient'])]}}
        return {}



    @api.model
    def action_row_click_data(self, op_reference):
        """Returns data to be displayed on clicking op row"""
        op_record = self.env['hospital.outpatient'].sudo().search(
            [('op_reference', '=', op_reference),
             ('active', 'in', [True, False])])
        op_data = [op_reference, op_record.patient_id.patient_seq,
                   op_record.patient_id.name, str(op_record.op_date),
                   op_record.slot, op_record.reason,
                   op_record.doctor_id.doctor_id.name,
                   op_record.is_sale_created]
        medicines = []
        for rec in op_record.prescription_ids:
            medicines.append(
                [rec.medicine_id.name, rec.no_intakes, rec.time, rec.note,
                 rec.quantity, rec.medicine_id.id])
        return {
            'op_data': op_data,
            'medicines': medicines
        }

    @api.model
    def create_medicine_sale_order(self, order_id):
        """Method for creating sale order for medicines"""
        order = self.sudo().search([('op_reference', 'ilike', order_id)])
        sale_order = self.env['sale.order'].sudo().create({
            'partner_id': order.patient_id.id,
        })
        for i in order.prescription_ids:
            self.env['sale.order.line'].sudo().create({
                'product_id': i.medicine_id.id,
                'product_uom_qty': i.quantity,
                'order': sale_order.id,
            })
            self.create_invoice()

    @api.model
    def create_file(self, rec_id):
        """Method for creating prescription"""
        record = self.env['hospital.outpatient'].sudo().browse(rec_id)
        p_list = []
        data = False
        for rec in record.prescription_ids:
            p_list.append({
                'medicine': rec.medicine_id.name,
                'intake': rec.no_intakes,
                'time': rec.time.capitalize(),
                'quantity': rec.quantity,
                'note': rec.note.capitalize() if rec.note else '',
            })
            data = {
                'datas': p_list,
                'date': record.op_date,
                'patient_name': record.patient_id.name,
                'doctor_name': record.doctor_id.doctor_id.name,
            }
        pdf = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'base_hospital_management.action_report_patient_prescription',
            rec_id, data=data)
        record.attachment_id = self.env['ir.attachment'].sudo().create({
            'datas': base64.b64encode(pdf[0]),
            'name': "Prescription",
            'type': 'binary',
            'res_model': 'hospital.outpatient',
            'res_id': rec_id,
        })
        return {
            'url': f'/web/content'
                   f'/{record.attachment_id.id}?download=true&amp'
                   f';access_token=',
        }

    @api.model
    def create_new_out_patient(self, kw):
        """Create out patient from receptionist dashboard"""
        if kw['id']:
            partner = self.env['res.partner'].sudo().search(
                ['|', ('barcode', '=', kw['id']),
                 ('phone', '=', kw['op_phone'])])
            self.sudo().create({
                'patient_id': partner.id,
                'op_date': kw['date'],
                'reason': kw['reason'],
                'slot': kw['slot'],
                'doctor_id': kw['doctor'],
            })

    def action_create_lab_test(self):
        """Button action for creating a lab test"""
        return {
            'name': 'Create Lab Test',
            'res_model': 'lab.test.line',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'current',
            'type': 'ir.actions.act_window',
            'context': {
                'default_patient_id': self.patient_id.id,
                'default_doctor_id': self.doctor_id.id,
                'default_patient_type': 'outpatient',
                'default_op_id': self.id
            }
        }

    def action_view_test(self):
        """Method for viewing all lab tests"""
        return {
            'name': 'Created Tests',
            'res_model': 'lab.test.line',
            'view_mode': 'tree,form',
            'target': 'current',
            'type': 'ir.actions.act_window',
            'domain': [
                ('patient_type', '=', 'outpatient'),
                ('op_id', '=', self.id)
            ]
        }

    def action_convert_to_inpatient(self):
        """Converts an outpatient to inpatient"""
        self.state = 'inpatient'
        return {
            'name': 'Convert to Inpatient',
            'res_model': 'hospital.inpatient',
            'view_mode': 'form',
            'target': 'current',
            'type': 'ir.actions.act_window',
            'context': {
                'default_patient_id': self.patient_id.id,
                'default_attending_doctor_id': self.doctor_id.doctor_id.id,
            }
        }

    def action_op_cancel(self):
        """Button action for cancelling an op"""
        self.state = 'cancel'

    # def action_confirm(self):
    #     """Button action for confirming an op"""
    #     if self.doctor_id.latest_slot == 0:
    #         self.slot = self.doctor_id.work_from
    #     else:
    #         self.slot = self.doctor_id.latest_slot + self.doctor_id.time_avg
    #     self.doctor_id.latest_slot = self.slot
    #     self.state = 'op'

    # def action_confirm(self):
    #     for rec in self:
    #         if not rec.slot:
    #             raise ValidationError("Please enter slot number.")

    #         rec.state = 'op'
    def action_confirm(self):
        for rec in self:
            # Slot is optional, so we don't validate it
            # If you want to validate when slot is provided, you can add:
            if rec.slot and rec.slot <= 0:
                raise ValidationError("Slot number must be a positive integer.")
            
            rec.state = 'op'

    # def create_invoice(self):
    #     """Method for creating invoice"""
    #     self.state = 'invoice'
    #     self.invoice_id = self.env['account.move'].sudo().create({
    #         'move_type': 'out_invoice',
    #         'date': fields.Date.today(),
    #         'invoice_date': fields.Date.today(),
    #         'partner_id': self.patient_id.id,
    #         'invoice_line_ids': [(
    #             0, 0, {
    #                 'name': 'Consultation fee',
    #                 'quantity': 1,
    #                 'price_unit': self.doctor_id.doctor_id.consultancy_charge,
    #             }
    #         )]
    #     })
    #     self.invoiced = True

    # def create_invoice(self):
    #     """Method for creating invoice"""
    #     self.state = 'invoice'

    #     invoice_lines = []

    #     # Consultation Fee Line
    #     if self.general_fee:
    #         invoice_lines.append((0, 0, {
    #             'name': 'Consultation Fee',
    #             'quantity': 1,
    #             'price_unit': self.general_fee,
    #         }))

    #     # Injection / Additional Charges Line
    #     if self.injection_charge:
    #         invoice_lines.append((0, 0, {
    #             'name': 'Injection / Additional Charges',
    #             'quantity': 1,
    #             'price_unit': self.injection_charge,
    #         }))

    #     self.invoice_id = self.env['account.move'].sudo().create({
    #         'move_type': 'out_invoice',
    #         'date': fields.Date.today(),
    #         'invoice_date': fields.Date.today(),
    #         'partner_id': self.patient_id.id,
    #         'invoice_line_ids': invoice_lines,
    #     })

    #     self.invoiced = True
    # def action_view_invoice(self):
    #     """Method for viewing invoice"""
    #     return {
    #         'name': 'Invoice',
    #         'domain': [('id', '=', self.invoice_id.id)],
    #         'type': 'ir.actions.act_window',
    #         'res_model': 'account.move',
    #         'view_mode': 'tree,form',
    #         'context': {'create': False},
    #     }

    def action_print_prescription(self):
        p_list = []

        for rec in self.prescription_ids:
            times = ', '.join(time.name.capitalize() for time in rec.selected_times)
            p_list.append({
                'medicine': rec.medicine_id.name,
                'intake': rec.no_intakes,
                'time': times or 'Not specified',
                'quantity': rec.quantity,
                'note': rec.note.capitalize() if rec.note else '',
            })

        data = {
            'datas': p_list,
            'date': self.op_date,
            'patient_name': self.patient_id.name,
            'doctor_name': self.doctor_id.doctor_id.name,
            'diagnosis': self.diagnosis or '',
        }

        return self.env.ref(
            'base_hospital_management.action_report_patient_prescription'
        ).report_action(self)
    
    @api.depends('patient_id')
    def _compute_associated_patients(self):
        for rec in self:
            if rec.patient_id and rec.patient_id.phone:
                patients = self.env['res.partner'].search([
                    ('phone', '=', rec.patient_id.phone),
                    ('id', '!=', rec.patient_id.id)
                ])
                rec.associated_patient_ids = patients
                rec.associated_patient_count = len(patients)
            else:
                rec.associated_patient_ids = False
                rec.associated_patient_count = 0

    def action_view_associated_patients(self):
        return {
            'name': 'Associated Patients',
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.associated_patient_ids.ids)],
            'target': 'current',
        }
    @api.model
    def fetch_dashboard_stats(self):
        """Fetch dashboard statistics for the current doctor in the active company."""
        today = fields.Date.context_today(self)
        user = self.env.user
        company_id = self.env.company.id
        
        is_manager = user.has_group('base_hospital_management.base_hospital_management_group_manager') or \
                     user.has_group('base.group_system')
        employee_profile = self.env['hr.employee'].get_current_employee_profile()
        doctor_employee_id = employee_profile.get('employee_id')
        
        def get_records_for_date(target_date):
            domain = [('op_date', '=', target_date), ('company_id', '=', company_id)]
            if not is_manager and doctor_employee_id:
                domain.append(('doctor_id.doctor_id', '=', doctor_employee_id))
            elif not is_manager:
                domain.append(('doctor_id.doctor_id.user_id', '=', user.id))
            return self.search(domain)

        outpatients = get_records_for_date(today)

        # Only today's active-company records should contribute to dashboard stats.
        active_new = outpatients.filtered(lambda o: o.patient_queue_type == 'new' and o.state in ['waiting', 'op'])
        active_followup = outpatients.filtered(lambda o: o.patient_queue_type in ['revisit', 'seen'] and o.state in ['waiting', 'op'])
        
        completed = outpatients.filtered(lambda o: o.state == 'done')
        pending = outpatients.filtered(lambda o: o.state in ['waiting', 'op'])
        
        cash_total = sum(outpatients.filtered(lambda o: o.payment_mode == 'cash').mapped('total_amount'))
        online_total = sum(outpatients.filtered(lambda o: o.payment_mode == 'online').mapped('total_amount'))
        
        return {
            'today_new_patients': len(active_new),
            'today_followup_patients': len(active_followup),
            'total_consultations': len(outpatients),
            'completed_consultations': len(completed),
            'pending_consultations': len(pending),
            'today_cash_collection': cash_total,
            'today_upi_collection': online_total,
            'today_total_collection': cash_total + online_total,
            'server_date': today.strftime('%Y-%m-%d')
        }


class HospitalOutpatientCharge(models.Model):
    _name = 'hospital.outpatient.charge'
    _description = 'Outpatient Charges'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='outpatient_id.company_id',
        store=True,
        index=True
    )
    charge_type_id = fields.Many2one(
        'hospital.charge.type',
        string="Charge Name",
        required=True
    )
    amount = fields.Monetary(string="Amount", required=True)
    currency_id = fields.Many2one(
        'res.currency',
        related='outpatient_id.currency_id',
        string="Currency"
    )
    outpatient_id = fields.Many2one(
        'hospital.outpatient',
        string="Outpatient Reference",
        ondelete='cascade'
    )


class HospitalChargeType(models.Model):
    _name = 'hospital.charge.type'
    _description = 'Hospital Charge Type'

    name = fields.Char(string="Charge Name", required=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True
    )

