/** @odoo-module */
import { registry} from '@web/core/registry';
import { useService } from "@web/core/utils/hooks";
import { useRef, useState } from "@odoo/owl";
import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

// Doctor dashboard component initialization
export class DoctorDashboard extends Component {
    setup() {
        super.setup(...arguments);
        this.ref = useRef('root')
        this.orm = useService('orm')
        this.user = useService("user");
        this.actionService = useService("action");
        this.welcome = useRef("welcome");
        
        // Get doctor name from current user
        this.doctorName = this.user.name || "Doctor";
        this.doctorInitial = this.doctorName.charAt(0).toUpperCase();
        
        // Get current user's partner ID
        this.currentPartnerId = this.user.partnerId;
        
        console.log("Current user:", this.user);
        console.log("Partner ID:", this.currentPartnerId);
        
        this.state = useState({
            patients : [],
            search_button : false,
            patients_search :[],
            profileImage: false,
            employeeId: false,
            currentCompanyId: false,
            isAdminView: false,
            
            // Statistics
            today_new_patients: 0,
            today_followup_patients: 0,
            completed_consultations: 0,
            total_consultations: 0,
            pending_consultations: 0,
            
            // Collection data - ADD THESE
            today_cash_collection: 0,
            today_upi_collection: 0,
            today_total_collection: 0,
            serverDate: false,
        });
        
        // Fetch employee profile picture on load
        this.fetchEmployeeProfile();
        
        // Fetch statistics
        this.fetchTodayStatistics();
        
        // Debug method
        this.debugCheckModel();
    }

