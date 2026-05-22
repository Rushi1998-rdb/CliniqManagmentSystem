/** @odoo-module */
import { registry } from '@web/core/registry';
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, useState, useRef, onWillStart } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
// import { useState } from "@odoo/owl";
class ReceptionDashBoard extends Component {

    setup() {
        this.ref = useRef('root');

        // Only keep refs that exist in XML
        this.out_patient = useRef('out-patient');
        this.rd_buttons = useRef('rd_buttons');

        this.action = useService('action');
        this.orm = useService("orm");
        this.user = useService("user");

        this.state = useState({
            patient_lst: [],
            visit_time: this.getCurrentTime(),
            today_followups: 0,
            today_new_patients: 0,
            today_total_patients: 0,
            pending_followups: 0,
            loading: true,
            chart_initialized: false,
            today_cash_collection: 0,
            today_upi_collection: 0,
            today_total_collection: 0,
            collection_percentage: 0,
            currentCompanyId: false
        });
        this.datePicker = null;      // for OP Date
        this.datePickerDOB = null;   // for Date of Birth
        this.dateTimePicker = null;  // for Visit Time
        onWillStart(async () => {
            await this.loadFollowupStatistics();
        });

        onMounted(async () => {
            await this.fetchAppointmentData();

            // live clock
            setInterval(() => {
                this.state.visit_time = this.getCurrentTime();
            }, 1000);
        });
    }
    getCurrentTime() {
        const now = new Date();
        return now.toLocaleTimeString();
    }
    // Load collection statistics for today
    async loadCollectionStatistics() {
        try {
            const today = new Date().toISOString().split('T')[0];
            
            // Get all today's outpatients that are done
            const outpatients = await this.orm.searchRead('hospital.outpatient', [
                ['op_date', '=', today],
                ['state', '=', 'done']
            ], ['total_amount', 'payment_mode']);
            
            let cashTotal = 0;
            let upiTotal = 0;
            
            outpatients.forEach(patient => {
                const amount = patient.total_amount || 0;
                if (patient.payment_mode === 'cash') {
                    cashTotal += amount;
                } else if (patient.payment_mode === 'online') {
                    upiTotal += amount;
                }
            });
            
            const totalCollection = cashTotal + upiTotal;
            
            this.state.today_cash_collection = cashTotal;
            this.state.today_upi_collection = upiTotal;
            this.state.today_total_collection = totalCollection;
            
            // Calculate percentage for display (optional)
            if (totalCollection > 0) {
                this.state.collection_percentage = ((cashTotal / totalCollection) * 100).toFixed(1);
            } else {
                this.state.collection_percentage = 0;
            }
            
            // Initialize collection donut chart
            setTimeout(() => {
                this.initCollectionDonutChart();
            }, 500);
            
        } catch (error) {
            console.error("Error loading collection statistics:", error);
        }
    }

