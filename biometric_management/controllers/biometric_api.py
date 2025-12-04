# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request, Response
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class BiometricAPIController(http.Controller):
    """
    Controlador API para gestión de dispositivos biométricos
    Endpoints REST para React Native App
    """

    def _json_response(self, data, status=200):
        """Helper para respuestas JSON estandarizadas"""
        return Response(
            json.dumps(data, ensure_ascii=False, default=str),
            status=status,
            mimetype='application/json',
            headers={'Content-Type': 'application/json; charset=utf-8'}
        )

    def _error_response(self, message, code='error', status=400):
        """Helper para respuestas de error"""
        return self._json_response({
            'success': False,
            'error': {
                'code': code,
                'message': message
            }
        }, status=status)

    def _validate_session(self):
        """Valida que exista una sesión activa"""
        if not request.session.uid:
            return False, self._error_response(
                'Sesión no válida o expirada',
                'SESSION_REQUIRED',
                401
            )
        return True, None

    # ============================================
    # ENDPOINTS - Gestión de Dispositivos
    # ============================================

    @http.route('/api/biometric/devices/register', 
                type='json', 
                auth='user', 
                methods=['POST'], 
                csrf=False)
    def register_device(self, **kwargs):
        """
        Registra un nuevo dispositivo biométrico
        
        POST /api/biometric/devices/register
        Body: {
            "device_id": "string",
            "device_name": "string",
            "platform": "ios|android|web",
            "os_version": "string",
            "model_name": "string",
            "brand": "string",
            "biometric_type": "fingerprint|facial_recognition|iris",
            "biometric_type_display": "string",
            "is_physical_device": boolean,
            "device_info_json": "string"
        }
        
        Returns: {
            "success": true,
            "data": {...device_data}
        }
        """
        try:
            # Validar datos requeridos
            required_fields = ['device_id', 'device_name', 'platform', 'biometric_type']
            for field in required_fields:
                if field not in kwargs:
                    return {
                        'success': False,
                        'error': f'Campo requerido faltante: {field}'
                    }

            # Registrar dispositivo
            BiometricDevice = request.env['biometric.device']
            device_data = BiometricDevice.register_device(kwargs)

            # Log de registro
            _logger.info(
                f'Dispositivo registrado vía API: {kwargs.get("device_name")} '
                f'para usuario {request.env.user.name}'
            )

            return {
                'success': True,
                'data': device_data,
                'message': 'Dispositivo registrado exitosamente'
            }

        except Exception as e:
            _logger.error(f'Error registrando dispositivo: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/api/biometric/devices', 
                type='json', 
                auth='user', 
                methods=['GET'], 
                csrf=False)
    def get_devices(self, current_device_id=None, **kwargs):
        """
        Obtiene todos los dispositivos del usuario actual
        
        GET /api/biometric/devices?current_device_id=abc123
        
        Args:
            current_device_id (str): ID del dispositivo desde donde se hace la petición
        
        Returns: {
            "success": true,
            "data": [...devices],
            "count": int
        }
        """
        try:
            BiometricDevice = request.env['biometric.device']
            
            # Buscar dispositivos del usuario
            devices_records = BiometricDevice.search([
                ('user_id', '=', request.env.user.id),
                ('state', '!=', 'revoked')
            ], order='last_used_at desc, enrolled_at desc')
            
            # Formatear con contexto del dispositivo actual
            devices = []
            for device in devices_records:
                # Pasar current_device_id al contexto
                device_data = device.with_context(
                    current_device_id=current_device_id
                )._format_device_data()
                devices.append(device_data)

            return {
                'success': True,
                'data': devices,
                'count': len(devices)
            }

        except Exception as e:
            _logger.error(f'Error obteniendo dispositivos: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/api/biometric/devices/<int:device_id>', 
                type='json', 
                auth='user', 
                methods=['GET'], 
                csrf=False)
    def get_device(self, device_id, **kwargs):
        """
        Obtiene información de un dispositivo específico
        
        GET /api/biometric/devices/{device_id}
        
        Returns: {
            "success": true,
            "data": {...device_data}
        }
        """
        try:
            device = request.env['biometric.device'].browse(device_id)

            if not device.exists():
                return {
                    'success': False,
                    'error': 'Dispositivo no encontrado'
                }

            # Verificar que el dispositivo pertenece al usuario actual
            if device.user_id.id != request.env.user.id:
                return {
                    'success': False,
                    'error': 'No tienes permiso para acceder a este dispositivo'
                }

            return {
                'success': True,
                'data': device._format_device_data()
            }

        except Exception as e:
            _logger.error(f'Error obteniendo dispositivo {device_id}: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/api/biometric/devices/<int:device_id>/revoke', 
                type='json', 
                auth='user', 
                methods=['POST'], 
                csrf=False)
    def revoke_device(self, device_id, **kwargs):
        """
        Revoca el acceso de un dispositivo
        
        POST /api/biometric/devices/{device_id}/revoke
        
        Returns: {
            "success": true,
            "message": "Dispositivo revocado exitosamente"
        }
        """
        try:
            device = request.env['biometric.device'].browse(device_id)

            if not device.exists():
                return {
                    'success': False,
                    'error': 'Dispositivo no encontrado'
                }

            # Verificar que el dispositivo pertenece al usuario actual
            if device.user_id.id != request.env.user.id:
                return {
                    'success': False,
                    'error': 'No tienes permiso para revocar este dispositivo'
                }

            device.action_revoke()

            _logger.info(
                f'Dispositivo revocado vía API: {device.device_name} '
                f'por usuario {request.env.user.name}'
            )

            return {
                'success': True,
                'message': 'Dispositivo revocado exitosamente'
            }

        except Exception as e:
            _logger.error(f'Error revocando dispositivo {device_id}: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/api/biometric/devices/<int:device_id>/activate', 
                type='json', 
                auth='user', 
                methods=['POST'], 
                csrf=False)
    def activate_device(self, device_id, **kwargs):
        """
        Reactiva un dispositivo
        
        POST /api/biometric/devices/{device_id}/activate
        
        Returns: {
            "success": true,
            "message": "Dispositivo activado exitosamente"
        }
        """
        try:
            device = request.env['biometric.device'].browse(device_id)

            if not device.exists():
                return {
                    'success': False,
                    'error': 'Dispositivo no encontrado'
                }

            # Verificar que el dispositivo pertenece al usuario actual
            if device.user_id.id != request.env.user.id:
                return {
                    'success': False,
                    'error': 'No tienes permiso para activar este dispositivo'
                }

            device.action_activate()

            return {
                'success': True,
                'message': 'Dispositivo activado exitosamente'
            }

        except Exception as e:
            _logger.error(f'Error activando dispositivo {device_id}: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }

    # ============================================
    # ENDPOINTS - Autenticación y Logs
    # ============================================

    @http.route('/api/biometric/auth/log', 
                type='json', 
                auth='user', 
                methods=['POST'], 
                csrf=False)
    def log_authentication(self, **kwargs):
        """
        Registra un intento de autenticación biométrica
        
        POST /api/biometric/auth/log
        Body: {
            "device_id": int,
            "success": boolean,
            "error_info": {
                "code": "string",
                "message": "string"
            },
            "session_id": "string",
            "duration_ms": int
        }
        
        Returns: {
            "success": true,
            "log_id": int
        }
        """
        try:
            device_id = kwargs.get('device_id')
            success = kwargs.get('success', True)
            error_info = kwargs.get('error_info')
            session_id = kwargs.get('session_id')

            if not device_id:
                return {
                    'success': False,
                    'error': 'device_id es requerido'
                }

            AuthLog = request.env['biometric.auth.log']
            result = AuthLog.log_authentication(
                device_id=device_id,
                success=success,
                error_info=error_info,
                session_id=session_id
            )

            return result

        except Exception as e:
            _logger.error(f'Error registrando autenticación: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/api/biometric/auth/history', 
                type='json', 
                auth='user', 
                methods=['GET'], 
                csrf=False)
    def get_auth_history(self, limit=50, **kwargs):
        """
        Obtiene el historial de autenticaciones del usuario
        
        GET /api/biometric/auth/history?limit=50
        
        Returns: {
            "success": true,
            "data": [...logs],
            "count": int
        }
        """
        try:
            AuthLog = request.env['biometric.auth.log']
            history = AuthLog.get_user_auth_history(limit=limit)

            return {
                'success': True,
                'data': history,
                'count': len(history)
            }

        except Exception as e:
            _logger.error(f'Error obteniendo historial: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/api/biometric/devices/<int:device_id>/stats', 
                type='json', 
                auth='user', 
                methods=['GET'], 
                csrf=False)
    def get_device_stats(self, device_id, **kwargs):
        """
        Obtiene estadísticas de autenticación de un dispositivo
        
        GET /api/biometric/devices/{device_id}/stats
        
        Returns: {
            "success": true,
            "data": {
                "total_attempts": int,
                "successful": int,
                "failed": int,
                "success_rate": float,
                "last_auth": "datetime"
            }
        }
        """
        try:
            device = request.env['biometric.device'].browse(device_id)

            if not device.exists():
                return {
                    'success': False,
                    'error': 'Dispositivo no encontrado'
                }

            # Verificar permisos
            if device.user_id.id != request.env.user.id:
                return {
                    'success': False,
                    'error': 'No tienes permiso para acceder a estas estadísticas'
                }

            AuthLog = request.env['biometric.auth.log']
            stats = AuthLog.get_device_auth_stats(device_id)

            return {
                'success': True,
                'data': stats
            }

        except Exception as e:
            _logger.error(f'Error obteniendo estadísticas: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }

    # ============================================
    # ENDPOINTS - Utilitarios
    # ============================================

    @http.route('/api/biometric/devices/current', 
                type='json', 
                auth='user', 
                methods=['POST'], 
                csrf=False)
    def identify_current_device(self, device_id, **kwargs):
        """
        Identifica y actualiza el dispositivo actual
        
        POST /api/biometric/devices/current
        Body: {
            "device_id": "string"
        }
        
        Returns: {
            "success": true,
            "device": {...device_data}
        }
        """
        try:
            if not device_id:
                return {
                    'success': False,
                    'error': 'device_id es requerido'
                }

            BiometricDevice = request.env['biometric.device']
            device = BiometricDevice.search([
                ('user_id', '=', request.env.user.id),
                ('device_id', '=', device_id)
            ], limit=1)

            if not device:
                return {
                    'success': False,
                    'error': 'Dispositivo no encontrado'
                }

            # Actualizar último uso
            device.update_last_used()

            return {
                'success': True,
                'device': device._format_device_data()
            }

        except Exception as e:
            _logger.error(f'Error identificando dispositivo: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/api/biometric/health', 
                type='json', 
                auth='public', 
                methods=['GET'], 
                csrf=False)
    def health_check(self, **kwargs):
        """
        Health check para verificar disponibilidad del servicio
        
        GET /api/biometric/health
        
        Returns: {
            "status": "ok",
            "timestamp": "datetime"
        }
        """
        return {
            'status': 'ok',
            'service': 'Biometric Management API',
            'version': '1.0.0',
            'timestamp': datetime.now().isoformat()
        }