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
    'depends': ['base', 'hr', 'mail'],
    'data': [
        # 1. Seguridad primero
        'security/biometric_security.xml',
        'security/ir.model.access.csv',
        # 2. Vistas de logs (contiene action_biometric_auth_log_by_device)
        'views/biometric_auth_log_views.xml',
        # 3. Vistas de dispositivos (usa action_biometric_auth_log_by_device)
        'views/biometric_device_views.xml',
        # 4. Menús al final
        'views/biometric_menu.xml',
        # 5. Datos por defecto
        'data/biometric_data.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}