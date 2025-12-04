# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class BiometricAuthLog(models.Model):
    _name = 'biometric.auth.log'
    _description = 'Log de Autenticaciones Biométricas'
    _order = 'auth_date desc'
    _rec_name = 'display_name'

    # ============================================
    # CAMPOS BÁSICOS
    # ============================================
    
    user_id = fields.Many2one(
        'res.users',
        string='Usuario',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    device_id = fields.Many2one(
        'biometric.device',
        string='Dispositivo',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    # ============================================
    # INFORMACIÓN DE AUTENTICACIÓN
    # ============================================
    
    auth_date = fields.Datetime(
        string='Fecha/Hora',
        required=True,
        default=fields.Datetime.now,
        index=True
    )
    
    success = fields.Boolean(
        string='Exitoso',
        default=True,
        index=True
    )
    
    auth_type = fields.Selection([
        ('biometric', 'Biométrica'),
        ('fallback', 'Alternativa'),
        ('automatic', 'Automática')
    ], string='Tipo Autenticación', default='biometric', required=True)
    
    # ============================================
    # INFORMACIÓN DEL INTENTO
    # ============================================
    
    error_code = fields.Char(
        string='Código Error',
        help='Código de error si falló'
    )
    
    error_message = fields.Text(
        string='Mensaje Error',
        help='Mensaje de error si falló'
    )
    
    ip_address = fields.Char(
        string='IP',
        help='Dirección IP desde donde se autenticó'
    )
    
    user_agent = fields.Char(
        string='User Agent',
        help='Información del navegador/app'
    )
    
    # ============================================
    # INFORMACIÓN ADICIONAL
    # ============================================
    
    session_id = fields.Char(
        string='Session ID',
        help='ID de sesión generado'
    )
    
    duration_ms = fields.Integer(
        string='Duración (ms)',
        help='Tiempo que tomó la autenticación en milisegundos'
    )
    
    notes = fields.Text(
        string='Notas',
        help='Notas adicionales sobre el intento'
    )
    
    # ============================================
    # CAMPOS COMPUTADOS
    # ============================================
    
    display_name = fields.Char(
        string='Nombre',
        compute='_compute_display_name'
    )
    
    device_name = fields.Char(
        related='device_id.device_name',
        string='Nombre Dispositivo',
        store=True
    )
    
    device_platform = fields.Selection(
        related='device_id.platform',
        string='Plataforma',
        store=True
    )
    
    @api.depends('user_id', 'auth_date', 'success')
    def _compute_display_name(self):
        """Genera nombre descriptivo para el log"""
        for record in self:
            status = 'Exitoso' if record.success else 'Fallido'
            date_str = fields.Datetime.to_string(record.auth_date)
            record.display_name = f'{record.user_id.name} - {status} - {date_str}'
    
    # ============================================
    # MÉTODOS API
    # ============================================
    
    @api.model
    def log_authentication(self, device_id, success=True, error_info=None, session_id=None, duration_ms=None):
        """
        Registra un intento de autenticación
        
        Args:
            device_id (int): ID del dispositivo
            success (bool): Si fue exitoso
            error_info (dict): Información del error si falló
            session_id (str): ID de sesión si fue exitoso
            duration_ms (int): Duración de la autenticación en milisegundos
            
        Returns:
            dict: Log creado
        """
        try:
            device = self.env['biometric.device'].browse(device_id)
            
            if not device.exists():
                _logger.error(f'Dispositivo {device_id} no encontrado')
                return {'error': 'Dispositivo no encontrado'}
            
            # Preparar datos del log
            log_data = {
                'user_id': self.env.user.id,
                'device_id': device_id,
                'auth_date': fields.Datetime.now(),
                'success': success,
                'session_id': session_id,
            }
            
            # Agregar duración si se proporciona
            if duration_ms is not None:
                log_data['duration_ms'] = duration_ms
            
            # Agregar info de error si falló
            if not success and error_info:
                log_data.update({
                    'error_code': error_info.get('code'),
                    'error_message': error_info.get('message'),
                })
            
            # Crear log
            log = self.create(log_data)
            
            # Si fue exitoso, actualizar dispositivo
            if success:
                device.update_last_used()
            
            _logger.info(
                f'Autenticación {"exitosa" if success else "fallida"} '
                f'para usuario {self.env.user.name} en dispositivo {device.device_name}'
            )
            
            return {
                'id': log.id,
                'success': True,
                'message': 'Log registrado correctamente'
            }
            
        except Exception as e:
            _logger.error(f'Error registrando autenticación: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }
    
    @api.model
    def get_user_auth_history(self, user_id=None, limit=50):
        """
        Obtiene el historial de autenticaciones de un usuario
        
        Args:
            user_id (int): ID del usuario (None = usuario actual)
            limit (int): Límite de registros
            
        Returns:
            list: Historial formateado
        """
        if user_id is None:
            user_id = self.env.user.id
        
        logs = self.search([
            ('user_id', '=', user_id)
        ], order='auth_date desc', limit=limit)
        
        return [{
            'id': log.id,
            'device_name': log.device_name,
            'device_platform': log.device_platform,
            'auth_date': log.auth_date.isoformat() if log.auth_date else None,
            'success': log.success,
            'auth_type': log.auth_type,
            'error_code': log.error_code,
            'error_message': log.error_message,
        } for log in logs]
    
    @api.model
    def get_device_auth_stats(self, device_id):
        """
        Obtiene estadísticas de autenticación de un dispositivo
        
        Args:
            device_id (int): ID del dispositivo
            
        Returns:
            dict: Estadísticas
        """
        logs = self.search([('device_id', '=', device_id)])
        
        total = len(logs)
        successful = len(logs.filtered(lambda l: l.success))
        failed = total - successful
        
        return {
            'total_attempts': total,
            'successful': successful,
            'failed': failed,
            'success_rate': (successful / total * 100) if total > 0 else 0,
            'last_auth': logs[0].auth_date.isoformat() if logs else None,
        }