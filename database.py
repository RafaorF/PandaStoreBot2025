import sqlite3
import json
import logging
from datetime import datetime, timedelta
import os
import shutil

logger = logging.getLogger('PandaBot.Database')

class Database:
    def __init__(self, db_path='data/bot.db'):
        """Inicializar banco de dados"""
        os.makedirs('data', exist_ok=True)
        os.makedirs('backups', exist_ok=True)
        
        self.db_path = db_path
        # Usar check_same_thread=False para permitir acesso de múltiplas threads
        self.conn = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        
        # Ativar WAL mode para melhor concorrência
        self.cursor.execute("PRAGMA journal_mode=WAL")
        self.cursor.execute("PRAGMA synchronous=NORMAL")
        
        self._create_tables()
        logger.info(f"✅ Banco de dados inicializado em: {os.path.abspath(db_path)}")
    
    def _create_tables(self):
        """Criar todas as tabelas necessárias"""
        
        # Tabela de usuários OAuth2
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS oauth_users (
                user_id TEXT PRIMARY KEY,
                access_token TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                added_at INTEGER NOT NULL,
                last_pulled INTEGER DEFAULT 0
            )
        """)
        
        # Tabela de tickets
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT UNIQUE NOT NULL,
                user_id TEXT NOT NULL,
                type TEXT NOT NULL,
                status TEXT DEFAULT 'open',
                created_at INTEGER NOT NULL,
                closed_at INTEGER DEFAULT NULL,
                closed_by TEXT DEFAULT NULL,
                rating INTEGER DEFAULT NULL,
                rating_feedback TEXT DEFAULT NULL,
                transcript TEXT DEFAULT NULL
            )
        """)
        
        # Tabela de configurações (suporta JSON)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                guild_id TEXT PRIMARY KEY,
                config_data TEXT NOT NULL,
                updated_at INTEGER
            )
        """)
        
        # Tabela de blacklist
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                user_id TEXT PRIMARY KEY,
                reason TEXT,
                added_by TEXT,
                added_at INTEGER
            )
        """)
        
        # Tabela de logs
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                user_id TEXT,
                guild_id TEXT,
                action TEXT NOT NULL,
                details TEXT,
                timestamp INTEGER NOT NULL
            )
        """)
        
        # Tabela de estatísticas
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                oauth_registrations INTEGER DEFAULT 0,
                successful_pulls INTEGER DEFAULT 0,
                failed_pulls INTEGER DEFAULT 0,
                tickets_opened INTEGER DEFAULT 0,
                tickets_closed INTEGER DEFAULT 0
            )
        """)
        
        # Tabela de avaliações
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                user_id TEXT,
                rating INTEGER,
                service_rating INTEGER,
                product_rating INTEGER,
                feedback TEXT,
                created_at INTEGER,
                FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id)
            )
        """)
        
        self.conn.commit()
        logger.info("✅ Tabelas verificadas/criadas")
    
    # ==================== OAUTH2 ====================
    
    def add_oauth_user(self, user_id, access_token, refresh_token, expires_at):
        """Adicionar/atualizar usuário OAuth2"""
        try:
            self.cursor.execute("""
                INSERT OR REPLACE INTO oauth_users 
                (user_id, access_token, refresh_token, expires_at, added_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, access_token, refresh_token, expires_at, int(datetime.utcnow().timestamp())))
            self.conn.commit()
            self.add_log('oauth', user_id, None, 'registered', 'OAuth2 autorizado')
            self.increment_stat('oauth_registrations')
            logger.info(f"✅ OAuth2 salvo para usuário {user_id}")
        except Exception as e:
            logger.error(f"❌ Erro ao salvar OAuth2 para {user_id}: {e}")
            self.conn.rollback()
    
    def get_oauth_user(self, user_id):
        """Obter dados OAuth2 de um usuário"""
        try:
            self.cursor.execute("SELECT * FROM oauth_users WHERE user_id = ?", (user_id,))
            row = self.cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Erro ao buscar OAuth2 de {user_id}: {e}")
            return None
    
    def get_all_oauth_users(self):
        """Obter todos os usuários OAuth2"""
        try:
            self.cursor.execute("SELECT * FROM oauth_users")
            return [dict(row) for row in self.cursor.fetchall()]
        except Exception as e:
            logger.error(f"Erro ao buscar todos OAuth2: {e}")
            return []
    
    def remove_oauth_user(self, user_id):
        """Remover usuário OAuth2"""
        try:
            self.cursor.execute("DELETE FROM oauth_users WHERE user_id = ?", (user_id,))
            self.conn.commit()
            self.add_log('oauth', user_id, None, 'removed', 'OAuth2 revogado')
        except Exception as e:
            logger.error(f"Erro ao remover OAuth2 de {user_id}: {e}")
            self.conn.rollback()
    
    def update_last_pulled(self, user_id):
        """Atualizar timestamp do último pull"""
        try:
            self.cursor.execute("""
                UPDATE oauth_users SET last_pulled = ? WHERE user_id = ?
            """, (int(datetime.utcnow().timestamp()), user_id))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Erro ao atualizar last_pulled de {user_id}: {e}")
            self.conn.rollback()
    
    def get_expired_tokens(self):
        """Obter tokens que expiram em menos de 24h"""
        threshold = int((datetime.utcnow() + timedelta(hours=24)).timestamp())
        try:
            self.cursor.execute("""
                SELECT * FROM oauth_users WHERE expires_at < ?
            """, (threshold,))
            return [dict(row) for row in self.cursor.fetchall()]
        except Exception as e:
            logger.error(f"Erro ao buscar tokens expirados: {e}")
            return []
    
    # ==================== TICKETS ====================
    
    def create_ticket(self, channel_id, user_id, ticket_type):
        """Criar novo ticket"""
        try:
            self.cursor.execute("""
                INSERT INTO tickets (channel_id, user_id, type, created_at)
                VALUES (?, ?, ?, ?)
            """, (channel_id, user_id, ticket_type, int(datetime.utcnow().timestamp())))
            self.conn.commit()
            self.increment_stat('tickets_opened')
            return self.cursor.lastrowid
        except Exception as e:
            logger.error(f"Erro ao criar ticket: {e}")
            self.conn.rollback()
            return None
    
    def get_ticket(self, channel_id):
        """Obter ticket por canal"""
        try:
            self.cursor.execute("SELECT * FROM tickets WHERE channel_id = ?", (channel_id,))
            row = self.cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Erro ao buscar ticket {channel_id}: {e}")
            return None
    
    def close_ticket(self, channel_id, closed_by, transcript):
        """Fechar ticket"""
        try:
            self.cursor.execute("""
                UPDATE tickets 
                SET status = 'closed', closed_at = ?, closed_by = ?, transcript = ?
                WHERE channel_id = ?
            """, (int(datetime.utcnow().timestamp()), closed_by, transcript, channel_id))
            self.conn.commit()
            self.increment_stat('tickets_closed')
        except Exception as e:
            logger.error(f"Erro ao fechar ticket {channel_id}: {e}")
            self.conn.rollback()
    
    def rate_ticket(self, ticket_id, rating, service_rating=None, product_rating=None, feedback=None):
        """Avaliar ticket"""
        try:
            self.cursor.execute("""
                INSERT INTO ratings 
                (ticket_id, rating, service_rating, product_rating, feedback, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ticket_id, rating, service_rating, product_rating, feedback, 
                  int(datetime.utcnow().timestamp())))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Erro ao avaliar ticket {ticket_id}: {e}")
            self.conn.rollback()
    
    def get_user_tickets(self, user_id):
        """Obter tickets de um usuário"""
        try:
            self.cursor.execute("""
                SELECT * FROM tickets WHERE user_id = ? ORDER BY created_at DESC
            """, (user_id,))
            return [dict(row) for row in self.cursor.fetchall()]
        except Exception as e:
            logger.error(f"Erro ao buscar tickets de {user_id}: {e}")
            return []
    
    # ==================== CONFIG ====================
    
    def get_config(self, guild_id):
        """Obter configurações do servidor"""
        try:
            self.cursor.execute("SELECT * FROM config WHERE guild_id = ?", (guild_id,))
            row = self.cursor.fetchone()
            
            if row:
                try:
                    config_data = json.loads(row['config_data'])
                    return config_data
                except:
                    return {}
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar config de {guild_id}: {e}")
            return None
    
    def set_config(self, guild_id, key, value):
        """Definir configuração específica"""
        try:
            current_config = self.get_config(guild_id) or {}
            current_config[key] = value
            current_config['updated_at'] = int(datetime.utcnow().timestamp())
            
            config_json = json.dumps(current_config)
            
            self.cursor.execute("""
                INSERT OR REPLACE INTO config (guild_id, config_data, updated_at)
                VALUES (?, ?, ?)
            """, (guild_id, config_json, current_config['updated_at']))
            
            self.conn.commit()
        except Exception as e:
            logger.error(f"Erro ao salvar config de {guild_id}: {e}")
            self.conn.rollback()
    
    def set_full_config(self, guild_id, config_dict):
        """Definir configuração completa"""
        try:
            config_dict['updated_at'] = int(datetime.utcnow().timestamp())
            config_json = json.dumps(config_dict)
            
            self.cursor.execute("""
                INSERT OR REPLACE INTO config (guild_id, config_data, updated_at)
                VALUES (?, ?, ?)
            """, (guild_id, config_json, config_dict['updated_at']))
            
            self.conn.commit()
        except Exception as e:
            logger.error(f"Erro ao salvar full config de {guild_id}: {e}")
            self.conn.rollback()
    
    # ==================== BLACKLIST ====================
    
    def add_to_blacklist(self, user_id, reason, added_by):
        """Adicionar à blacklist"""
        try:
            self.cursor.execute("""
                INSERT OR REPLACE INTO blacklist (user_id, reason, added_by, added_at)
                VALUES (?, ?, ?, ?)
            """, (user_id, reason, added_by, int(datetime.utcnow().timestamp())))
            self.conn.commit()
            self.add_log('blacklist', user_id, None, 'added', reason)
        except Exception as e:
            logger.error(f"Erro ao adicionar {user_id} à blacklist: {e}")
            self.conn.rollback()
    
    def remove_from_blacklist(self, user_id):
        """Remover da blacklist"""
        try:
            self.cursor.execute("DELETE FROM blacklist WHERE user_id = ?", (user_id,))
            self.conn.commit()
            self.add_log('blacklist', user_id, None, 'removed', 'Removido da blacklist')
        except Exception as e:
            logger.error(f"Erro ao remover {user_id} da blacklist: {e}")
            self.conn.rollback()
    
    def is_blacklisted(self, user_id):
        """Verificar se está na blacklist"""
        try:
            self.cursor.execute("SELECT * FROM blacklist WHERE user_id = ?", (user_id,))
            return self.cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Erro ao verificar blacklist de {user_id}: {e}")
            return False
    
    def get_all_blacklisted(self):
        """Obter todos da blacklist"""
        try:
            self.cursor.execute("SELECT * FROM blacklist")
            return [dict(row) for row in self.cursor.fetchall()]
        except Exception as e:
            logger.error(f"Erro ao buscar blacklist: {e}")
            return []
    
    # ==================== LOGS ====================
    
    def add_log(self, log_type, user_id, guild_id, action, details):
        """Adicionar log"""
        try:
            self.cursor.execute("""
                INSERT INTO logs (type, user_id, guild_id, action, details, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (log_type, user_id, guild_id, action, details, 
                  int(datetime.utcnow().timestamp())))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Erro ao adicionar log: {e}")
            self.conn.rollback()
    
    def get_logs(self, limit=100):
        """Obter logs recentes"""
        try:
            self.cursor.execute("""
                SELECT * FROM logs ORDER BY timestamp DESC LIMIT ?
            """, (limit,))
            return [dict(row) for row in self.cursor.fetchall()]
        except Exception as e:
            logger.error(f"Erro ao buscar logs: {e}")
            return []
    
    # ==================== ESTATÍSTICAS ====================
    
    def increment_stat(self, stat_type):
        """Incrementar estatística do dia"""
        try:
            today = datetime.utcnow().date().isoformat()
            
            self.cursor.execute("SELECT * FROM stats WHERE date = ?", (today,))
            if self.cursor.fetchone():
                self.cursor.execute(f"""
                    UPDATE stats SET {stat_type} = {stat_type} + 1 WHERE date = ?
                """, (today,))
            else:
                self.cursor.execute(f"""
                    INSERT INTO stats (date, {stat_type}) VALUES (?, 1)
                """, (today,))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Erro ao incrementar stat {stat_type}: {e}")
            self.conn.rollback()
    
    def get_stats(self, days=7):
        """Obter estatísticas"""
        try:
            self.cursor.execute("""
                SELECT * FROM stats 
                WHERE date >= date('now', '-' || ? || ' days')
                ORDER BY date DESC
            """, (days,))
            
            stats_list = [dict(row) for row in self.cursor.fetchall()]
            
            total_users = len(self.get_all_oauth_users())
            total_blacklisted = len(self.get_all_blacklisted())
            
            self.cursor.execute("SELECT COUNT(*) as total FROM tickets")
            total_tickets = self.cursor.fetchone()['total']
            
            return {
                'total_users': total_users,
                'total_blacklisted': total_blacklisted,
                'total_tickets': total_tickets,
                'daily_stats': stats_list
            }
        except Exception as e:
            logger.error(f"Erro ao buscar stats: {e}")
            return {
                'total_users': 0,
                'total_blacklisted': 0,
                'total_tickets': 0,
                'daily_stats': []
            }
    
    # ==================== BACKUP ====================
    
    def backup(self):
        """Criar backup do banco de dados"""
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        backup_path = f'backups/backup_{timestamp}.db'
        
        try:
            # Forçar sincronização antes do backup
            self.conn.commit()
            
            # Fazer checkpoint do WAL
            self.cursor.execute("PRAGMA wal_checkpoint(FULL)")
            
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"💾 Backup criado: {backup_path}")
            
            # Manter apenas últimos 30 backups
            backups = sorted(
                [f for f in os.listdir('backups') if f.startswith('backup_') and f.endswith('.db')],
                reverse=True
            )
            for old_backup in backups[30:]:
                try:
                    os.remove(os.path.join('backups', old_backup))
                    logger.info(f"🗑️ Backup antigo removido: {old_backup}")
                except:
                    pass
                
            return backup_path
        except Exception as e:
            logger.error(f"❌ Erro ao criar backup: {e}")
            return None
    
    def get_all_backups(self):
        """Obter lista de todos os backups"""
        try:
            backups = []
            for filename in os.listdir('backups'):
                if filename.startswith('backup_') and filename.endswith('.db'):
                    filepath = os.path.join('backups', filename)
                    size = os.path.getsize(filepath)
                    mtime = os.path.getmtime(filepath)
                    
                    backups.append({
                        'filename': filename,
                        'filepath': filepath,
                        'size': size,
                        'size_mb': round(size / (1024 * 1024), 2),
                        'created_at': datetime.fromtimestamp(mtime).isoformat()
                    })
            
            return sorted(backups, key=lambda x: x['created_at'], reverse=True)
        except Exception as e:
            logger.error(f"Erro ao listar backups: {e}")
            return []
    
    def export_json(self):
        """Exportar dados para JSON"""
        try:
            data = {
                'exported_at': datetime.utcnow().isoformat(),
                'oauth_users': self.get_all_oauth_users(),
                'tickets': self.get_all_tickets(),
                'blacklist': self.get_all_blacklisted(),
                'stats': self.get_stats(30)
            }
            
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            json_path = f'backups/export_{timestamp}.json'
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"📄 Exportado para JSON: {json_path}")
            return json_path
        except Exception as e:
            logger.error(f"Erro ao exportar JSON: {e}")
            return None
    
    def get_all_tickets(self):
        """Obter todos os tickets"""
        try:
            self.cursor.execute("SELECT * FROM tickets ORDER BY created_at DESC")
            return [dict(row) for row in self.cursor.fetchall()]
        except Exception as e:
            logger.error(f"Erro ao buscar todos tickets: {e}")
            return []
    
    def close(self):
        """Fechar conexão"""
        try:
            self.conn.commit()
            self.conn.close()
            logger.info("🔒 Banco de dados fechado")
        except Exception as e:
            logger.error(f"Erro ao fechar banco: {e}")