    getTodayDateString() {
        const today = new Date();
        const year = today.getFullYear();
        const month = String(today.getMonth() + 1).padStart(2, '0');
        const day = String(today.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }

    async getTodayDoctorDomain(extraDomain = []) {
        if (!this.state.currentCompanyId) {
            this.state.currentCompanyId = await this.orm.call('res.users', 'get_current_company_id', []);
        }

        if (!this.state.isAdminView) {
            const isSystemAdmin = await this.orm.call('res.users', 'has_group', ['base.group_system']);
            const isHospitalManager = await this.orm.call('res.users', 'has_group', ['base_hospital_management.base_hospital_management_group_manager']);
            this.state.isAdminView = Boolean(isSystemAdmin || isHospitalManager);
        }

        let employeeId = this.state.employeeId;
        if (!this.state.isAdminView && !employeeId) {
            const profile = await this.orm.call('hr.employee', 'get_current_employee_profile', []);
            if (profile && profile.employee_id) {
                employeeId = profile.employee_id;
                this.state.employeeId = employeeId;
                this.state.currentCompanyId = profile.company_id || this.state.currentCompanyId;
                if (profile.image_1920) {
                    this.state.profileImage = profile.image_1920;
                }
            }
        }

        const today = this.state.serverDate || this.getTodayDateString();
        const domain = [['op_date', '=', today], ['company_id', '=', this.state.currentCompanyId || 0], ...extraDomain];

        if (this.state.isAdminView) {
            return domain;
        }

        if (employeeId) {
            domain.splice(2, 0, ['doctor_id.doctor_id', '=', employeeId]);
        } else {
            domain.splice(2, 0, ['doctor_id.doctor_id.user_id', '=', this.user.userId || 0]);
        }

        return domain;
    }
    
    // Method to fetch employee profile picture
    async fetchEmployeeProfile() {
        try {
            const profile = await this.orm.call('hr.employee', 'get_current_employee_profile', []);

            if (profile && profile.employee_id) {
                this.state.profileImage = profile.image_1920;
                this.state.employeeId = profile.employee_id;
                this.state.currentCompanyId = profile.company_id;
                console.log("Employee profile found:", profile);
                await this.fetchTodayStatistics();
            } else {
                this.state.currentCompanyId = await this.orm.call('res.users', 'get_current_company_id', []);
                console.log("No employee found for user ID:", this.user.userId);
                await this.fetchTodayStatistics();
            }
        } catch (error) {
            console.error("Error fetching employee profile:", error);
            this.state.currentCompanyId = await this.orm.call('res.users', 'get_current_company_id', []);
        }
    }
    
    // Fetch today's statistics
    async fetchTodayStatistics() {
        try {
            // Call server-side method to get accurate stats
            const stats = await this.orm.call('hospital.outpatient', 'fetch_dashboard_stats', []);
            console.log("Dashboard stats from server:", stats);
            
            if (stats) {
                this.state.today_new_patients = stats.today_new_patients;
                this.state.today_followup_patients = stats.today_followup_patients;
                this.state.total_consultations = stats.total_consultations;
                this.state.completed_consultations = stats.completed_consultations;
                this.state.pending_consultations = stats.pending_consultations;
                
                this.state.today_cash_collection = stats.today_cash_collection;
                this.state.today_upi_collection = stats.today_upi_collection;
                this.state.today_total_collection = stats.today_total_collection;
                this.state.serverDate = stats.server_date;
            }
            
        } catch (error) {
            console.error("Error fetching statistics:", error);
        }
    }
    
    // View methods for collection
    async viewCashPayments() {
        const today = this.getTodayDateString();
        const domain = await this.getTodayDoctorDomain([
            ['payment_mode', '=', 'cash'],
            ['total_amount', '>', 0]
        ]);
        
        this.actionService.doAction({
            name: _t('Cash Payments Today'),
            type: 'ir.actions.act_window',
            res_model: 'hospital.outpatient',
            view_mode: 'tree,form',
            views: [
                [false, 'tree'],
                [false, 'form']
            ],
            domain: domain,
            context: {
                'search_default_op_date': today,
            }
        });
    }
    
    async viewUPIPayments() {
        const today = this.getTodayDateString();
        const domain = await this.getTodayDoctorDomain([
            ['payment_mode', '=', 'online'],
            ['total_amount', '>', 0]
        ]);
        
        this.actionService.doAction({
            name: _t('UPI Payments Today'),
            type: 'ir.actions.act_window',
            res_model: 'hospital.outpatient',
            view_mode: 'tree,form',
            views: [
                [false, 'tree'],
                [false, 'form']
            ],
            domain: domain,
            context: {
                'search_default_op_date': today,
            }
        });
    }

    // Add this temporary debug method
    async debugDoctorRecords() {
        try {
            console.log("=== DEBUG: Checking all records for current doctor ===");
            
            const allRecords = await this.orm.searchRead('hospital.outpatient', [
                ['doctor_id', '=', this.currentPartnerId]
            ], ['id', 'op_reference', 'op_date', 'patient_queue_type', 'state']);
            
            console.log("All records for this doctor:", allRecords);
            
            // Group by date
            const byDate = {};
            allRecords.forEach(record => {
                const date = record.op_date;
                if (!byDate[date]) byDate[date] = [];
                byDate[date].push(record);
            });
            
            console.log("Records by date:", byDate);
            
        } catch (error) {
            console.error("Debug error:", error);
        }
    }

    // Call this in setup() temporarily
    // this.debugDoctorRecords();
    
    // Debug method to check available models
    async debugCheckModel() {
        try {
            console.log("=== DEBUG: Checking available models ===");
            
            // Check if hospital.outpatient model exists
            try {
                const modelData = await this.orm.call('ir.model', 'search_read', [
                    [['model', '=', 'hospital.outpatient']], 
                    ['model', 'name']
                ]);
                console.log("hospital.outpatient model data:", modelData);
            } catch (e) {
                console.log("Error checking hospital.outpatient model:", e);
            }
            
            // Check all models that might be related
            const allModels = await this.orm.call('ir.model', 'search_read', [
                [], ['model', 'name'], 0, 20
            ]);
            
            const patientModels = allModels.filter(m => 
                m.model.includes('patient') || 
                m.model.includes('outpatient') || 
                m.model.includes('inpatient')
            );
            
            console.log("Patient-related models:", patientModels);
            
        } catch (error) {
            console.error("Debug error:", error);
        }
    }
        
    // View methods for the circles
    async viewNewPatients() {
        const today = this.getTodayDateString();
        const domain = await this.getTodayDoctorDomain([
            ['patient_queue_type', '=', 'new'],
            ['state', 'in', ['waiting', 'op']]
        ]);
        console.log("Viewing New Patients for date:", today);
        
        this.actionService.doAction({
            name: _t('New Patients Today'),
            type: 'ir.actions.act_window',
            res_model: 'hospital.outpatient',
            view_mode: 'tree,form',
            views: [
                [false, 'tree'],
                [false, 'form']
            ],
            domain: domain,
            context: {
                'search_default_op_date': today,
                'default_op_date': today,
            }
        });
    }

    async viewFollowupPatients() {
        const today = this.getTodayDateString();
        const domain = await this.getTodayDoctorDomain([
            ['patient_queue_type', 'in', ['revisit', 'seen']],
            ['state', 'in', ['waiting', 'op']]
        ]);
        console.log("Viewing Follow-up Patients for date:", today);
        
        this.actionService.doAction({
            name: _t('Follow-up Patients Today'),
            type: 'ir.actions.act_window',
            res_model: 'hospital.outpatient',
            view_mode: 'tree,form',
            views: [
                [false, 'tree'],
                [false, 'form']
            ],
            domain: domain,
            context: {
                'search_default_op_date': today,
                'default_op_date': today,
            }
        });
    }

    async viewCompletedConsultations() {
        const today = this.getTodayDateString();
        const domain = await this.getTodayDoctorDomain([
            ['state', '=', 'done']
        ]);
        console.log("Viewing Completed Consultations for date:", today);
        
        this.actionService.doAction({
            name: _t('Completed Consultations'),
            type: 'ir.actions.act_window',
            res_model: 'hospital.outpatient',
            view_mode: 'tree,form',
            views: [
                [false, 'tree'],
                [false, 'form']
            ],
            domain: domain,
            context: {
                'search_default_op_date': today,
                'default_op_date': today,
            }
        });
    }

    async viewPendingConsultations() {
        const today = this.getTodayDateString();
        const domain = await this.getTodayDoctorDomain([
            ['state', 'in', ['waiting', 'op']],
        ]);
        console.log("Viewing Pending Consultations for date:", today);
        
        this.actionService.doAction({
            name: _t('Pending Consultations'),
            type: 'ir.actions.act_window',
            res_model: 'hospital.outpatient',
            view_mode: 'tree,form',
            views: [
                [false, 'tree'],
                [false, 'form']
            ],
            domain: domain,
            context: {
                'search_default_op_date': today,
                'default_op_date': today,
            }
        });
    }
    
    // Method to update profile picture in hr.employee
    async updateProfilePicture() {
        if (!this.state.employeeId) {
            // Show error if no employee linked
            this.actionService.doAction({
                type: 'ir.actions.client',
                tag: 'display_notification',
                params: {
                    title: _t('Error'),
                    message: _t('No employee record linked to your user'),
                    type: 'danger',
                    sticky: false,
                }
            });
            return;
        }
        
        // Create file input
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        
        input.onchange = async (ev) => {
            const file = ev.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = async (e) => {
                    const imageData = e.target.result.split(',')[1];
                    
                    // Save to employee record
                    await this.orm.call('hr.employee', 'write', [[this.state.employeeId], {
                        'image_1920': imageData
                    }]);
                    
                    // Update state to refresh the image
                    this.state.profileImage = imageData;
                    
                    // Show success notification
                    this.actionService.doAction({
                        type: 'ir.actions.client',
                        tag: 'display_notification',
                        params: {
                            title: _t('Success'),
                            message: _t('Profile picture updated successfully'),
                            type: 'success',
                            sticky: false,
                        }
                    });
                };
                reader.readAsDataURL(file);
            }
        };
        
        input.click();
    }
    
