{
    'name': 'Custom Branding',
    'version': '17.0.1.0.5',
    'author': 'Dreamwarez',
    'website': 'https://dreamwarez.com',
    'license': 'LGPL-3',
    'depends': ['web', 'website', 'mail_bot'],
    'data': [
        'views/custom_login_templates.xml',
        'views/custom_favicon.xml',
        'views/login_title.xml',
    ],
    
    'assets': {
        'web.assets_frontend': [
            'custom_branding/static/src/css/cliniq_login.css',
        ],
        'web.assets_backend': [
            "custom_branding/static/src/js/early_title_fix.js",
            'custom_branding/static/src/js/custom_title.js',
            'custom_branding/static/src/js/hide_mail_odoo_title.js',
            'custom_branding/static/src/js/debrand_mail_messages.js',
            # 'custom_branding/static/src/js/custom_content.js',
        ],
    },      
    'installable': True,
    'auto_install': False,
}
