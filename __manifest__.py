# -*- coding: utf-8 -*-
{
    'name': 'Tourism company',
    'version': '1.0.0',
    'summary': 'إدارة السيارات والسائقين في شركة السياحة',
    'description': """
شركة السياحة
============

إدارة بيانات السيارات والسائقين في مكان واحد.

المميزات:
- تسجيل بيانات السيارات ومواصفاتها.
- إدارة بيانات السائقين وصورهم.
- تسجيل بيانات الرخص وتواريخ انتهائها.
- ربط السائقين بالسيارات.
- متابعة حالات السيارات والسائقين.
- تنبيهات انتهاء رخص السيارات والسائقين.
- متابعة تواريخ انتهاء تأمين السيارات.
    """,
    'category': 'Operations/Fleet',
    'author': 'Tourism Company',
    'license': 'LGPL-3',

    'depends': [
        'base',
        'mail',
    ],

    'data': [
        'security/ir.model.access.csv',
        'report/vehicle_maintenance_report.xml',
        'report/vehicle_handover_report.xml',
        'report/trip_order_report.xml',
        'report/trip_monthly_report.xml',
        'views/vehicle_views.xml',
        'views/driver_profile_views.xml',
        'views/vehicle_maintenance_views.xml',
        'views/vehicle_handover_views.xml',
        'views/trip_order_views.xml',
        'views/trip_dashboard_views.xml',
        'data/cron.xml',
        'data/driver_cron.xml',
        'data/ir_cron_maintenance.xml',
        'data/trip_order_sequence.xml',
        'data/handover_trip_link_views.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'vehicle_profile/static/src/js/trip_dashboard.js',
        ],
    },




    'installable': True,
    'application': True,
}