    // Existing methods
    async list_patient_data(){
        this.actionService.doAction({
            name: _t('Patient details'),
            type: 'ir.actions.act_window',
            res_model: 'res.partner',
            view_mode: 'tree,form',
            views: [[false, 'list'],[false, 'form']],
            domain: [['patient_seq', 'not in', ['New', 'Employee', 'User']]]
        });
        const patients = await this.orm.call('res.partner', 'fetch_patient_data', [],);
        if (self.$('.n_active')[0]){
            self.$('.n_active')[0].classList.remove('n_active');
        }
        self.$('.patient_data')[0].classList.add('n_active');
        self.listPatient = patients;
    }

    action_list_inpatient() {
        this.actionService.doAction({
            name: _t('Inpatient details'),
            type: 'ir.actions.act_window',
            res_model: 'hospital.inpatient',
            view_mode: 'tree,form',
            views: [[false, 'list'],[false, 'form']],
        });
    }

    fetch_doctors_schedule() {
         this.actionService.doAction({
            name: _t('Surgery details'),
            type: 'ir.actions.act_window',
            res_model: 'inpatient.surgery',
            view_mode: 'tree,form',
            views: [[false, 'tree'],[false, 'form']],
        });
    }

    async fetch_consultation(){
        const today = this.getTodayDateString();
        const domain = await this.getTodayDoctorDomain();

        this.actionService.doAction({
            name: _t("Today's Outpatient Details"),
            type: 'ir.actions.act_window',
            res_model: 'hospital.outpatient',
            view_mode: 'tree,form',
            views: [[false, 'tree'], [false, 'form']],
            target: 'current',
            domain: domain,
            context: {
                search_default_today: 1,
                search_default_op_date: today,
                default_op_date: today,
            },
        });
    }

    fetch_allocation_lines() {
        this.actionService.doAction({
            name: _t('Doctor Allocation'),
            type: 'ir.actions.act_window',
            res_model: 'doctor.allocation',
            view_mode: 'tree,form',
            views: [[false, 'list'],[false, 'form']]
        });
    }
}

DoctorDashboard.template = "DoctorDashboard"
registry.category("actions").add('doctor_dashboard_tags', DoctorDashboard);
