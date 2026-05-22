/** @odoo-module */
import { registry } from '@web/core/registry';
import { useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
const { Component, onWillStart, useState } = owl;
import { PharmacyOrderLines } from "./pharmacy_orderlines";

export class PharmacyDashboard extends Component {
    getErrorMessage(error, fallbackMessage) {
        return (
            error?.data?.data?.arguments?.[0] ||
            error?.data?.arguments?.[0] ||
            error?.data?.data?.message ||
            error?.data?.message ||
            error?.message ||
            error?.cause?.message ||
            fallbackMessage
        );
    }

    formatDobForDisplay(dobValue) {
        if (!dobValue) {
            return '';
        }
        if (typeof dobValue === "string" && dobValue.includes('/')) {
            return dobValue;
        }
        const parts = String(dobValue).split('-');
        if (parts.length === 3) {
            return `${parts[2]}/${parts[1]}/${parts[0]}`;
        }
        return String(dobValue);
    }

    formatDobForServer(dobValue) {
        if (!dobValue) {
            return false;
        }
        if (typeof dobValue === "string" && dobValue.includes('-')) {
            return dobValue;
        }
        const parts = String(dobValue).split('/');
        if (parts.length === 3) {
            const [day, month, year] = parts;
            if (day && month && year) {
                return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
            }
        }
        return dobValue;
    }

    setup() {
        super.setup(...arguments);
        
        // Refs
        this.ref = useRef('root');
        this.vaccine_div = useRef('vaccine_div');
        this.medicine_div = useRef('medicine_div');
        this.home_content = useRef('home_content');
        this.orders_div = useRef('orders_div');
        this.prescriptions_div = useRef('prescriptions_div');
        this.patient_name = useRef('PatientName');
        this.patient_email = useRef('Email');
        this.patient_search = useRef('PatientSearch');
        
        // Services
        this.orm = useService('orm');
        this.user = useService("user");
        this.actionService = useService("action");
        
        // State
        this.state = useState({
            product_lst: [],
            med: [],
            filtered_med: [],
            units: [],
            sub_total: 0,
            vaccine: [],
            order_data: [],
            prescription_data: [],
            order_line: [],
            menu: 'home',
            patient_search_results: [],
        });

        // Initial data loading
        this.fetch_product();
        onWillStart(async () => {
            this.state.med = await this.orm.call('product.template', 'action_get_medicine_data', []);
            this.state.filtered_med = this.state.med || [];
        });
    }

    async fetch_product() {
        this.state.product_lst = await this.orm.call(
            'product.template',
            'action_get_medicine_data',
            []
        );
        this.create_order();
    }

    async create_order() {
        this.state.menu = 'home';
        this.updateVisibility();
        
        await this.orm.call('hospital.pharmacy', 'company_currency').then(function(result) {
            $('#symbol').text(result || '');
        });
        
        this.state.medicines = this.state.product_lst;
        this.state.units = [];
    }

    updateVisibility() {
        this.vaccine_div?.el?.classList.add("d-none");
        this.medicine_div?.el?.classList.add("d-none");
        this.home_content?.el?.classList.add("d-none");
        this.orders_div?.el?.classList.add("d-none");
        this.prescriptions_div?.el?.classList.add("d-none");

        switch(this.state.menu) {
            case 'home':
                this.home_content?.el?.classList.remove("d-none");
                break;
            case 'medicines':
                this.medicine_div?.el?.classList.remove("d-none");
                break;
            case 'vaccines':
                this.vaccine_div?.el?.classList.remove("d-none");
                break;
            case 'orders':
                this.orders_div?.el?.classList.remove("d-none");
                break;
            case 'prescriptions':
                this.prescriptions_div?.el?.classList.remove("d-none");
                break;
        }
    }

    updateOrderLine(line, id) {
        const orderline = this.state.order_line.find(orderline => orderline.id === id);
        if (orderline) {
            orderline.product = line.product;
            orderline.qty = parseInt(line.qty);
            orderline.uom = line.uom;
            orderline.price = line.price;
            orderline.sub_total = line.sub_total;
        }
    }

    addRow() {
        this.state.order_line = [
            ...this.state.order_line, 
            owl.reactive({
                id: new Date().getTime(),
                product: false,
                qty: 1,
                uom: 0,
                uom_count: 1,
                price: 0,
                sub_total: 0
            })
        ];
    }

    removeLine(id) {
        this.state.order_line = this.state.order_line.filter(line => line.id !== id);
    }

    async create_sale_order() {
        var data = {};
        data['name'] = $('#patient-name').val();
        data['phone'] = $('#patient-phone').val();
        data['email'] = $('#patient-mail').val();
        data['dob'] = this.formatDobForServer($('#patient-dob').val());
        data['gender'] = $('input[name="gender"]:checked').val() || false;
        data['products'] = this.state.order_line;
        let hasInvalidQuantity = false;
        if (hasInvalidQuantity) {
            alert('Medicine quantity must be greater than or equal to 1.');
            return;
        }
        if (this.patient_name.el.value === "") {
            alert("Please enter the Name");
            return;
        }
        if (this.patient_email.el.value === "") {
            alert("Please enter the Email");
            return;
        }
        this.orm.call('hospital.pharmacy', 'create_sale_order', [data]).then(function(result) {
            alert('The sale order has been created with reference number ' + result.invoice);
            window.location.reload();
        }).catch((error) => {
            console.error("Failed to create sale order:", error);
            alert(this.getErrorMessage(error, "Failed to create sale order. Please try again."));
        });
    }

    // async fetch_patient_data() {
    //     try {
    //         const result = await this.orm.call(
    //             'res.partner',
    //             'action_get_patient_data',
    //             [[this.patient_search.el.value]]
    //         );
            
    //         // Clear existing form and profile data
    //         $('#patient-name').val('');
    //         $('#patient-phone').val('');
    //         $('#patient-mail').val('');
    //         $('#patient-dob').val('');
    //         $('input[name="gender"]').prop('checked', false);
    //         $('#patient-title').text('');
    //         $('#patient-code').text('');
    //         $('#patient-age').text('');
    //         $('#patient-blood').text('');
    //         $('#patient-gender').text('');
    //         $('#hist_head').html('');
    //         $('#patient-image').attr('src', 'https://cdn.pixabay.com/photo/2015/10/05/22/37/blank-profile-picture-973460_1280.png');

    //         if (result.name === 'Patient Not Found') {
    //             $('#hist_head').html('');
    //             $('#patient-image').attr('src', 'https://cdn.pixabay.com/photo/2015/10/05/22/37/blank-profile-picture-973460_1280.png');
    //         } else {
    //             // Update patient profile
    //             $('#patient-title').text(result.name || '');
    //             $('#patient-code').text(result.unique || '');
    //             $('#patient-age').text(result.dob || '');
    //             $('#patient-blood').text(result.blood_group || '');
    //             $('#patient-gender').text(result.gender || '');
    //             if (result.image_1920) {
    //                 $('#patient-image').attr('src', `data:image/png;base64,${result.image_1920}`);
    //             }

    //             // Update sale order form fields
    //             $('#patient-name').val(result.name || '');
    //             $('#patient-phone').val(result.phone || '');
    //             $('#patient-mail').val(result.email || '');
    //             $('#patient-dob').val(result.dob || ''); // Changed from result.date_of_birth to result.dob
    //             if (result.gender) {
    //                 // Try lowercase and capitalized values for radio buttons
    //                 let genderValue = result.gender.toLowerCase();
    //                 if ($(`input[name="gender"][value="${genderValue}"]`).length) {
    //                     $(`input[name="gender"][value="${genderValue}"]`).prop('checked', true);
    //                 } else {
    //                     // Fallback to capitalized value
    //                     $(`input[name="gender"][value="${result.gender}"]`).prop('checked', true);
    //                 }
    //             }
    //         }
    //     } catch (error) {
    //         console.error("Failed to fetch patient data:", error);
    //         alert("Failed to fetch patient data. Please try again.");
    //     }
    // }

    async fetch_patient_data() {
        try {
            const result = await this.orm.call(
                'res.partner',
                'search_patients_by_phone',
                [this.patient_search.el.value]
            );
            this.state.patient_search_results = result || [];

            // Clear existing form and profile data
            $('#patient-name').val('');
            $('#patient-phone').val('');
            $('#patient-mail').val('');
            $('#patient-dob').val('');
            $('input[name="gender"]').prop('checked', false);
            $('#patient-title').text('');
            $('#patient-code').text('');
            $('#patient-age').text('');
            $('#patient-blood').text('');
            $('#patient-gender').text('');
            $('#hist_head').html('');
            $('#patient-image').attr('src', 'https://cdn.pixabay.com/photo/2015/10/05/22/37/blank-profile-picture-973460_1280.png');

            if (this.state.patient_search_results.length === 1) {
                await this.fetch_selected_patient_details(this.state.patient_search_results[0].id);
            }
        } catch (error) {
            console.error("Failed to fetch patient data:", error);
            alert("Failed to fetch patient data. Please try again.");
        }
    }

    async fetch_selected_patient_details(patientId) {
        const selectedPatientId = patientId?.target ? patientId.target.value : patientId;
        if (!selectedPatientId) {
            return;
        }

        try {
            const result = await this.orm.call(
                'res.partner',
                'get_patient_basic_details',
                [selectedPatientId]
            );

            $('#patient-title').text(result.name || '');
            $('#patient-code').text(result.unique || '');
            $('#patient-age').text(result.dob || '');
            $('#patient-blood').text(result.blood_group || '');
            $('#patient-gender').text(result.gender || '');

            if (result.image_1920) {
                $('#patient-image').attr('src', `data:image/png;base64,${result.image_1920}`);
            } else {
                $('#patient-image').attr('src', 'https://cdn.pixabay.com/photo/2015/10/05/22/37/blank-profile-picture-973460_1280.png');
            }

            $('#patient-name').val(result.name || '');
            $('#patient-phone').val(result.phone || '');
            $('#patient-mail').val(result.email || '');
            $('#patient-dob').val(result.dob_display || this.formatDobForDisplay(result.dob));

            $('input[name="gender"]').prop('checked', false);
            if (result.gender) {
                const genderValue = result.gender.toLowerCase();
                if ($(`input[name="gender"][value="${genderValue}"]`).length) {
                    $(`input[name="gender"][value="${genderValue}"]`).prop('checked', true);
                }
            }
        } catch (error) {
            console.error("Failed to fetch selected patient details:", error);
            alert("Failed to fetch patient details. Please try again.");
        }
    }

    async fetch_medicine_data() {
        this.state.menu = 'medicines';
        this.updateVisibility();
        
        if (!this.state.med?.length) {
            this.state.med = await this.orm.call(
                'product.template',
                'action_get_medicine_data',
                []
            );
        }
        this.state.filtered_med = this.state.med || [];
    }

    search_medicines(ev) {
        const query = ev.target.value.toLowerCase();
        if (query) {
            this.state.filtered_med = this.state.med.filter(m => 
                (m[0] && m[0].toLowerCase().includes(query))
            );
        } else {
            this.state.filtered_med = this.state.med || [];
        }
    }

    async fetch_vaccine_data() {
        this.state.menu = 'vaccines';
        this.updateVisibility();
        
        if (!this.state.vaccine?.length) {
            this.state.vaccine = await this.orm.call(
                'product.template',
                'action_get_vaccine_data',
                []
            );
        }
    }

    async fetch_sale_orders() {
        this.state.menu = 'orders';
        this.updateVisibility();
        
        if (!this.state.order_data?.length) {
            this.state.order_data = await this.orm.call(
                'hospital.pharmacy',
                'fetch_sale_orders',
                []
            );
        }
    }

    async fetch_prescriptions() {
        this.state.menu = 'prescriptions';
        this.updateVisibility();

        if (!this.state.prescription_data?.length) {
            this.state.prescription_data = await this.orm.call(
                'hospital.pharmacy',
                'fetch_prescriptions',
                []
            );
        }
    }

    async openPrescription(prescriptionId) {
        try {
            const action = await this.orm.call(
                'hospital.pharmacy',
                'action_open_prescription',
                [prescriptionId]
            );
            await this.actionService.doAction(action);
        } catch (error) {
            console.error("Failed to open prescription:", error);
            alert(this.getErrorMessage(error, "Failed to open prescription. Please try again."));
        }
    }

    async createSaleOrderFromPrescription(prescriptionId) {
        try {
            const result = await this.orm.call(
                'hospital.pharmacy',
                'create_sale_order_from_prescription',
                [prescriptionId]
            );
            alert('The sale order has been created with reference number ' + result.invoice);
            this.state.prescription_data = await this.orm.call(
                'hospital.pharmacy',
                'fetch_prescriptions',
                []
            );
            this.state.order_data = [];
        } catch (error) {
            console.error("Failed to create sale order from prescription:", error);
            alert(this.getErrorMessage(error, "Failed to create sale order. Please try again."));
        }
    }

    async printSaleOrderBill(orderId) {
        try {
            const action = await this.orm.call(
                'hospital.pharmacy',
                'action_print_sale_order',
                [orderId]
            );
            await this.actionService.doAction(action);
        } catch (error) {
            console.error("Failed to print sale order bill:", error);
            alert(this.getErrorMessage(error, "Failed to print bill. Please try again."));
        }
    }

    async openOrCreateInvoice(orderId) {
        try {
            const action = await this.orm.call(
                'hospital.pharmacy',
                'action_open_or_create_invoice',
                [orderId]
            );
            await this.actionService.doAction(action);
        } catch (error) {
            console.error("Failed to open or create invoice:", error);
            alert(this.getErrorMessage(error, "Failed to open invoice. Please try again."));
        }
    }

    async printInvoice(orderId) {
        try {
            const action = await this.orm.call(
                'hospital.pharmacy',
                'action_print_invoice',
                [orderId]
            );
            await this.actionService.doAction(action);
            this.state.order_data = await this.orm.call(
                'hospital.pharmacy',
                'fetch_sale_orders',
                []
            );
        } catch (error) {
            console.error("Failed to print invoice:", error);
            alert(this.getErrorMessage(error, "Failed to print invoice. Please try again."));
        }
    }

    async clear_data() {
        this.patient_search.el.value = '';
        this.state.patient_search_results = [];
        $('#hist_head').html('');
        $('#patient-title').html('');
        $('#patient-code').html('');
        $('#patient-gender').html('');
        $('#patient-blood').html('');
        $('#patient-image').attr('src', 'https://cdn.pixabay.com/photo/2015/10/05/22/37/blank-profile-picture-973460_1280.png');
        $('#patient-name').val('');
        $('#patient-phone').val('');
        $('#patient-mail').val('');
        $('#patient-dob').val('');
        $('input[name="gender"]').prop('checked', false);
    }
}

PharmacyDashboard.template = "PharmacyDashboard";
PharmacyDashboard.components = { PharmacyOrderLines };
registry.category("actions").add('pharmacy_dashboard_tags', PharmacyDashboard);

// /** @odoo-module */
// import { registry} from '@web/core/registry';
// import { useRef } from "@odoo/owl";
// import { useService } from "@web/core/utils/hooks";
// import { _t } from "@web/core/l10n/translation";
// const { Component, onWillStart, useState} = owl
// import { PharmacyOrderLines } from "./pharmacy_orderlines";
//     var currency=0;
//     var quantity=0;
//     var amount=0;
//     var sub_t=0;
//     var sub_total=0;
//     var product_lst=[];
//     var uom_lst= [];
//     var invoice=0;
//     var invoice_id=0;
//     var tax=0;
// export class PharmacyDashboard extends Component {
// //Initialize Pharmacy Dashboard
//     setup() {
//         super.setup(...arguments);
//         this.ref = useRef('root')
//         this.vaccine_div = useRef('vaccine_div')
//         this.medicine_div = useRef('medicine_div')
//         this.home_content = useRef('home_content')
//         this.patient_name = useRef('PatientName');
//         this.patient_email = useRef('Email');
//         this.patient_search = useRef('PatientSearch');
//         this.orders_div = useRef('orders_div')
//         this.orm = useService('orm')
//         this.user = useService("user");
//         this.actionService = useService("action");
//         this.state = useState({
//               product_lst :[],
//               medicines :[],
//               units :[],
//               sub_total,
//               vaccine :[],
//               order_data:[],
//               order_line: [],
//               menu: 'home',
//         });
//         this.fetch_product();
//         onWillStart(async () => {
//             this.state.med = await this.orm.call('product.template','action_get_medicine_data',[],)})
//     }
// //  Fetch product details
//     async fetch_product() {
//         const domain = [['medicine_ok', '=', true]];
//         const result = await this.orm.call('product.template', 'search_read', [domain]);
//         this.state.product_lst = result;
//         this.create_order();
//     }
// //  Method for creating sale order
//     async create_order() {
//         this.vaccine_div?.el?.classList.add("d-none");
//         this.medicine_div?.el?.classList.add("d-none");
//         this.home_content?.el?.classList.remove("d-none");
//         this.orders_div?.el?.classList.add("d-none");
//         await this.orm.call('hospital.pharmacy','company_currency',
//         ).then(function (result){
//            $('#symbol'+ currency).text(result || '');
//            $('#symbol').text(result || '');
//         })
//         this.state.medicines = await this.product_lst;
//         this.state.units = await this.uom_lst;
//     }
// // To update the orderline of sale order
//     updateOrderLine(line, id) {
//         const orderline = this.state.order_line.filter(orderline => orderline.id === id)[0]
//         orderline.product = line.product
//         orderline.qty = parseInt(line.qty)
//         orderline.uom = line.uom
//         orderline.price = line.price
//         orderline.sub_total = line.sub_total
//     }
// //  To add new row in the sale order line
//     addRow () {
//         const data = [...this.state.order_line, owl.reactive({id: new Date(), product: false, qty: 1, uom: 0, price: 0, sub_total: 0})]
//         this.state.order_line = data
//     }
// // To remove the line if not needed
//     removeLine(id){
//         const filteredData = this.state.order_line.filter(line => line.id != id)
//         this.state.order_line = filteredData
//     }
// //  Create sale order
//     async create_sale_order () {
//         var data ={};
//         data['name'] = $('#patient-name').val();
//         data['phone'] = $('#patient-phone').val();
//         data['email']=  $('#patient-mail').val();
//         data['dob'] =  $('#patient-dob').val();
//         data['products']= this.state.order_line;
//         let hasInvalidQuantity = false;
//         if (hasInvalidQuantity) {
//             alert('Medicine quantity must be greater than or equal to 1.');
//             return;
//         }
//         if(this.patient_name.el.value === "")
//         {
//             alert("Please enter the Name")
//             return;
//         }
//         if(this.patient_email.el.value === "")
//         {
//             alert("Please enter the Email")
//             return;
//         }
//         this.orm.call('hospital.pharmacy', 'create_sale_order',[data]
//         ).then(function (result) {
//             alert('The sale order has been created with refernce number ' +result.invoice)
//             window.location.reload()
//         })
//     }
// //  Fetch patient data
//     async fetch_patient_data () {
//         var self = this;
//         await this.orm.call('res.partner', 'action_get_patient_data',
//            [[this.patient_search.el.value]],
//         ).then(function (result) {
//             $('#patient-title').text(result.name || '');
//             $('#patient-code').text(result.unique || '');
//             $('#patient-age').text(result.dob || '');
//             $('#patient-blood').text(result.blood_group || '');
//             $('#patient-blood').text(result.blood_group || '');
//             $('#patient-gender').text(result.gender || '');
//             $('#patient-image').attr('data:image/png;base64, ' + result.image_1920);
//             if (result.name == 'Patient Not Found') {
//                $('#hist_head').html('')
//                $('#patient-image').attr('src', 'https://cdn.pixabay.com/photo/2015/10/05/22/37/blank-profile-picture-973460_1280.png');
//             }
//             else {
//             }
//         })
//     }
// //  Fetch medicine data while clicking Medicine button
//     // async fetch_medicine_data () {
//     //     this.vaccine_div?.el?.classList.add("d-none");
//     //     this.home_content?.el?.classList.add("d-none");
//     //     this.medicine_div?.el?.classList.remove("d-none");
//     //     this.orders_div?.el?.classList.add("d-none");
//     // }

//     async fetch_medicine_data() {
//         this.state.menu = 'medicines';  // This will trigger the t-if in the template
//         this.vaccine_div?.el?.classList.add("d-none");
//         this.home_content?.el?.classList.add("d-none");
//         this.medicine_div?.el?.classList.remove("d-none");
//         this.orders_div?.el?.classList.add("d-none");
        
//         // Ensure medicine data is loaded
//         if (!this.state.med || this.state.med.length === 0) {
//             this.state.med = await this.orm.call(
//                 'product.template',
//                 'action_get_medicine_data',
//                 []
//             );
//         }
//     }


// //  Fetch vaccine data
//     // async fetch_vaccine_data () {
//     //     this.vaccine_div?.el?.classList.remove("d-none");
//     //     this.home_content?.el?.classList.add("d-none");
//     //     this.medicine_div?.el?.classList.add("d-none");
//     //     this.orders_div?.el?.classList.add("d-none");
//     //     this.state.vaccine = await this.orm.call('product.template','action_get_vaccine_data', [],)
//     // }

//     async fetch_vaccine_data() {
//         this.state.menu = 'vaccines';  // This triggers the t-if in template
//         this.vaccine_div?.el?.classList.remove("d-none");
//         this.home_content?.el?.classList.add("d-none");
//         this.medicine_div?.el?.classList.add("d-none");
//         this.orders_div?.el?.classList.add("d-none");
        
//         // Ensure vaccine data is loaded
//         if (!this.state.vaccine || this.state.vaccine.length === 0) {
//             this.state.vaccine = await this.orm.call(
//                 'product.template',
//                 'action_get_vaccine_data',
//                 []
//             );
//         }
//     }


// //  Method fo fetching all sale orders
//     // async fetch_sale_orders () {
//     //     this.vaccine_div?.el?.classList.add("d-none");
//     //     this.home_content?.el?.classList.add("d-none");
//     //     this.medicine_div?.el?.classList.add("d-none");
//     //     this.orders_div?.el?.classList.remove("d-none");
//     //     this.state.order_data = await this.orm.call('sale.order', 'search_read',
//     //         [[['partner_id.patient_seq','not in', ['New', 'Employee', 'User']]], ['name', 'create_date', 'partner_id', 'amount_total', 'state']],)

//     // }

//     async fetch_sale_orders() {
//         this.state.menu = 'orders';  // This triggers the t-if in template
//         this.vaccine_div?.el?.classList.add("d-none");
//         this.home_content?.el?.classList.add("d-none");
//         this.medicine_div?.el?.classList.add("d-none");
//         this.orders_div?.el?.classList.remove("d-none");
        
//         // Load orders data if not already loaded
//         if (!this.state.order_data || this.state.order_data.length === 0) {
//             this.state.order_data = await this.orm.call(
//                 'sale.order', 
//                 'search_read',
//                 [
//                     [['partner_id.patient_seq', 'not in', ['New', 'Employee', 'User']]], 
//                     ['name', 'create_date', 'partner_id', 'amount_total', 'state']
//                 ]
//             );
//         }
//     }

// //  Method for emptying the data
//     async clear_data () {
//         this.patient_search.el.value = '';
//         $('#hist_head').html('')
//         $('#patient-title').html('')
//         $('#patient-code').html('')
//         $('#patient-gender').html('')
//         $('#patient-blood').html('')
//         $('#patient-image').attr('src', 'https://cdn.pixabay.com/photo/2015/10/05/22/37/blank-profile-picture-973460_1280.png');
//     }
// }
// PharmacyDashboard.template = "PharmacyDashboard"
// registry.category("actions").add('pharmacy_dashboard_tags', PharmacyDashboard);
// PharmacyDashboard.components = { PharmacyOrderLines }