    // Initialize collection donut chart
    initCollectionDonutChart() {
        const canvas = document.getElementById('collectionDonutChart');
        if (!canvas) {
            setTimeout(() => this.initCollectionDonutChart(), 500);
            return;
        }
        
        const ctx = canvas.getContext('2d');
        
        const data = {
            datasets: [{
                data: [this.state.today_cash_collection, this.state.today_upi_collection],
                backgroundColor: ['#2ecc71', '#3498db'],
                borderWidth: 0,
            }]
        };
        
        const total = this.state.today_total_collection;
        
        const options = {
            responsive: true,
            maintainAspectRatio: true,
            cutout: '65%',
            plugins: {
                legend: { 
                    display: false  // This removes the colored square box
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const value = context.raw || 0;
                            const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                            if (context.dataIndex === 0) {
                                return `Cash: ₹${value.toLocaleString('en-IN')} (${percentage}%)`;
                            } else {
                                return `UPI: ₹${value.toLocaleString('en-IN')} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        };
        
        if (window.collectionChart) {
            window.collectionChart.destroy();
        }
        window.collectionChart = new Chart(ctx, {
            type: 'doughnut',
            data: data,
            options: options
        });
    }
    // View cash payments
    viewCashPayments() {
        const today = new Date().toISOString().split('T')[0];
        
        this.action.doAction({
            name: _t('Cash Payments Today'),
            type: 'ir.actions.act_window',
            res_model: 'hospital.outpatient',
            view_mode: 'tree,form',
            views: [[false, 'tree'], [false, 'form']],
            domain: [['op_date', '=', today], ['payment_mode', '=', 'cash'], ['state', '=', 'done']],
            context: {
                'search_default_op_date': today,
            }
        });
    }

    // View UPI payments
    viewUPIPayments() {
        const today = new Date().toISOString().split('T')[0];
        
        this.action.doAction({
            name: _t('UPI Payments Today'),
            type: 'ir.actions.act_window',
            res_model: 'hospital.outpatient',
            view_mode: 'tree,form',
            views: [[false, 'tree'], [false, 'form']],
            domain: [['op_date', '=', today], ['payment_mode', '=', 'online'], ['state', '=', 'done']],
            context: {
                'search_default_op_date': today,
            }
        });
    }
    async loadFollowupStatistics() {
        this.state.loading = true;
        try {
            const today = new Date().toISOString().split('T')[0];
            
            // Get all today's outpatients
            const outpatients = await this.orm.searchRead('hospital.outpatient', [
                ['op_date', '=', today]
            ], ['id', 'patient_queue_type', 'state', 'patient_id', 'op_reference', 'total_amount', 'payment_mode']);
            
            console.log("Today's outpatients:", outpatients); // Debug log
            
            // Calculate statistics
            const followups = outpatients.filter(o => o.patient_queue_type === 'revisit').length;
            const newPatients = outpatients.filter(o => o.patient_queue_type === 'new').length;
            const total = outpatients.length;
            const pendingFollowups = outpatients.filter(o => 
                o.patient_queue_type === 'revisit' && o.state !== 'done'
            ).length;
            
            // Calculate collection
            const doneOutpatients = outpatients.filter(o => o.state === 'done');
            let cashTotal = 0;
            let upiTotal = 0;
            
            doneOutpatients.forEach(patient => {
                const amount = patient.total_amount || 0;
                if (patient.payment_mode === 'cash') {
                    cashTotal += amount;
                } else if (patient.payment_mode === 'online') {
                    upiTotal += amount;
                }
            });
            
            this.state.today_followups = followups;
            this.state.today_new_patients = newPatients;
            this.state.today_total_patients = total;
            this.state.pending_followups = pendingFollowups;
            this.state.today_cash_collection = cashTotal;
            this.state.today_upi_collection = upiTotal;
            this.state.today_total_collection = cashTotal + upiTotal;
            
            console.log("Statistics loaded:", {
                followups, newPatients, total, pendingFollowups,
                cashTotal, upiTotal, totalCollection: cashTotal + upiTotal
            });
            
            // Initialize charts after DOM is ready
            setTimeout(() => {
                this.initDonutChart();
                this.initMiniDonutChart();
                this.initCollectionDonutChart();
            }, 500);
            
        } catch (error) {
            console.error("Error loading follow-up statistics:", error);
        } finally {
            this.state.loading = false;
        }
    }

    // Method to set current time in visit time field
    setCurrentVisitTime() {
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const day = String(now.getDate()).padStart(2, '0');
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        
        const currentDateTime = `${year}-${month}-${day}T${hours}:${minutes}`;
        
        const visitTimeInput = $('#op_visit_time');
        if (visitTimeInput.length && !visitTimeInput.val()) {
            visitTimeInput.val(currentDateTime);
        }
    }
    // Initialize the main donut chart
    initDonutChart() {
        const canvas = document.getElementById('followupDonutChart');
        if (!canvas) {
            console.log("Canvas element not found, retrying...");
            setTimeout(() => this.initDonutChart(), 500);
            return;
        }
        
        if (this.state.chart_initialized) return;
        
        console.log("Initializing main donut chart with data:", {
            followups: this.state.today_followups,
            newPatients: this.state.today_new_patients
        });
        
        const ctx = canvas.getContext('2d');
        
        // Data: Follow-ups (Orange) vs New Patients (Green)
        const data = {
            labels: ['Follow-up Patients', 'New Patients'],
            datasets: [{
                data: [this.state.today_followups, this.state.today_new_patients],
                backgroundColor: ['#ff9800', '#2ecc71'],
                borderWidth: 0,
                hoverOffset: 4
            }]
        };
        
        const total = this.state.today_followups + this.state.today_new_patients;
        
        const options = {
            responsive: true,
            maintainAspectRatio: true,
            cutout: '65%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        font: { size: 12 },
                        padding: 10,
                        generateLabels: function(chart) {
                            const data = chart.data;
                            return data.labels.map((label, i) => ({
                                text: `${label}: ${data.datasets[0].data[i]} (${((data.datasets[0].data[i] / total) * 100).toFixed(1)}%)`,
                                fillStyle: data.datasets[0].backgroundColor[i],
                                hidden: false,
                                index: i
                            }));
                        }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.raw || 0;
                            const percentage = ((value / total) * 100).toFixed(1);
                            return `${label}: ${value} (${percentage}%)`;
                        }
                    }
                }
            }
        };
        
        try {
            if (window.followupChart) {
                window.followupChart.destroy();
            }
            window.followupChart = new Chart(ctx, {
                type: 'doughnut',
                data: data,
                options: options
            });
            this.state.chart_initialized = true;
            console.log("Main donut chart created successfully");
        } catch (error) {
            console.error("Error creating chart:", error);
        }
    }

    // Refresh statistics (called when new patient is added)
    async refreshStatistics() {
        await this.loadFollowupStatistics();
    }

    // View all follow-up patients
    viewFollowupPatients() {
        const today = new Date().toISOString().split('T')[0];
        
        this.action.doAction({
            name: _t('Today\'s Follow-up Patients'),
            type: 'ir.actions.act_window',
            res_model: 'hospital.outpatient',
            view_mode: 'tree,form',
            views: [[false, 'tree'], [false, 'form']],
            domain: [
                ['op_date', '=', today],
                ['patient_queue_type', '=', 'revisit'],
                ['state', '!=', 'done']
            ],
            context: {
                'search_default_op_date': today,
                'default_op_date': today,
            }
        });
    }

    // View all patients today
    viewAllPatients() {
        const today = new Date().toISOString().split('T')[0];
        
        this.action.doAction({
            name: _t('Today\'s All Patients'),
            type: 'ir.actions.act_window',
            res_model: 'hospital.outpatient',
            view_mode: 'tree,form',
            views: [[false, 'tree'], [false, 'form']],
            domain: [
                ['op_date', '=', today]
            ],
            context: {
                'search_default_op_date': today,
            }
        });
    }

    async fetch_patient_id() {
        const patientId = $('#sl_patient').val();

        if (patientId === "create_new") {
            const phone = $('#o_patient-phone').val();
            
            // ✅ Validate phone number before creating new patient
            if (!phone || phone.trim() === '') {
                alert('Please enter a phone number first.');
                return;
            }
            
            // Remove any non-digit characters
            const phoneDigits = phone.replace(/\D/g, '');
            if (phoneDigits.length !== 10) {
                alert('Please enter a valid 10-digit mobile number before creating a new patient.');
                return;
            }

            // Open patient creation form with pre-filled phone number
            this.action.doAction({
                type: 'ir.actions.act_window',
                name: 'Create New Patient',
                res_model: 'res.partner',
                views: [[false, 'form']],
                view_mode: 'form',
                target: 'new',
                context: {
                    default_phone: phoneDigits,
                    default_name: '',  // Empty name for user to fill
                    default_gender: '',
                    default_date_of_birth: false,
                    form_view_ref: 'base_hospital_management.res_partner_view_form'
                }
            }, {
                onClose: async () => {
                    console.log("Patient creation wizard closed. Refreshing patient list...");
                    
                    // Refresh the patient dropdown with the newly created patient
                    const phoneDigits = $('#o_patient-phone').val().replace(/\D/g, '');
                    
                    // Fetch patients again
                    const patients = await this.orm.call(
                        'res.partner',
                        'search_read',
                        [[['phone', '=', phoneDigits]]],
                        { fields: ['id', 'name', 'patient_seq', 'date_of_birth', 'age_display'] }
                    );

                    let options = '<option value="">Select Patient</option>';
                    
                    patients.forEach(p => {
                        const age = p.age_display ? ` (${p.age_display})` : this.getAgeDisplay(p.date_of_birth);
                        options += `
                            <option value="${p.id}">
                                ${p.patient_seq || ''} - ${p.name}${age}
                            </option>
                        `;
                    });
                    
                    // Always add "Create New" option
                    options += `
                        <option value="create_new" style="color: green; font-weight: bold;">➕ Create New Patient</option>
                    `;
                    
                    $('#sl_patient').html(options);
                    
                    // Auto-select the newly created patient (the last one)
                    if (patients.length > 0) {
                        const latest = patients[patients.length - 1].id;
                        $('#sl_patient').val(latest);
                        
                        // Fetch and display patient details
                        await this.fetch_patient_id();
                    }
                }
            });
            return;
        }

        if (!patientId) return;

        const patient = await this.orm.call(
            'res.partner',
            'search_read',
            [[['id', '=', parseInt(patientId)]]],
            { fields: ['name', 'phone', 'date_of_birth', 'blood_group', 'gender', 'place'] }
        );

        if (patient.length > 0) {
            const data = patient[0];
            $('#o_patient-name').val(data.name || '');
            $('#o_patient-phone').val(data.phone || '');
            $('#o_patient-dob').val(data.date_of_birth || '');
            if (data.date_of_birth) {
                const formattedDOB = this.formatISOToDMY(data.date_of_birth);
                $('#o_patient-dob').val(formattedDOB);
                $('#o_patient-dob').attr('data-iso', data.date_of_birth);
            } else {
                $('#o_patient-dob').val('');
                $('#o_patient-dob').removeAttr('data-iso');
            }
            $('#o_patient_bloodgroup').val(data.blood_group || '');
            $('#o_patient_place').val(data.place || '');

            if (data.gender) {
                $(`input[name="gender"][value="${data.gender}"]`).prop('checked', true);
            }
            
            // ✅ Show success message
            $('#search-result-message').html(
                '<div class="alert alert-success">✓ Patient selected: ' + data.name + '</div>'
            );
        }
    }
    // Method for creating patient
    // createPatient() {
    //     if ($('.r_active')[0]) { $('.r_active')[0].classList.remove('r_active'); }
    //     $('.o_patient_button')[0].classList.add('r_active');
    //     this.room_ward.el.classList.add("d-none");
    //     this.patient_creation.el.classList.remove("d-none");
    //     this.out_patient.el.classList.add("d-none");
    //     this.inpatient.el.classList.add("d-none");
    //     this.rd_buttons.el.classList.add("d-none");
    //     this.ward.el.classList.add("d-none");
    //     this.room.el.classList.add("d-none");
        
    //     // Reset search when opening patient creation
    //     this.resetSearch();
    // }
    createPatient() {

        if ($('.o_patient_button')[0]) {
            if ($('.r_active')[0]) { $('.r_active')[0].classList.remove('r_active'); }
            $('.o_patient_button')[0].classList.add('r_active');
        }

        if (this.room_ward.el) this.room_ward.el.classList.add("d-none");
        if (this.patient_creation.el) this.patient_creation.el.classList.remove("d-none");
        if (this.out_patient.el) this.out_patient.el.classList.add("d-none");
        if (this.inpatient.el) this.inpatient.el.classList.add("d-none");
        if (this.rd_buttons.el) this.rd_buttons.el.classList.add("d-none");
        if (this.ward.el) this.ward.el.classList.add("d-none");
        if (this.room.el) this.room.el.classList.add("d-none");

        this.resetSearch();
    }
    // Calculate age from date of birth
    calculateAge(ev) {
        const dob = $('#patient-dob').val();
        if (!dob) {
            $('#patient-age').val('');
            return;
        }
        
        const birthDate = new Date(dob);
        const today = new Date();
        
        let age = today.getFullYear() - birthDate.getFullYear();
        const monthDiff = today.getMonth() - birthDate.getMonth();
        
        // Adjust age if birthday hasn't occurred yet this year
        if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
            age--;
        }
        
        $('#patient-age').val(age + ' years');
    }

    // Reset search fields
    // resetSearch() {
    //     this.state.search_mode = false;
    //     this.state.found_patients = [];
    //     this.state.selected_patient = null;
    //     this.state.show_new_patient_form = false;
    //     $('#search-phone').val('');
    //     $('#search-result-message').html('');
    //     $('#patient-select-dropdown').hide();
    //     this.clearPatientForm();
    // }
    // Reset search fields
    resetSearch() {
        this.state.show_new_patient_form = false;
        $('#search-phone').val('');
        $('#search-result-message').html('');
        $('#existing-patients-list').html(''); // Clear the patients list
        this.clearPatientForm();
    }

    // Clear patient form fields
    clearPatientForm() {
        $('#patient-name').val('');
        $('#patient-dob').val('');
        $('#patient-phone').val('');
        $('#patient-mail').val('');
        $('#patient-weight').val('');
        $('#patient-height').val('');
        $('#patient-bloodgroup').val('');
        $("input[name='rhtype']").prop('checked', false);
        $('#rhtype[value="+"]').prop('checked', true);
        $("input[name='gender']").prop('checked', false);
        $('#patient-m-status').val('');
        $('#patient-img').val('');
    }

    // Search patient by phone number
    // async searchPatientByPhone() {
    //     const phone = $('#search-phone').val().trim();
        
    //     if (!phone) {
    //         $('#search-result-message').html('<div class="alert alert-warning">Please enter a phone number</div>');
    //         return;
    //     }

    //     try {
    //         const patients = await this.orm.call(
    //             'res.partner',
    //             'search_read',
    //             [[['phone', '=', phone], ['patient_seq', 'not in', ['New', 'Employee', 'User']]]],
    //             { fields: ['id', 'name', 'phone', 'date_of_birth', 'blood_group', 'rh_type', 'gender', 'marital_status', 'email', 'height', 'weight', 'image_1920'] }
    //         );

    //         if (patients && patients.length > 0) {
    //             // Multiple patients found with same phone number
    //             this.state.search_mode = true;
    //             this.state.found_patients = patients;
    //             this.state.show_new_patient_form = false;
                
    //             // Show patient selection dropdown
    //             this.showPatientSelection(patients);
                
    //         } else {
    //             // No patient found - show new patient form
    //             this.state.search_mode = true;
    //             this.state.found_patients = [];
    //             this.state.selected_patient = null;
    //             this.state.show_new_patient_form = true;
    //             this.clearPatientForm();
    //             $('#patient-phone').val(phone); // Pre-fill phone number
    //             $('#search-result-message').html(
    //                 '<div class="alert alert-info">No patient found. Please fill details to create new patient.</div>'
    //             );
    //             $('#patient-select-dropdown').hide();
    //         }
    //     } catch (error) {
    //         console.error("Error searching patient:", error);
    //         $('#search-result-message').html(
    //             '<div class="alert alert-danger">Error searching patient. Please try again.</div>'
    //         );
    //     }
    // }
    // Search patient by phone number
    async searchPatientByPhone(ev) {
        // If triggered by keyup event, only proceed if Enter key was pressed
        if (ev && ev.type === 'keyup' && ev.key !== 'Enter') {
            return;
        }
        
        const phone = $('#search-phone').val().trim();
        
        if (!phone) {
            $('#search-result-message').html('<div class="alert alert-warning">Please enter a phone number</div>');
            $('#existing-patients-list').html('');
            return;
        }

        try {
            const patients = await this.orm.call(
                'res.partner',
                'search_read',
                [[['phone', '=', phone], ['patient_seq', 'not in', ['New', 'Employee', 'User']]]],
                { fields: ['id', 'name', 'phone', 'date_of_birth', 'blood_group', 'gender', 'age_display'] }
            );

            if (patients && patients.length > 0) {
                // Display list of existing patients
                let patientListHtml = '<div class="alert alert-info"><strong>Existing patients with this phone number:</strong><ul class="mt-2">';
                
                patients.forEach(p => {
                    const age = p.age_display ? ` (${p.age_display})` : this.getAgeDisplay(p.date_of_birth);
                    patientListHtml += `<li><strong>${p.name}</strong>${age} - ${p.blood_group || 'Blood group not set'}</li>`;
                });
                
                patientListHtml += '</ul></div>';
                patientListHtml += '<div class="alert alert-warning"><i class="fa fa-exclamation-triangle"></i> If this person is not in the list above, you can create a new patient below.</div>';
                
                $('#existing-patients-list').html(patientListHtml);
                $('#search-result-message').html('<div class="alert alert-success">✓ Found ' + patients.length + ' patient(s) with this phone number</div>');
                
                // Clear the form for new patient entry
                this.state.show_new_patient_form = true;
                this.clearPatientForm();
                $('#patient-phone').val(phone); // Pre-fill phone number
                
            } else {
                // No patients found
                $('#existing-patients-list').html('');
                $('#search-result-message').html(
                    '<div class="alert alert-info">No patient found with this number. You can create a new patient.</div>'
                );
                this.state.show_new_patient_form = true;
                this.clearPatientForm();
                $('#patient-phone').val(phone); // Pre-fill phone number
            }
        } catch (error) {
            console.error("Error searching patient:", error);
            $('#search-result-message').html(
                '<div class="alert alert-danger">Error searching patient. Please try again.</div>'
            );
        }
    }

    // Show patient selection dropdown
    showPatientSelection(patients) {
        let dropdownHtml = '<div id="patient-select-dropdown" class="mt-3 mb-3">';
        dropdownHtml += '<label><strong>Select Patient:</strong></label>';
        dropdownHtml += '<select id="patient-select" class="form-control" t-on-change="selectPatient">';
        dropdownHtml += '<option value="">-- Select Patient --</option>';
        
        patients.forEach(p => {
            const age = p.age_display ? ` (${p.age_display})` : this.getAgeDisplay(p.date_of_birth);
            dropdownHtml += `<option value="${p.id}">${p.name}${age} - ${p.blood_group || 'Blood group not set'}</option>`;
        });
        
        dropdownHtml += '<option value="new">+ Create New Family Member with this phone</option>';
        dropdownHtml += '</select></div>';
        
        $('#search-result-message').html(
            '<div class="alert alert-success">✓ Multiple patients found with this phone number. Please select one.</div>'
        );
        $('#patient-select-dropdown').html(dropdownHtml).show();
    }

    // Select patient from dropdown
    async selectPatient(ev) {
        const selectedValue = ev.target.value;
        
        if (selectedValue === 'new') {
            // Create new family member with same phone
            this.state.selected_patient = null;
            this.state.show_new_patient_form = true;
            this.clearPatientForm();
            $('#patient-phone').val($('#search-phone').val());
            return;
        }
        
        if (!selectedValue) return;

        const patient = this.state.found_patients.find(p => p.id == selectedValue);
        if (patient) {
            this.state.selected_patient = patient;
            this.state.show_new_patient_form = false;
            
            // Auto-fill the form with selected patient details
            $('#patient-name').val(patient.name || '');
            $('#patient-phone').val(patient.phone || '');
            $('#patient-mail').val(patient.email || '');
            $('#patient-dob').val(patient.date_of_birth || '');
            $('#patient-weight').val(patient.weight || '');
            $('#patient-height').val(patient.height || '');
            $('#patient-bloodgroup').val(patient.blood_group || '');

            // Set RH Type
            if (patient.rh_type) {
                $(`input[name='rhtype'][value='${patient.rh_type}']`).prop('checked', true);
            }
            
            // Set Gender
            if (patient.gender) {
                $(`input[name='gender'][value='${patient.gender}']`).prop('checked', true);
            }
            
            // Set Marital Status
            if (patient.marital_status) {
                $('#patient-m-status').val(patient.marital_status);
            }
        }
    }

    // Method for saving patient
    // async savePatient() {
    //     // If a patient is selected from existing ones, use that
    //     if (this.state.selected_patient) {
    //         alert(`Selected patient: ${this.state.selected_patient.name}. You can now create an appointment.`);
    //         // Set the patient in appointment form
    //         $('#sl_patient').val(this.state.selected_patient.id);
    //         this.fetchAppointmentData();
    //         return;
    //     }

    //     // Otherwise create new patient
    //     const data = await this.fetch_patient_data();
    //     if (!data['name'] || !data['phone']) {
    //         alert("Please fill the name and phone");
    //         return;
    //     }

    //     try {
    //         // Handle image upload
    //         const fileInput = $('#patient-img')[0];
    //         if (fileInput.files && fileInput.files[0]) {
    //             const file = fileInput.files[0];
    //             if (file.type.startsWith('image/')) {
    //                 const base64Image = await new Promise((resolve, reject) => {
    //                     const reader = new FileReader();
    //                     reader.onload = (event) => resolve(event.target.result.split(',')[1]);
    //                     reader.onerror = (error) => reject(error);
    //                     reader.readAsDataURL(file);
    //                 });
    //                 data['image_1920'] = base64Image;
    //             }
    //         }

    //         const patientId = await this.orm.call('res.partner', 'create', [[data]]);
    //         this.env.services.notification.add('New patient record has been created', { type: 'success' });
            
    //         // Reset search after creation
    //         this.resetSearch();
            
    //     } catch (error) {
    //         console.error("Error creating patient:", error);
    //         let errorMessage = 'Error creating patient';
    //         if (error.data && error.data.message) {
    //             errorMessage += ': ' + error.data.message;
    //         } else if (error.message) {
    //             errorMessage += ': ' + error.message;
    //         }
    //         this.env.services.notification.add(errorMessage, { type: 'danger' });
    //     }
    // }

    // Method for saving patient
    // async savePatient() {
    //     const data = await this.fetch_patient_data();
    //     if (!data['name'] || !data['phone']) {
    //         alert("Please fill the name and phone");
    //         return;
    //     }

    //     try {
    //         // Handle image upload
    //         const fileInput = $('#patient-img')[0];
    //         if (fileInput.files && fileInput.files[0]) {
    //             const file = fileInput.files[0];
    //             if (file.type.startsWith('image/')) {
    //                 const base64Image = await new Promise((resolve, reject) => {
    //                     const reader = new FileReader();
    //                     reader.onload = (event) => resolve(event.target.result.split(',')[1]);
    //                     reader.onerror = (error) => reject(error);
    //                     reader.readAsDataURL(file);
    //                 });
    //                 data['image_1920'] = base64Image;
    //             }
    //         }

    //         const patientId = await this.orm.call('res.partner', 'create', [[data]]);
    //         this.env.services.notification.add('New patient record has been created', { type: 'success' });
            
    //         // Reset search after creation
    //         this.resetSearch();
            
    //     } catch (error) {
    //         console.error("Error creating patient:", error);
    //         let errorMessage = 'Error creating patient';
    //         if (error.data && error.data.message) {
    //             errorMessage += ': ' + error.data.message;
    //         } else if (error.message) {
    //             errorMessage += ': ' + error.message;
    //         }
    //         this.env.services.notification.add(errorMessage, { type: 'danger' });
    //     }
    // }
async savePatient() {
    const data = await this.fetch_patient_data();

    // 🔴 Basic Required Validation
    if (!data['name'] || !data['phone']) {
        alert("Please fill Name and Phone");
        return;
    }

    // 🔴 DOB Required Validation
    if (!data['date_of_birth']) {
        alert("Date of Birth is required");
        return;
    }

    // 🔴 Gender Required Validation
    if (!data['gender']) {
        alert("Gender is required");
        return;
    }

    try {
        const fileInput = $('#patient-img')[0];
        if (fileInput.files && fileInput.files[0]) {
            const file = fileInput.files[0];
            if (file.type.startsWith('image/')) {
                const base64Image = await new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onload = (event) => resolve(event.target.result.split(',')[1]);
                    reader.onerror = (error) => reject(error);
                    reader.readAsDataURL(file);
                });
                data['image_1920'] = base64Image;
            }
        }

        await this.orm.call('res.partner', 'create', [[data]]);
        this.env.services.notification.add(
            'New patient record has been created',
            { type: 'success' }
        );

        this.resetSearch();

    } catch (error) {
        console.error("Error creating patient:", error);
        this.env.services.notification.add(
            'Error creating patient',
            { type: 'danger' }
        );
    }
}
    // async fetchPatientsByPhone() {
    //     const phone = $('#o_patient-phone').val();

    //     if (!phone) {
    //         $('#sl_patient').html('<option value="">Select Patient</option>');
    //         return;
    //     }

    //     const patients = await this.orm.call(
    //         'res.partner',
    //         'search_read',
    //         [[['phone', '=', phone]]],
    //         { fields: ['id', 'name', 'patient_seq', 'date_of_birth'] }
    //     );

    //     let options = '';

    //     if (patients.length > 0) {

    //         options += '<option value="">Select Patient</option>';

    //         patients.forEach(p => {

    //             let age = '';
    //             if (p.date_of_birth) {
    //                 const dob = new Date(p.date_of_birth);
    //                 const today = new Date();
    //                 let ageYears = today.getFullYear() - dob.getFullYear();
    //                 age = ` (${ageYears} yrs)`;
    //             }

    //             options += `
    //                 <option value="${p.id}">
    //                     ${p.patient_seq || ''} - ${p.name}${age}
    //                 </option>
    //             `;
    //         });

    //     } else {

    //         options = `
    //             <option value="">No Patient Found</option>
    //             <option value="create_new">➕ Create New Patient</option>
    //         `;

    //     }

    //     $('#sl_patient').html(options);
    // }
    async fetchPatientsByPhone() {
        const phone = this.sanitizePhoneNumber();

        if (!phone) {
            $('#sl_patient').html('<option value="">Select Patient</option>');
            return;
        }

        if (phone.length < 10) {
            $('#sl_patient').html('<option value="">Enter 10-digit phone number</option>');
            return;
        }

        const patients = await this.orm.call(
            'res.partner',
            'search_read',
            [[['phone', '=', phone]]],
            { fields: ['id', 'name', 'patient_seq', 'date_of_birth', 'age_display'] }
        );

        let options = '<option value="">Select Patient</option>';

        if (patients.length > 0) {
            // Show existing patients
            patients.forEach(p => {
                const age = p.age_display ? ` (${p.age_display})` : this.getAgeDisplay(p.date_of_birth);
                options += `
                    <option value="${p.id}">
                        ${p.patient_seq || ''} - ${p.name}${age}
                    </option>
                `;
            });
            
            // ✅ ALWAYS show "Create New Patient" option, even when patients exist
            options += `
                <option value="create_new" style="color: green; font-weight: bold;">➕ Create New Patient</option>
            `;
            
            $('#search-result-message').html(
                '<div class="alert alert-info">✓ Found ' + patients.length + ' patient(s). You can select existing or create new.</div>'
            );
        } else {
            // No patients found
            options += `
                <option value="create_new" style="color: green; font-weight: bold;">➕ Create New Patient</option>
            `;
            $('#search-result-message').html(
                '<div class="alert alert-warning">No patient found. Click "Create New Patient" to register.</div>'
            );
        }

        $('#sl_patient').html(options);
    }

    async fetch_patient_data() {
        var patient_name = $('#patient-name').val();
        var patient_phone = $('#patient-phone').val();
        var patient_mail = $('#patient-mail').val();
        var patient_dob = $('#patient-dob').val();
        var patient_bloodgroup = $('#patient-bloodgroup').val();
        var patient_m_status = $('#patient-m-status').val() || '';
        var patient_rhtype = $("input[name='rhtype']:checked").val();
        var patient_gender = $("input[name='gender']:checked").val();
        var patient_height = $('#patient-height').val();
        var patient_weight = $('#patient-weight').val();
        // var patient_bp = $('#patient-bp').val();
        // var patient_temp = $('#temperature').val();
        var data = {
            'name': patient_name,
            'blood_group': patient_bloodgroup,
            'rh_type': patient_rhtype,
            'gender': patient_gender,
            'marital_status': patient_m_status,
            'phone': patient_phone,
            'email': patient_mail,
            'height': patient_height,
            'weight': patient_weight ? parseFloat(patient_weight) : 0,
            // 'bp': patient_bp,
            // 'temperature': patient_temp ? parseFloat(patient_temp) : 0,
        };

        if (patient_dob) {
            data['date_of_birth'] = patient_dob;
        }
        return data;
    }

    // Method on clicking appointment button
    fetchAppointmentData() {

        if ($('.r_active')[0]) {
            $('.r_active')[0].classList.remove('r_active');
        }

        if ($('.o_appointment_button')[0]) {
            $('.o_appointment_button')[0].classList.add('r_active');
        }

        if (this.out_patient.el) {
            this.out_patient.el.classList.remove("d-none");
        }

        if (this.rd_buttons.el) {
            this.rd_buttons.el.classList.remove("d-none");
        }

        this.createOutPatient();
        
        // // ✅ Set current time when opening appointment form
        // setTimeout(() => {
        //     this.setCurrentVisitTime();
        // }, 100);
    }

    // Creates new outpatient
    // async createOutPatient (){
    //     var self = this;
    //     const date = new Date();
    //     var formattedCurrentDate = date.toISOString().split('T')[0];
    //     const result = await this.orm.call('res.partner','fetch_patient_data',[],)
    //     this.state.patient_lst = result
    //     self.patient_lst=result
    //     $('.select_patient').html('<option value="">Select Patient</option>');
    //     self.patient_lst.forEach(element => {
    //         $('.select_patient').append(`
    //             <option value="${element['id']}">${element.patient_seq}-${element.name}</option>
    //         `)
    //     })
    //    await this.orm.call('doctor.allocation','search_read',[]
    //    ).then(function (result){
    //     self.dr_lst=result
    //     $('.select_dr').html('')
    //     self.dr_lst.forEach(element => {
    //         $('.select_dr').append(`
    //             <option value="${element['id']}">${element.display_name}</option>
    //         `)
    //     })
    //        }),
    //        $('#controls').html(``);
    //         var currentDate = new Date();
    //         $('#op_date').val(currentDate.toISOString().split('T')[0])
    //         const now = new Date();
    //         $('#op_visit_time').val(now.toISOString().slice(0,16));
    // }

    // async createOutPatient (){
    //     var self = this;

    //     const result = await this.orm.call('res.partner','fetch_patient_data',[],)
    //     this.state.patient_lst = result

    //     $('.select_patient').html('<option value="">Select Patient</option>');
    //     result.forEach(element => {
    //         $('.select_patient').append(`
    //             <option value="${element.id}">${element.patient_seq}-${element.name}</option>
    //         `)
    //     })

    //     const drs = await this.orm.call('doctor.allocation','search_read',[])
    //     $('.select_dr').html('')
    //     drs.forEach(element => {
    //         $('.select_dr').append(`
    //             <option value="${element.id}">${element.display_name}</option>
    //         `)
    //     })

    //     var currentDate = new Date();
    //     $('#op_date').val(currentDate.toISOString().split('T')[0])

    //     // ⭐ VERY IMPORTANT FIX
    //     // if (!$('#op_visit_time').val()){
    //     //     const now = new Date();
    //     //     $('#op_visit_time').val(now.toISOString().slice(0,16));
    //     // }
    //     // 'visit_time': $('#op_visit_time').val()
    // }
    // async createOutPatient() {
    //     var self = this;

    //     const result = await this.orm.call('res.partner', 'fetch_patient_data', [],);
    //     this.state.patient_lst = result

    //     $('.select_patient').html('<option value="">Select Patient</option>');
    //     result.forEach(element => {
    //         $('.select_patient').append(`
    //             <option value="${element.id}">${element.patient_seq}-${element.name}</option>
    //         `)
    //     })

    //     const drs = await this.orm.call('doctor.allocation', 'search_read', []);
    //     $('.select_dr').html('');
    //     drs.forEach(element => {
    //         $('.select_dr').append(`
    //             <option value="${element.id}">${element.display_name}</option>
    //         `)
    //     })

    //     // var currentDate = new Date();
    //     // $('#op_date').val(currentDate.toISOString().split('T')[0]);

    //     // // ✅ Set current time in visit time field
    //     // this.setCurrentVisitTime();
    //     var currentDate = new Date();
    //     $('#op_date').val(this.formatDateToDMY(currentDate));
    //     $('#op_date').attr('data-iso', currentDate.toISOString().split('T')[0]);

    //     // Initialize flatpickr if not already done
    //     if (!this.datePicker) {
    //         this.initDatePicker();
    //     } else {
    //         this.datePicker.setDate(currentDate);
    //     }
    // }
    async createOutPatient() {
        var self = this;
        if (!this.state.currentCompanyId) {
            this.state.currentCompanyId = await this.orm.call('res.users', 'get_current_company_id', []);
        }

        const result = await this.orm.call('res.partner', 'fetch_patient_data', [],);
        this.state.patient_lst = result

        $('.select_patient').html('<option value="">Select Patient</option>');
        result.forEach(element => {
            $('.select_patient').append(`
                <option value="${element.id}">${element.patient_seq}-${element.name}</option>
            `)
        })

        const drs = await this.orm.call('doctor.allocation', 'get_reception_allocations', []);
        $('.select_dr').html('');
        drs.forEach(element => {
            $('.select_dr').append(`
                <option value="${element.id}">${element.display_name}</option>
            `)
        })

        // Set OP Date
        var currentDate = new Date();
        $('#op_date').val(this.formatDateToDMY(currentDate));
        $('#op_date').attr('data-iso', currentDate.toISOString().split('T')[0]);
        if (!this.datePicker) {
            this.initDatePicker();
        } else {
            this.datePicker.setDate(currentDate);
        }

        // Initialize Date of Birth picker (no default value)
        if (!this.datePickerDOB) {
            this.initDOBPicker();
        }

        // const now = new Date();
        // // Format to dd/mm/yyyy hh:MM AM/PM
        // const options = { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: true };
        // const formattedDateTime = now.toLocaleString('en-GB', options).replace(',', ''); // e.g., "05/04/2026 03:45 PM"
        // $('#op_visit_time').val(formattedDateTime);
        // $('#op_visit_time').attr('data-iso', now.toISOString().slice(0,16));
        // if (!this.dateTimePicker) {
        //     this.initVisitTimePicker();
        // } else {
        //     this.dateTimePicker.setDate(now);
        // }
        // Set Visit Time to current local time
        const now = new Date();
        if (!this.dateTimePicker) {
            const success = this.initVisitTimePicker();
            if (success && this.dateTimePicker) {
                this.dateTimePicker.setDate(now);
            } else {
                // Fallback: manually set current time and combine with OP date for storage
                const formatted = this.formatTimeToDisplay(now);
                $('#op_visit_time').val(formatted);
                const opDateIso = this.normalizeOpDateInput();
                const iso = `${opDateIso}T${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
                $('#op_visit_time').attr('data-iso', iso);
            }
        } else {
            this.dateTimePicker.setDate(now);
        }
    }
    // Method for creating inpatient
    async createInPatient (){
        var self = this
        this.room_ward.el.classList.add("d-none")
        this.patient_creation.el.classList.add("d-none");
        this.out_patient.el.classList.add("d-none");
        this.inpatient.el.classList.remove("d-none");
        this.ward.el.classList.add("d-none");
        this.room.el.classList.add("d-none");
        await this.orm.call('res.partner','fetch_patient_data',[]).then(function (result){
        self.patient_id_lst=result
        $('.select_patient_id').html('')
            self.patient_id_lst.forEach(element => {
                $('.select_patient_id').append(`
                    <option value="${element['id']}">${element.patient_seq}-${element.name}</option>
                `)
            })
        }),
        await this.orm.call('hr.employee', 'get_company_doctors', [])
        .then(function (result){
            self.attending_dr_lst=result
            $('.attending_doctor_id').html('')
            self.attending_dr_lst.forEach(element => {
                $('.attending_doctor_id').append(`
                    <option value="${element['id']}">${element.display_name}</option>
                `)
            })
        })
    }

    // Method for saving outpatient
    // async save_out_patient_data () {

    //     var self = this;
    //     var data = await self.fetch_out_patient_data();

    //     if (data != false) {

    //         try {

    //             var result = await this.orm.call('res.partner', 'create_patient', [data]);

    //             if (result && result.success) {

    //                 alert(result.message || 'Outpatient created successfully');

    //                 // Clear form
    //                 $('#o_patient-name').val("");
    //                 $('#sl_patient').val("");
    //                 $('#o_patient-phone').val("");
    //                 $('#o_patient-dob').val("");
    //                 $('#reason').val("");
    //                 $('#slot').val("");
    //                 $('#sl_dr').val("");

    //                 this.action.doAction({
    //                     type: 'ir.actions.act_window',
    //                     name: 'Outpatient List',
    //                     res_model: 'hospital.outpatient',
    //                     view_mode: 'tree,form',
    //                     views: [[false, 'tree'], [false, 'form']],
    //                     target: 'current',
    //                 });

    //             } else {
    //                 alert(result?.message || 'Failed to create outpatient');
    //             }

    //         } catch (error) {

    //             console.error("Error creating outpatient:", error);

    //             let msg = "Error creating outpatient";

    //             if (error.data && error.data.message) {
    //                 msg = error.data.message;
    //             }

    //             if (error.data && error.data.arguments && error.data.arguments.length) {
    //                 msg = error.data.arguments[0];
    //             }

    //             alert(msg);
    //         }
    //     }
    // }
    // Initialize the mini donut chart - Shows Follow-ups vs New Patients
    initMiniDonutChart() {
        const canvas = document.getElementById('miniFollowupDonutChart');
        if (!canvas) {
            setTimeout(() => this.initMiniDonutChart(), 500);
            return;
        }
        
        const ctx = canvas.getContext('2d');
        
        // Data: Follow-ups (Orange) vs New Patients (Green)
        const data = {
            datasets: [{
                data: [this.state.today_followups, this.state.today_new_patients],
                backgroundColor: ['#ff9800', '#2ecc71'],  // Orange for Follow-ups, Green for New Patients
                borderWidth: 0,
            }]
        };
        
        const total = this.state.today_followups + this.state.today_new_patients;
        
        const options = {
            responsive: true,
            maintainAspectRatio: true,
            cutout: '65%',
            plugins: {
                legend: { display: false },
                tooltip: { 
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.raw || 0;
                            const percentage = ((value / total) * 100).toFixed(1);
                            if (context.dataIndex === 0) {
                                return `Follow-ups: ${value} (${percentage}%)`;
                            } else {
                                return `New Patients: ${value} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        };
        
        if (window.miniFollowupChart) {
            window.miniFollowupChart.destroy();
        }
        window.miniFollowupChart = new Chart(ctx, {
            type: 'doughnut',
            data: data,
            options: options
        });
    }
    // Method for saving outpatient
    async save_out_patient_data () {

        var self = this;
        var data = await self.fetch_out_patient_data();

        if (data != false) {

            try {

                var result = await this.orm.call(
                    'res.partner',
                    'create_patient',
                    [data]
                );

                if (result && result.success) {

                    alert(result.message || 'Outpatient created successfully');
                    await this.refreshStatistics();

                    // ⭐⭐⭐ VERY IMPORTANT PART (NEW CUSTOMIZATION)
                    if (result.patient_id){

                        const patients = await this.orm.call(
                            'res.partner',
                            'fetch_patient_data',
                            []
                        );

                        let options = '<option value="">Select Patient</option>';

                        patients.forEach(p => {
                            options += `
                                <option value="${p.id}">
                                    ${p.patient_seq}-${p.name}
                                </option>
                            `;
                        });

                        $('#sl_patient').html(options);

                        // ⭐ auto select newly created patient
                        $('#sl_patient').val(result.patient_id);

                        // ⭐ auto fetch patient details
                        await this.fetch_patient_id();
                    }

                    // ⭐ Clear OP form fields
                    $('#o_patient-name').val("");
                    $('#o_patient-phone').val("");
                    $('#o_patient-dob').val("");
                    $('#reason').val("");
                    $('#slot').val("");
                    $('#sl_dr').val("");

                    // ⭐ Open OP list
                    this.action.doAction({
                        type: 'ir.actions.act_window',
                        name: 'Outpatient List',
                        res_model: 'hospital.outpatient',
                        view_mode: 'tree,form',
                        views: [[false, 'tree'], [false, 'form']],
                        target: 'current',
                    });

                } else {
                    alert(result?.message || 'Failed to create outpatient');
                }

            } catch (error) {

                console.error("Error creating outpatient:", error);

                let msg = "Error creating outpatient";

                if (error.data && error.data.message) {
                    msg = error.data.message;
                }

                if (error.data && error.data.arguments && error.data.arguments.length) {
                    msg = error.data.arguments[0];
                }

                alert(msg);
            }
        }
    }

    // Method for displaying patient card
    patient_card () {
        if($('#select_type').val() === 'dont_have_card'){
            $('#sl_patient').hide();
            $('#patient_label').hide();
        }
        else{
            $('#sl_patient').show();
            $('#patient_label').show();
        }
    }

    // Helper function to validate and format phone number
    sanitizePhoneNumber() {
        const input = $('#o_patient-phone');
        const cleaned = (input.val() || '').replace(/\D/g, '').slice(0, 10);
        input.val(cleaned);
        return cleaned;
    }

    getAgeDisplay(dateOfBirth) {
        if (!dateOfBirth) return '';

        const dob = new Date(dateOfBirth);
        const today = new Date();
        if (Number.isNaN(dob.getTime()) || dob > today) return '';

        let years = today.getFullYear() - dob.getFullYear();
        let months = today.getMonth() - dob.getMonth();

        if (today.getDate() < dob.getDate()) {
            months -= 1;
        }
        if (months < 0) {
            years -= 1;
            months += 12;
        }

        return ` (${years} yrs ${months} months)`;
    }

    validatePhoneNumber(phone) {
        if (!phone) return '';
        
        // Remove all non-digit characters
        let cleaned = phone.replace(/\D/g, '');
        
        // Check if it's exactly 10 digits
        if (cleaned.length === 10) {
            return cleaned;
        } else if (cleaned.length > 10) {
            alert('Phone number cannot exceed 10 digits');
            return cleaned.substring(0, 10);
        } else if (cleaned.length > 0 && cleaned.length < 10) {
            alert('Phone number must be exactly 10 digits');
            return cleaned;
        }
        return cleaned;
    }
    async fetch_out_patient_data () {
        var o_patient_name = $('#o_patient-name').val();
        var o_patient_phone = $('#o_patient-phone').val();
        // var o_patient_dob = $('#o_patient-dob').val();
        var o_patient_dob = $('#o_patient-dob').data('iso') || $('#o_patient-dob').val();
        var o_patient_blood_group = $("#o_patient_bloodgroup").val();
        var o_patient_rhtype = $("input[id='o_rhtype']:checked").val();
        var o_patient_gender = $("input[name='gender']:checked").val();
        var patient_id = $('#sl_patient').val();
        var op_date = this.normalizeOpDateInput();
        var habit_history = $('#habit_history').val();
        var reason = $('#reason').val();
        var ticket_no = $('#slot').val();
        var doctor = $('#sl_dr').val();
        var op_bp = $('#op_bp').val();
        var op_temperature = $('#op_temperature').val();
        var op_pulse = $('#op_pulse').val();
        var op_spo2 = $('#op_spo2').val();
        // var op_visit_time = $('#op_visit_time').val();
        var op_visit_time = this.normalizeVisitTimeInput(op_date);
        
        console.log("VISIT TIME FROM INPUT:", op_visit_time);

        // ✅ Phone Number Validation - Must be exactly 10 digits
        if (o_patient_phone && o_patient_phone.trim()) {
            // Remove any non-digit characters for validation
            const phoneDigits = o_patient_phone.replace(/\D/g, '');
            if (phoneDigits.length !== 10) {
                alert('Phone number must be exactly 10 digits. Please enter a valid 10-digit mobile number.');
                return false;
            }
            // Update the phone number with only digits
            o_patient_phone = phoneDigits;
            $('#o_patient-phone').val(phoneDigits);
        }
        
        // Keep the selected time, but always align its date with the chosen OP date.
        this.syncVisitTimeWithOpDate();
        op_visit_time = this.normalizeVisitTimeInput(op_date);
        
        if (o_patient_name === '' || doctor === '' || op_date === '') {
            alert('Please fill out all the required fields: Name, Doctor, and Date.');
            return false;
        } else {
            var data = {
                'op_name': o_patient_name,
                'op_phone': o_patient_phone,
                'op_blood_group': o_patient_blood_group,
                'op_rh': o_patient_rhtype,
                'op_gender': o_patient_gender,
                'patient_id': patient_id,
                'date': op_date,
                'habit_history': habit_history,
                'reason': reason,
                'slot': ticket_no ? parseInt(ticket_no) : 0,
                'doctor': doctor,
                'bp': op_bp || '',
                'temperature': op_temperature ? parseFloat(op_temperature) : 0,
                'pulse': op_pulse ? parseInt(op_pulse) : 0,
                'spo2': op_spo2 ? parseInt(op_spo2) : 0,
                'visit_time': op_visit_time,  // Send as received from datetime-local
            };

            if (o_patient_dob) {
                data['op_dob'] = o_patient_dob;
            }

            console.log("SENDING VISIT TIME:", data.visit_time);
            return data;
        }
    }

    // Method for fetching inpatient data
    async fetch_in_patient_data (){
        var patient_id = $('#sl_patient_id').val();
        var reason_of_admission = $('#reason_of_admission').val();
        var admission_type = $('#admission_type').val();
        var attending_doctor_id = $('#attending_doctor_id').val();
        if (patient_id === null || attending_doctor_id === null ||
        admission_type === null) {
            alert('Please fill out all the required fields.');
            return false;
        }
        else{
            var data = {
                'patient_id' : patient_id,
                'reason_of_admission' : reason_of_admission,
                'admission_type' : admission_type,
                'attending_doctor_id' : attending_doctor_id,
            }
            return data
        }
    }

    // Method for creating new inpatient
    async save_in_patient_data (){
        var data = await this.fetch_in_patient_data()
        if (data != false || data != null || data != undefined){
            this.orm.call('hospital.inpatient','create_new_in_patient',[null,data]
            ).then(function (){
                alert('Inpatient is created');
                  $('#sl_patient_id').val("");
                  $('#reason_of_admission').val("");
                  $('#admission_type').val("");
                  $('#attending_doctor_id').val("");
        });
        }
    }
    // Initialize date picker with dd/mm/yyyy format
    initDatePicker() {
        const dateInput = document.getElementById('op_date');
        if (dateInput && typeof flatpickr !== 'undefined') {
            this.datePicker = flatpickr(dateInput, {
                dateFormat: "d/m/Y",
                allowInput: true,
                onChange: (selectedDates, dateStr) => {
                    if (selectedDates.length) {
                        // Store ISO format in a data attribute for backend
                        const d = selectedDates[0];
                        const year = d.getFullYear();
                        const month = String(d.getMonth() + 1).padStart(2, '0');
                        const day = String(d.getDate()).padStart(2, '0');
                        dateInput.setAttribute('data-iso', `${year}-${month}-${day}`);
                        this.syncVisitTimeWithOpDate();
                    } else {
                        dateInput.removeAttribute('data-iso');
                    }
                }
            });
        }
    }

    // Format a Date object to dd/mm/yyyy
    formatDateToDMY(date) {
        const day = String(date.getDate()).padStart(2, '0');
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const year = date.getFullYear();
        return `${day}/${month}/${year}`;
    }
    // Initialize Date of Birth picker with dd/mm/yyyy
    initDOBPicker() {
        const dobInput = document.getElementById('o_patient-dob');
        if (dobInput && typeof flatpickr !== 'undefined') {
            this.datePickerDOB = flatpickr(dobInput, {
                dateFormat: "d/m/Y",
                allowInput: true,
                onChange: (selectedDates, dateStr) => {
                    if (selectedDates.length) {
                        const d = selectedDates[0];
                        const year = d.getFullYear();
                        const month = String(d.getMonth() + 1).padStart(2, '0');
                        const day = String(d.getDate()).padStart(2, '0');
                        dobInput.setAttribute('data-iso', `${year}-${month}-${day}`);
                    } else {
                        dobInput.removeAttribute('data-iso');
                    }
                }
            });
        }
    }

 

    // initVisitTimePicker() {
    //     const timeInput = document.getElementById('op_visit_time');
    //     if (timeInput && typeof flatpickr !== 'undefined') {
    //         this.dateTimePicker = flatpickr(timeInput, {
    //             dateFormat: "d/m/Y h:i K",        // 12-hour format with AM/PM
    //             enableTime: true,
    //             time_24hr: false,                 // use 12-hour clock
    //             allowInput: true,
    //             onChange: (selectedDates, dateStr) => {
    //                 if (selectedDates.length) {
    //                     const d = selectedDates[0];
    //                     const year = d.getFullYear();
    //                     const month = String(d.getMonth() + 1).padStart(2, '0');
    //                     const day = String(d.getDate()).padStart(2, '0');
    //                     const hours = String(d.getHours()).padStart(2, '0');
    //                     const minutes = String(d.getMinutes()).padStart(2, '0');
    //                     timeInput.setAttribute('data-iso', `${year}-${month}-${day}T${hours}:${minutes}`);
    //                 } else {
    //                     timeInput.removeAttribute('data-iso');
    //                 }
    //             }
    //         });
    //     }
    // }

    initVisitTimePicker() {
        const timeInput = document.getElementById('op_visit_time');
        if (timeInput && typeof flatpickr !== 'undefined') {
            this.dateTimePicker = flatpickr(timeInput, {
                dateFormat: "d/m/Y h:i K",      // 12‑hour display
                enableTime: true,
                time_24hr: false,
                allowInput: true,
                onChange: (selectedDates, dateStr) => {
                    if (selectedDates.length) {
                        const d = selectedDates[0];
                        const year = d.getFullYear();
                        const month = String(d.getMonth() + 1).padStart(2, '0');
                        const day = String(d.getDate()).padStart(2, '0');
                        const hours = String(d.getHours()).padStart(2, '0');
                        const minutes = String(d.getMinutes()).padStart(2, '0');
                        timeInput.setAttribute('data-iso', `${year}-${month}-${day}T${hours}:${minutes}`);
                    } else {
                        timeInput.removeAttribute('data-iso');
                    }
                }
            });
            return true;
        }
        console.warn("Visit Time input not found or flatpickr missing");
        return false;
    }


    // Format datetime to dd/mm/yyyy HH:MM
    formatDateTimeToDMYHM(date) {
        const day = String(date.getDate()).padStart(2, '0');
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const year = date.getFullYear();
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        return `${day}/${month}/${year} ${hours}:${minutes}`;
    }

    syncVisitTimeWithOpDate() {
        const opDateIso = this.normalizeOpDateInput();
        const visitTimeIso = this.normalizeVisitTimeInput(opDateIso);

        if (!opDateIso || !visitTimeIso) {
            return;
        }

        let timePart = '00:00';
        if (visitTimeIso.includes('T')) {
            timePart = visitTimeIso.split('T')[1].slice(0, 5);
        } else {
            const parsedVisit = new Date(visitTimeIso);
            if (!Number.isNaN(parsedVisit.getTime())) {
                timePart = `${String(parsedVisit.getHours()).padStart(2, '0')}:${String(parsedVisit.getMinutes()).padStart(2, '0')}`;
            }
        }

        const syncedIso = `${opDateIso}T${timePart}`;
        $('#op_visit_time').attr('data-iso', syncedIso);

        if (this.dateTimePicker) {
            this.dateTimePicker.setDate(syncedIso, true);
        } else {
            const syncedDate = new Date(`${syncedIso}:00`);
            if (!Number.isNaN(syncedDate.getTime())) {
                $('#op_visit_time').val(this.formatDateTimeToDMYHM(syncedDate));
            }
        }
    }

    normalizeOpDateInput() {
        const visibleValue = ($('#op_date').val() || '').trim();
        const isoValue = ($('#op_date').data('iso') || '').trim();

        const displayMatch = visibleValue.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
        if (displayMatch) {
            const [, day, month, year] = displayMatch;
            const normalized = `${year}-${month}-${day}`;
            $('#op_date').attr('data-iso', normalized);
            return normalized;
        }

        return isoValue || visibleValue;
    }

    normalizeVisitTimeInput(opDateIso = null) {
        const visibleValue = ($('#op_visit_time').val() || '').trim();
        const isoValue = ($('#op_visit_time').data('iso') || '').trim();
        const normalizedOpDate = opDateIso || this.normalizeOpDateInput();

        const displayMatch = visibleValue.match(/^(\d{2})\/(\d{2})\/(\d{4})\s+(\d{1,2}):(\d{2})(?:\s*([APap][Mm]))?$/);
        if (displayMatch) {
            let [, day, month, year, hours, minutes, meridiem] = displayMatch;
            let hourNumber = parseInt(hours, 10);

            if (meridiem) {
                const upperMeridiem = meridiem.toUpperCase();
                if (upperMeridiem === 'PM' && hourNumber < 12) {
                    hourNumber += 12;
                }
                if (upperMeridiem === 'AM' && hourNumber === 12) {
                    hourNumber = 0;
                }
            }

            const normalized = `${year}-${month}-${day}T${String(hourNumber).padStart(2, '0')}:${minutes}`;
            $('#op_visit_time').attr('data-iso', normalized);
            return normalizedOpDate ? `${normalizedOpDate}T${String(hourNumber).padStart(2, '0')}:${minutes}` : normalized;
        }

        if (isoValue && normalizedOpDate && isoValue.includes('T')) {
            const timePart = isoValue.split('T')[1].slice(0, 5);
            return `${normalizedOpDate}T${timePart}`;
        }

        return isoValue || visibleValue;
    }

    initVisitTimePicker() {
        const timeInput = document.getElementById('op_visit_time');
        if (timeInput && typeof flatpickr !== 'undefined') {
            this.dateTimePicker = flatpickr(timeInput, {
                dateFormat: "h:i K",
                enableTime: true,
                time_24hr: false,
                noCalendar: true,
                allowInput: true,
                defaultDate: new Date(),
                onChange: (selectedDates) => {
                    if (selectedDates.length) {
                        const d = selectedDates[0];
                        const opDateIso = this.normalizeOpDateInput();
                        const hours = String(d.getHours()).padStart(2, '0');
                        const minutes = String(d.getMinutes()).padStart(2, '0');
                        if (opDateIso) {
                            timeInput.setAttribute('data-iso', `${opDateIso}T${hours}:${minutes}`);
                        }
                    } else {
                        timeInput.removeAttribute('data-iso');
                    }
                }
            });
            return true;
        }
        console.warn("Visit Time input not found or flatpickr missing");
        return false;
    }

    formatTimeToDisplay(date) {
        let hours = date.getHours();
        const minutes = String(date.getMinutes()).padStart(2, '0');
        const meridiem = hours >= 12 ? 'PM' : 'AM';
        hours = hours % 12 || 12;
        return `${String(hours).padStart(2, '0')}:${minutes} ${meridiem}`;
    }

    syncVisitTimeWithOpDate() {
        const opDateIso = this.normalizeOpDateInput();
        const visitTimeIso = this.normalizeVisitTimeInput(opDateIso);

        if (!opDateIso || !visitTimeIso) {
            return;
        }

        const timePart = visitTimeIso.includes('T')
            ? visitTimeIso.split('T')[1].slice(0, 5)
            : visitTimeIso;

        const syncedIso = `${opDateIso}T${timePart}`;
        $('#op_visit_time').attr('data-iso', syncedIso);

        if (this.dateTimePicker) {
            this.dateTimePicker.setDate(`2000-01-01T${timePart}:00`, true);
        } else {
            const syncedDate = new Date(`${syncedIso}:00`);
            if (!Number.isNaN(syncedDate.getTime())) {
                $('#op_visit_time').val(this.formatTimeToDisplay(syncedDate));
            }
        }
    }

    normalizeVisitTimeInput(opDateIso = null) {
        const visibleValue = ($('#op_visit_time').val() || '').trim();
        const isoValue = ($('#op_visit_time').data('iso') || '').trim();
        const normalizedOpDate = opDateIso || this.normalizeOpDateInput();

        const displayMatch = visibleValue.match(/^(\d{1,2}):(\d{2})(?:\s*([APap][Mm]))?$/);
        if (displayMatch) {
            let [, hours, minutes, meridiem] = displayMatch;
            let hourNumber = parseInt(hours, 10);

            if (meridiem) {
                const upperMeridiem = meridiem.toUpperCase();
                if (upperMeridiem === 'PM' && hourNumber < 12) {
                    hourNumber += 12;
                }
                if (upperMeridiem === 'AM' && hourNumber === 12) {
                    hourNumber = 0;
                }
            }

            const normalized = `${normalizedOpDate}T${String(hourNumber).padStart(2, '0')}:${minutes}`;
            $('#op_visit_time').attr('data-iso', normalized);
            return normalized;
        }

        if (isoValue && normalizedOpDate && isoValue.includes('T')) {
            const timePart = isoValue.split('T')[1].slice(0, 5);
            return `${normalizedOpDate}T${timePart}`;
        }

        return isoValue || visibleValue;
    }

    // Convert ISO date (YYYY-MM-DD) to DD/MM/YYYY
    formatISOToDMY(isoDate) {
        if (!isoDate) return '';
        const [year, month, day] = isoDate.split('-');
        return `${day}/${month}/${year}`;
    }

    // Method for getting room or ward details
    fetchRoomWard (){
        $('#view_secondary').html('');
        this.room_ward.el.classList.remove("d-none")
        this.patient_creation.el.classList.add("d-none");
        this.out_patient.el.classList.add("d-none");
        this.inpatient.el.classList.add("d-none");
        this.rd_buttons.el.classList.add("d-none");
        if ($('.r_active')[0]){$('.r_active')[0].classList.remove('r_active');}
        $('.o_room_ward_button')[0].classList.add('r_active');
    }

    // Method for getting ward details
    async fetchWard (){
        this.ward.el.classList.remove("d-none");
        this.room.el.classList.add("d-none");
        if ($('.r_active2')[0]){$('.r_active2')[0].classList.remove('r_active2');}
        $('.o_ward_button')[0].classList.add('r_active2');
        var result = await this.orm.call('hospital.ward','search_read',)
        this.state.ward_data = result
    }

    // Method for getting room details
    async fetchRoom (){
        this.room.el.classList.remove("d-none");
        this.ward.el.classList.add("d-none");
        if ($('.r_active2')[0]){$('.r_active2')[0].classList.remove('r_active2');}
        $('.o_room_button')[0].classList.add('r_active2');
        var result= await this.orm.call('patient.room','search_read',)
        this.state.room_data = result
    }
}

ReceptionDashBoard.template = "ReceptionDashboard"
registry.category('actions').add('reception_dashboard_tags', ReceptionDashBoard);
