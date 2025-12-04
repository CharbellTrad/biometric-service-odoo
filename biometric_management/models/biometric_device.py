# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
import logging
import json
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class BiometricDevice(models.Model):
    _name = 'biometric.device'
    _description = 'Dispositivo Biométrico'
    _order = 'last_used_at desc, enrolled_at desc'
    _rec_name = 'device_name'
    _inherit = ['mail.thread', 'mail.activity.mixin']  # Para el chatter

    # ============================================
    # CAMPOS BÁSICOS
    # ============================================
    
    active = fields.Boolean(
        string='Activo',
        default=True,
        help='Si está desactivado, el registro se archivará'
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='Usuario',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
        help='Usuario propietario del dispositivo'
    )
    
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        compute='_compute_employee_id',
        store=True,
        help='Empleado asociado al usuario'
    )
    
    # ============================================
    # INFORMACIÓN DEL DISPOSITIVO
    # ============================================
    
    device_id = fields.Char(
        string='ID Dispositivo',
        required=True,
        index=True,
        help='Identificador único del dispositivo (generado por la app)'
    )
    
    device_name = fields.Char(
        string='Nombre Dispositivo',
        required=True,
        tracking=True,
        help='Nombre descriptivo del dispositivo'
    )
    
    platform = fields.Selection([
        ('ios', 'iOS'),
        ('android', 'Android'),
        ('web', 'Web')
    ], string='Plataforma', required=True, index=True, tracking=True)
    
    os_version = fields.Char(
        string='Versión OS',
        help='Versión del sistema operativo'
    )
    
    model_name = fields.Char(
        string='Modelo',
        help='Modelo del dispositivo'
    )
    
    brand = fields.Char(
        string='Marca',
        help='Marca del dispositivo'
    )
    
    is_physical_device = fields.Boolean(
        string='Dispositivo Físico',
        default=True,
        help='Indica si es un dispositivo físico o emulador'
    )
    
    # ============================================
    # INFORMACIÓN BIOMÉTRICA
    # ============================================
    
    biometric_type = fields.Selection([
        ('fingerprint', 'Huella Digital'),
        ('facial_recognition', 'Reconocimiento Facial'),
        ('iris', 'Reconocimiento de Iris'),
        ('unknown', 'Desconocido')
    ], string='Tipo Biométrico', required=True, default='unknown', tracking=True)
    
    biometric_type_display = fields.Char(
        string='Biometría',
        help='Nombre legible del tipo de biometría'
    )
    
    # ============================================
    # CREDENCIALES (ENCRIPTADAS)
    # ============================================
    
    encrypted_credentials = fields.Text(
        string='Credenciales Encriptadas',
        help='Credenciales del usuario encriptadas (NUNCA en texto plano)'
    )
    
    # ============================================
    # ESTADO Y ACTIVIDAD
    # ============================================
    
    state = fields.Selection([
        ('active', 'Activo'),
        ('inactive', 'Inactivo'),
        ('revoked', 'Revocado')
    ], string='Estado', default='active', required=True, index=True, tracking=True)
    
    is_enabled = fields.Boolean(
        string='Habilitado',
        default=True,
        tracking=True,
        help='Indica si el dispositivo está habilitado para autenticación'
    )
    
    enrolled_at = fields.Datetime(
        string='Fecha Registro',
        required=True,
        default=fields.Datetime.now,
        help='Fecha y hora de inscripción del dispositivo'
    )
    
    last_used_at = fields.Datetime(
        string='Último Uso',
        help='Fecha y hora del último uso exitoso'
    )
    
    revoked_at = fields.Datetime(
        string='Fecha Revocación',
        readonly=True,
        tracking=True,
        help='Fecha y hora de revocación del dispositivo'
    )
    
    revoked_by = fields.Many2one(
        'res.users',
        string='Revocado Por',
        readonly=True,
        help='Usuario que revocó el dispositivo'
    )
    
    # ============================================
    # INFORMACIÓN ADICIONAL
    # ============================================
    
    device_info_json = fields.Text(
        string='Info Completa (JSON)',
        help='Información completa del dispositivo en formato JSON'
    )
    
    notes = fields.Text(
        string='Notas',
        help='Notas adicionales sobre el dispositivo'
    )
    
    # ============================================
    # CAMPOS COMPUTADOS
    # ============================================
    
    auth_count = fields.Integer(
        string='Total Autenticaciones',
        compute='_compute_auth_stats',
        store=True,
        help='Número total de autenticaciones exitosas'
    )
    
    last_auth_date = fields.Datetime(
        string='Última Autenticación',
        compute='_compute_auth_stats',
        store=True
    )
    
    days_since_last_use = fields.Integer(
        string='Días Sin Uso',
        compute='_compute_days_since_last_use',
        help='Días desde el último uso',
        store=True
    )
    
    is_recently_used = fields.Boolean(
        string='Usado Recientemente',
        compute='_compute_is_recently_used',
        help='Usado en las últimas 24 horas',
        store=True
    )
    
    is_stale = fields.Boolean(
        string='Inactivo (>30 días)',
        compute='_compute_is_stale',
        help='Más de 30 días sin usar',
        store=True
    )
    
    # ============================================
    # RESTRICCIONES SQL
    # ============================================
    
    _sql_constraints = [
        ('unique_device_per_user', 
         'UNIQUE(user_id, device_id)',
         'Este dispositivo ya está registrado para este usuario.'),
    ]
    
    # ============================================
    # CAMPOS COMPUTADOS - MÉTODOS
    # ============================================
    
    @api.depends('user_id')
    def _compute_employee_id(self):
        """Relaciona el dispositivo con el empleado del usuario"""
        for record in self:
            if record.user_id:
                employee = self.env['hr.employee'].search([
                    ('user_id', '=', record.user_id.id)
                ], limit=1)
                record.employee_id = employee.id if employee else False
            else:
                record.employee_id = False
    
    @api.depends('last_used_at')
    def _compute_days_since_last_use(self):
        """Calcula días desde el último uso"""
        for record in self:
            if record.last_used_at:
                delta = fields.Datetime.now() - record.last_used_at
                record.days_since_last_use = delta.days
            else:
                record.days_since_last_use = -1
    
    @api.depends('last_used_at')
    def _compute_is_recently_used(self):
        """Determina si fue usado en las últimas 24 horas"""
        for record in self:
            if record.last_used_at:
                delta = fields.Datetime.now() - record.last_used_at
                record.is_recently_used = delta.total_seconds() < 86400  # 24 horas
            else:
                record.is_recently_used = False
    
    @api.depends('last_used_at', 'enrolled_at')
    def _compute_is_stale(self):
        """Determina si está inactivo (>30 días)"""
        for record in self:
            reference_date = record.last_used_at or record.enrolled_at
            if reference_date:
                delta = fields.Datetime.now() - reference_date
                record.is_stale = delta.days > 30
            else:
                record.is_stale = False
    
    @api.depends('device_id')
    def _compute_auth_stats(self):
        """Calcula estadísticas de autenticación"""
        for record in self:
            if record.id:
                auth_logs = self.env['biometric.auth.log'].search([
                    ('device_id', '=', record.id),
                    ('success', '=', True)
                ])
                record.auth_count = len(auth_logs)
                record.last_auth_date = max(auth_logs.mapped('auth_date')) if auth_logs else False
            else:
                record.auth_count = 0
                record.last_auth_date = False
    
    # ============================================
    # MÉTODOS CRUD
    # ============================================
    
    @api.model_create_multi
    def create(self, vals_list):
        """Validaciones al crear dispositivos"""
        for vals in vals_list:
            # Validar que el usuario existe
            if 'user_id' in vals:
                user = self.env['res.users'].browse(vals['user_id'])
                if not user.exists():
                    raise ValidationError('El usuario especificado no existe.')
        
        # Crear dispositivos
        devices = super(BiometricDevice, self).create(vals_list)
        
        for device in devices:
            _logger.info(
                f'Dispositivo biométrico creado: {device.device_name} '
                f'para usuario {device.user_id.name}'
            )
        
        return devices
    
    def write(self, vals):
        """Validaciones al actualizar un dispositivo"""
        # Si se está revocando, agregar info
        if 'state' in vals and vals['state'] == 'revoked':
            vals['revoked_at'] = fields.Datetime.now()
            vals['revoked_by'] = self.env.user.id
            vals['is_enabled'] = False
        
        result = super(BiometricDevice, self).write(vals)
        
        if 'state' in vals and vals['state'] == 'revoked':
            for record in self:
                _logger.info(
                    f'Dispositivo revocado: {record.device_name} '
                    f'por {self.env.user.name}'
                )
        
        return result
    
    def unlink(self):
        """Validaciones al eliminar"""
        for record in self:
            _logger.warning(
                f'Eliminando dispositivo biométrico: {record.device_name} '
                f'del usuario {record.user_id.name}'
            )
        
        return super(BiometricDevice, self).unlink()
    
    # ============================================
    # MÉTODOS DE NEGOCIO
    # ============================================
    
    def action_revoke(self):
        """Revoca el acceso del dispositivo"""
        self.ensure_one()
        
        if self.state == 'revoked':
            raise UserError('Este dispositivo ya está revocado.')
        
        self.write({
            'state': 'revoked',
            'is_enabled': False,
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Dispositivo Revocado',
                'message': f'El dispositivo {self.device_name} ha sido revocado.',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_activate(self):
        """Reactiva un dispositivo"""
        self.ensure_one()
        
        if self.state == 'active':
            raise UserError('Este dispositivo ya está activo.')
        
        self.write({
            'state': 'active',
            'is_enabled': True,
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Dispositivo Activado',
                'message': f'El dispositivo {self.device_name} ha sido activado.',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def update_last_used(self):
        """Actualiza el timestamp de último uso"""
        self.ensure_one()
        self.write({
            'last_used_at': fields.Datetime.now(),
            'state': 'active'
        })
        
        _logger.debug(f'Actualizado last_used para dispositivo: {self.device_name}')
    
    # ============================================
    # MÉTODOS API PARA LA APP
    # ============================================
    
    @api.model
    def register_device(self, device_data=None, **kwargs):
        """
        Registra un nuevo dispositivo biométrico
        
        Args:
            device_data (dict): Información del dispositivo (puede venir via args o kwargs)
            **kwargs: Datos del dispositivo cuando se llama via JSON-RPC
            
        Returns:
            dict: Información del dispositivo creado
        """
        try:
            # Si device_data es None, usar kwargs directamente (JSON-RPC call)
            if device_data is None:
                device_data = kwargs
            
            # Validar datos requeridos
            required_fields = ['device_id', 'device_name', 'platform', 'biometric_type']
            for field in required_fields:
                if field not in device_data:
                    raise ValidationError(f'Campo requerido faltante: {field}')
            
            # Agregar usuario actual
            device_data['user_id'] = self.env.user.id
            
            # Verificar si ya existe
            existing = self.search([
                ('user_id', '=', self.env.user.id),
                ('device_id', '=', device_data['device_id'])
            ], limit=1)
            
            if existing:
                # Actualizar dispositivo existente
                existing.write({
                    'device_name': device_data.get('device_name', existing.device_name),
                    'os_version': device_data.get('os_version', existing.os_version),
                    'biometric_type': device_data.get('biometric_type', existing.biometric_type),
                    'biometric_type_display': device_data.get('biometric_type_display'),
                    'last_used_at': fields.Datetime.now(),
                    'state': 'active',
                    'is_enabled': True,
                })
                device = existing
                _logger.info(f'Dispositivo actualizado: {device.device_name}')
            else:
                # Crear nuevo dispositivo
                device = self.create(device_data)
                _logger.info(f'Nuevo dispositivo registrado: {device.device_name}')
            
            return device._format_device_data()
            
        except Exception as e:
            _logger.error(f'Error registrando dispositivo: {str(e)}')
            raise UserError(f'Error al registrar dispositivo: {str(e)}')
    
    @api.model
    def get_user_devices(self, user_id=None, current_device_id=None, **kwargs):
        """
        Obtiene todos los dispositivos de un usuario
        
        Args:
            user_id (int): ID del usuario (None = usuario actual)
            current_device_id (str): ID del dispositivo actual para marcarlo
            **kwargs: Argumentos adicionales desde JSON-RPC
            
        Returns:
            list: Lista de dispositivos formateados
        """
        # Obtener current_device_id desde kwargs si no se pasó directamente
        if current_device_id is None:
            current_device_id = kwargs.get('current_device_id')
        
        if user_id is None:
            user_id = kwargs.get('user_id') or self.env.user.id
        
        devices = self.search([
            ('user_id', '=', user_id),
            ('state', '!=', 'revoked')
        ], order='last_used_at desc, enrolled_at desc')
        
        # Pasar current_device_id al contexto para identificar dispositivo actual
        return [device.with_context(current_device_id=current_device_id)._format_device_data() for device in devices]
    
    def _format_device_data(self):
        """Formatea los datos del dispositivo para la API - Compatible con Frontend"""
        self.ensure_one()
        
        # Determinar si es el dispositivo actual (comparando device_id del contexto)
        current_device_id = self.env.context.get('current_device_id')
        is_current = (current_device_id == self.device_id) if current_device_id else False
        
        return {
            # Campos básicos
            'id': self.id,
            'deviceId': self.device_id,  # ← Frontend usa camelCase
            'deviceName': self.device_name,
            'platform': self.platform,
            'osVersion': self.os_version,
            'modelName': self.model_name,
            'brand': self.brand,
            'isPhysicalDevice': self.is_physical_device,
            
            # Biometría
            'biometricType': self.biometric_type_display or self.biometric_type,
            
            # Estado
            'state': self.state,
            'isEnabled': self.is_enabled,
            'isCurrentDevice': is_current,  # ← Nuevo campo requerido
            
            # Fechas (ISO 8601)
            'enrolledAt': self.enrolled_at.isoformat() if self.enrolled_at else None,
            'lastUsedAt': self.last_used_at.isoformat() if self.last_used_at else None,
            
            # Estadísticas
            'authCount': self.auth_count,
            'isRecentlyUsed': self.is_recently_used,
            'isStale': self.is_stale,
            'daysSinceLastUse': self.days_since_last_use,
        }