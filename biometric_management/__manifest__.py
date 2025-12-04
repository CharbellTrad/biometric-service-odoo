# -*- coding: utf-8 -*-
{
    'name': 'Biometric Devices Management',
    'version': '1.0.0',
    'category': 'Human Resources',
    'summary': 'Gestión de dispositivos biométricos para autenticación de usuarios',
    'description': """
        Sistema de Gestión de Dispositivos Biométricos
        ==============================================
        
        Este módulo permite:
        * Registrar dispositivos biométricos por usuario
        * Gestionar credenciales biométricas de forma segura
        * Monitorear uso y actividad de dispositivos
        * Revocar acceso a dispositivos específicos
        * Auditoría completa de autenticaciones biométricas
        
        Características:
        - Soporte para iOS (Face ID, Touch ID) y Android (Huella, Facial)
        - Información detallada del dispositivo
        - Timestamps de registro y último uso
        - Estados: activo, inactivo, revocado
        - Historial de autenticaciones
    """,
    'author': 'Tu Nombre/Empresa',
    'website': 'https://tuempresa.com',
    'depends': ['base', 'hr'],
    'data': [
        'security/biometric_security.xml',
        'security/ir.model.access.csv',
        'views/biometric_device_views.xml',
        'views/biometric_auth_log_views.xml',
        'views/biometric_menu.xml',
        'data/biometric_data.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}