# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.http import root
import requests
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
        required=False,  # Permitir auth sin dispositivo biométrico
        ondelete='set null',
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
        ('traditional', 'Tradicional'),
        ('fallback', 'Alternativa'),
        ('automatic', 'Automática')
    ], string='Tipo Autenticación', default='biometric', required=True)
    
    # ============================================
    # TRACKING DE SESIÓN
    # ============================================
    
    session_active = fields.Boolean(
        string='Sesión Activa',
        default=True,
        help='Indica si la sesión de esta autenticación sigue activa'
    )
    
    session_ended_at = fields.Datetime(
        string='Sesión Finalizada',
        help='Fecha/hora en que finalizó la sesión'
    )
    
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
    
    # Campos de dispositivo - pueden venir del device_id o ser directos
    device_name_direct = fields.Char(
        string='Nombre Dispositivo Directo',
        help='Nombre del dispositivo cuando no hay device_id'
    )
    
    device_platform_direct = fields.Char(
        string='Plataforma Directa',
        help='Plataforma cuando no hay device_id'
    )
    
    device_name = fields.Char(
        string='Nombre Dispositivo',
        compute='_compute_device_info',
        store=True
    )
    
    device_platform = fields.Char(
        string='Plataforma',
        compute='_compute_device_info',
        store=True
    )
    
    @api.depends('device_id', 'device_id.device_name', 'device_id.platform', 'device_name_direct', 'device_platform_direct')
    def _compute_device_info(self):
        """Computa nombre y plataforma desde device_id o campos directos"""
        for record in self:
            if record.device_id:
                record.device_name = record.device_id.device_name or 'Dispositivo'
                record.device_platform = record.device_id.platform or 'unknown'
            else:
                record.device_name = record.device_name_direct or 'Sin dispositivo'
                record.device_platform = record.device_platform_direct or 'unknown'
    
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
                # Persistencia de datos del dispositivo (para historial si se borra dispositivo)
                'device_name_direct': device.device_name,
                'device_platform_direct': device.platform,
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
            
            # Crear log (con sudo para evitar restricciones de acceso)
            log = self.sudo().create(log_data)
            
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
    def get_user_auth_history(self, user_id=None, limit=20, offset=0):
        """
        Obtiene el historial de autenticaciones de un usuario con paginación
        
        Args:
            user_id (int): ID del usuario (None = usuario actual)
            limit (int): Límite de registros por página
            offset (int): Desplazamiento para paginación
            
        Returns:
            dict: Historial formateado con información de paginación
        """
        from datetime import timedelta
        
        if user_id is None:
            user_id = self.env.user.id
        
        domain = [('user_id', '=', user_id)]
        
        # Obtener total para paginación
        total_count = self.search_count(domain)
        
        # Obtener logs con paginación
        logs = self.search(domain, order='auth_date desc', limit=limit, offset=offset)
        
        # Venezuela timezone offset (UTC-4)
        tz_offset = timedelta(hours=-4)
        
        def format_datetime_venezuela(dt):
            """Convierte datetime UTC a hora Venezuela"""
            if not dt:
                return None
            # Restar 4 horas para Venezuela (UTC a UTC-4)
            local_dt = dt + tz_offset
            return local_dt.strftime('%Y-%m-%dT%H:%M:%S')
        
        records = [{
            'id': log.id,
            'device_name': log.device_name or 'Sin dispositivo',
            'device_platform': log.device_platform or 'unknown',
            'device_name_direct': log.device_name_direct,
            'device_platform_direct': log.device_platform_direct,
            'auth_date': format_datetime_venezuela(log.auth_date),
            'success': log.success,
            'auth_type': log.auth_type,
            'session_active': log.session_active,
            'session_ended_at': format_datetime_venezuela(log.session_ended_at),
            'error_code': log.error_code,
            'error_message': log.error_message,
            'ip_address': log.ip_address,
            'user_agent': log.user_agent,
            'duration_ms': log.duration_ms,
            'notes': log.notes,
            'session_id': log.session_id,
        } for log in logs]
        
        return {
            'records': records,
            'total': total_count,
            'limit': limit,
            'offset': offset,
            'has_more': (offset + limit) < total_count,
        }
    
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
    
    @api.model
    def log_traditional_login(self, session_id=None, device_info=None):
        """
        Registra un login tradicional (usuario/contraseña)
        
        Args:
            session_id (str): ID de sesión
            device_info (dict): Información del dispositivo {device_name, platform}
            
        Returns:
            dict: Resultado de la operación
        """
        try:
            # Buscar dispositivo del usuario con coincidencia estricta
            device = None
            
            # 1. Intentar buscar por UUID único si está disponible
            if device_info and device_info.get('device_id'):
                device = self.env['biometric.device'].search([
                    ('user_id', '=', self.env.user.id),
                    ('device_id', '=', device_info.get('device_id')),
                    ('state', '=', 'active')
                ], limit=1)
            
            # 2. Si no hay UUID o no se encontró, buscar por plataforma (evitar mezclar iOS/Android)
            if not device and device_info and device_info.get('platform'):
                device = self.env['biometric.device'].search([
                    ('user_id', '=', self.env.user.id),
                    ('platform', '=', device_info.get('platform')),
                    ('state', '=', 'active')
                ], limit=1)
            
            # 3. Si no hay info, buscar cualquier activo (comportamiento legacy)
            if not device and not device_info:
                 device = self.env['biometric.device'].search([
                    ('user_id', '=', self.env.user.id),
                    ('state', '=', 'active')
                ], limit=1)
            
            log_data = {
                'user_id': self.env.user.id,
                'auth_date': fields.Datetime.now(),
                'success': True,
                'auth_type': 'traditional',
                'session_id': session_id,
                'session_active': True,
            }
            
            if device:
                log_data['device_id'] = device.id
                # SIEMPRE guardar copia de los datos (para historial persistente)
                log_data['device_name_direct'] = device.device_name
                log_data['device_platform_direct'] = device.platform
            else:
                # Si no hay dispositivo biométrico coincidente, usar info directa
                log_data['device_name_direct'] = device_info.get('device_name', 'Dispositivo') if device_info else 'Dispositivo'
                log_data['device_platform_direct'] = device_info.get('platform', 'unknown') if device_info else 'unknown'
            
            # Crear log (con sudo para evitar restricciones de acceso)
            log = self.sudo().create(log_data)
            
            _logger.info(f'Login tradicional registrado para {self.env.user.name}')
            
            return {
                'success': True,
                'log_id': log.id,
                'message': 'Login registrado correctamente'
            }
            
        except Exception as e:
            _logger.error(f'Error registrando login tradicional: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }
    
    @api.model
    def end_session(self, session_id=None, device_uuid=None):
        """
        Marca la sesión actual como finalizada
        🔧 Usa sudo() para permitir que cualquier usuario cierre su propia sesión
        
        Args:
            session_id (str): ID de sesión (opcional)
            device_uuid (str): UUID del dispositivo para cerrar sesión específica (opcional)
            
        Returns:
            dict: Resultado de la operación
        """
        try:
            current_user_id = self.env.user.id
            
            # Buscar sesiones activas del usuario (con sudo para evitar restricciones de acceso)
            domain = [
                ('user_id', '=', current_user_id),
                ('session_active', '=', True)
            ]
            
            if session_id:
                domain.append(('session_id', '=', session_id))
            
            # Si se proporciona device_uuid, filtrar por el dispositivo correspondiente
            if device_uuid:
                device = self.env['biometric.device'].search([
                    ('device_id', '=', device_uuid),
                    ('user_id', '=', current_user_id)
                ], limit=1)
                
                if device:
                    domain.append(('device_id', '=', device.id))
                    _logger.info(f'Cerrando sesión específica para dispositivo {device.device_name}')
            
            # 🔧 Usar sudo() para la búsqueda y escritura
            active_sessions = self.sudo().search(domain, order='auth_date desc')
            
            if active_sessions:
                active_sessions.write({
                    'session_active': False,
                    'session_ended_at': fields.Datetime.now()
                })
                
                _logger.info(f'Sesión(es) finalizada(s) para {self.env.user.name}: {len(active_sessions)} sesiones')
                
                return {
                    'success': True,
                    'sessions_ended': len(active_sessions),
                    'message': 'Sesión(es) finalizada(s)'
                }
            
            return {
                'success': True,
                'sessions_ended': 0,
                'message': 'No había sesiones activas'
            }
            
        except Exception as e:
            _logger.error(f'Error finalizando sesión: {str(e)}')
            return {
                'success': False,
                'error': str(e)
            }
    
    @api.model
    def get_active_sessions(self, user_id=None):
        """
        Obtiene las sesiones activas de un usuario
        
        Args:
            user_id (int): ID del usuario (None = usuario actual)
            
        Returns:
            list: Sesiones activas
        """
        if user_id is None:
            user_id = self.env.user.id
        
        sessions = self.search([
            ('user_id', '=', user_id),
            ('session_active', '=', True),
            ('success', '=', True)
        ], order='auth_date desc')
        
        return [{
            'id': s.id,
            'device_name': s.device_name,
            'auth_date': s.auth_date.isoformat() if s.auth_date else None,
            'auth_type': s.auth_type,
        } for s in sessions]
    
    @api.model
    def destroy_session(self, session_id):
        """
        Destruye/finaliza una sesión específica usando el endpoint de Odoo
        """
        if not session_id:
            return {
                'success': False,
                'message': 'Session ID es requerido'
            }
        
        try:
            # 1. Buscar el registro de autenticación
            auth_log = self.sudo().search([
                ('session_id', '=', session_id),
                ('session_active', '=', True)
            ], limit=1)
            
            if not auth_log:
                return {
                    'success': False,
                    'message': 'Sesión no encontrada o ya está finalizada'
                }
            
            # 2. Destruir la sesión usando el endpoint de Odoo
            try:
                # Obtener la base URL del servidor
                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                destroy_url = f"{base_url}/web/session/destroy"
                
                # Hacer la petición con el session_id específico
                response = requests.post(
                    destroy_url,
                    json={},
                    headers={
                        'Content-Type': 'application/json',
                        'Cookie': f'session_id={session_id}'  # ← Enviar la sesión a destruir
                    },
                    timeout=5
                )
                
                if response.status_code == 200:
                    _logger.info(f"✅ Sesión {session_id} destruida vía endpoint")
                else:
                    _logger.warning(f"⚠️ Respuesta inesperada al destruir sesión: {response.status_code}")
                    # Continuar de todos modos
                    
            except Exception as e:
                _logger.error(f"❌ Error llamando endpoint destroy: {str(e)}")
                # No fallar aquí, intentar el método alternativo
            
            # 3. Método alternativo: Acceder directamente al session store
            try:
                session_store = root.session_store
                
                # El session store tiene un método save/delete
                # Intentar eliminar con diferentes formatos de clave
                db_name = self.env.cr.dbname
                
                for sid_format in [
                    session_id,
                    f"{db_name}_{session_id}",
                ]:
                    try:
                        session_store.delete(db_name, sid_format)
                        _logger.info(f"✅ Sesión eliminada del store: {sid_format}")
                        break
                    except Exception as inner_e:
                        _logger.debug(f"Formato {sid_format} no funcionó: {str(inner_e)}")
                        continue
                        
            except Exception as e:
                _logger.warning(f"⚠️ No se pudo eliminar del session store: {str(e)}")
                # No es crítico si ya se destruyó vía endpoint
            
            # 4. Marcar el log como finalizado
            auth_log.write({
                'session_active': False,
                'session_ended_at': fields.Datetime.now()
            })
            
            _logger.info(f"✅ Sesión {session_id} marcada como finalizada")
            
            return {
                'success': True,
                'message': 'Sesión finalizada correctamente',
                'session_id': session_id
            }
            
        except Exception as e:
            _logger.error(f"❌ Error al destruir sesión {session_id}: {str(e)}")
            return {
                'success': False,
                'message': f'Error al finalizar la sesión: {str(e)}'
            }
        """
        Destruye una sesión específica
        """
        if not session_id:
            return {
                'success': False,
                'message': 'Session ID es requerido'
            }
        
        try:
            # 1. Buscar el registro de autenticación
            auth_log = self.sudo().search([
                ('session_id', '=', session_id),
                ('session_active', '=', True)
            ], limit=1)
            
            if not auth_log:
                return {
                    'success': False,
                    'message': 'Sesión no encontrada o ya está finalizada'
                }
            
            # 2. Destruir la sesión del session store
            session_deleted = False
            error_msg = None
            
            try:
                session_store = root.session_store
                db_name = self.env.cr.dbname
                
                # El método correcto es: session_store.delete(dbname, sid)
                session_store.delete(db_name, session_id)
                session_deleted = True
                _logger.info(f"✅ Sesión {session_id} eliminada del session store")
                
            except AttributeError as e:
                # Si session_store.delete no existe, intentar otra forma
                _logger.warning(f"⚠️ Método delete no disponible: {str(e)}")
                try:
                    # Acceso directo al store (depende del tipo de store)
                    store = root.session_store
                    if hasattr(store, 'path'):  # FilesystemSessionStore
                        import os
                        session_file = os.path.join(store.path, db_name, session_id)
                        if os.path.exists(session_file):
                            os.remove(session_file)
                            session_deleted = True
                            _logger.info(f"✅ Archivo de sesión eliminado: {session_file}")
                except Exception as inner_e:
                    error_msg = str(inner_e)
                    _logger.error(f"❌ Error eliminando archivo: {inner_e}")
                    
            except Exception as e:
                error_msg = str(e)
                _logger.error(f"❌ Error general eliminando sesión: {e}")
            
            # 3. Marcar el log como finalizado SIEMPRE
            # (incluso si no se pudo eliminar del store, al menos marcamos el log)
            auth_log.write({
                'session_active': False,
                'session_ended_at': fields.Datetime.now()
            })
            
            _logger.info(f"✅ Auth log marcado como finalizado")
            
            # 4. Retornar resultado
            if session_deleted:
                return {
                    'success': True,
                    'message': 'Sesión finalizada correctamente'
                }
            else:
                # Sesión marcada como finalizada pero puede seguir activa en el store
                return {
                    'success': True,
                    'message': 'Sesión marcada como finalizada. Es posible que deba esperar a que expire.',
                    'warning': error_msg
                }
            
        except Exception as e:
            _logger.error(f"❌ Error crítico: {str(e)}")
            return {
                'success': False,
                'message': f'Error al finalizar la sesión: {str(e)}'
            }
        """
        Destruye/finaliza una sesión específica
        """
        if not session_id:
            return {
                'success': False,
                'message': 'Session ID es requerido'
            }
        
        try:
            # 1. Buscar el registro de autenticación
            auth_log = self.sudo().search([
                ('session_id', '=', session_id),
                ('session_active', '=', True)
            ], limit=1)
            
            if not auth_log:
                return {
                    'success': False,
                    'message': 'Sesión no encontrada o ya está finalizada'
                }
            
            # 2. Destruir la sesión del session store
            session_deleted = False
            try:
                # Método 1: Usando el session_store directamente
                session_store = root.session_store
                
                # Formato completo del SID en el store
                sid_key = f"{self.env.cr.dbname}_{session_id}"
                
                # Intentar varios formatos de clave
                for key_format in [session_id, sid_key, f"session:{session_id}"]:
                    try:
                        session_store.delete(key_format)
                        _logger.info(f"✅ Sesión eliminada con clave: {key_format}")
                        session_deleted = True
                        break
                    except:
                        continue
                
                # Método 2: Si el anterior falla, invalidar manualmente
                if not session_deleted:
                    # Marcar como inválida en la tabla de sesiones
                    self.env.cr.execute("""
                        DELETE FROM ir_sessions 
                        WHERE sid = %s
                    """, (session_id,))
                    
                    if self.env.cr.rowcount > 0:
                        session_deleted = True
                        _logger.info(f"✅ Sesión {session_id} eliminada de ir_sessions")
                    
            except Exception as e:
                _logger.error(f"❌ Error eliminando sesión: {str(e)}")
                return {
                    'success': False,
                    'message': f'Error al eliminar la sesión: {str(e)}'
                }
            
            # 3. Marcar el log como finalizado
            auth_log.write({
                'session_active': False,
                'session_ended_at': fields.Datetime.now()
            })
            
            _logger.info(f"✅ Sesión {session_id} destruida completamente")
            
            return {
                'success': True,
                'message': 'Sesión finalizada correctamente',
                'session_deleted': session_deleted
            }
            
        except Exception as e:
            _logger.error(f"❌ Error: {str(e)}")
            return {
                'success': False,
                'message': str(e)
            }
        """
        Destruye/finaliza una sesión específica
        
        Args:
            session_id (str): Session ID a destruir
            
        Returns:
            dict: Resultado de la operación
        """
        if not session_id:
            return {
                'success': False,
                'message': 'Session ID es requerido'
            }
        
        try:
            # 1. Buscar el registro de autenticación con esa sesión
            auth_log = self.sudo().search([
                ('session_id', '=', session_id),
                ('session_active', '=', True)
            ], limit=1)
            
            if not auth_log:
                return {
                    'success': False,
                    'message': 'Sesión no encontrada o ya está finalizada'
                }
            
            # 2. Marcar la sesión como finalizada
            auth_log.write({
                'session_active': False,
                'session_ended_at': fields.Datetime.now()
            })
            
            _logger.info(f"✅ Sesión {session_id} marcada como finalizada")
            
            # 3. Intentar destruir la sesión del session store de Odoo
            try:
                session_store = root.session_store
                session_store.delete(self.env.cr.dbname, session_id)
                _logger.info(f"✅ Sesión {session_id} eliminada del session store")
            except Exception as e:
                _logger.warning(f"⚠️ No se pudo eliminar del session store: {str(e)}")
                # No es crítico, ya marcamos el log como finalizado
            
            return {
                'success': True,
                'message': 'Sesión finalizada correctamente',
                'session_id': session_id
            }
            
        except Exception as e:
            _logger.error(f"❌ Error al destruir sesión {session_id}: {str(e)}")
            return {
                'success': False,
                'message': f'Error al finalizar la sesión: {str(e)}'
            }