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
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        
        self._create_tables()
        logger.info("✅ Banco de dados inicializado")
    
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
        
        # Tabela de configurações (CORRIGIDA - suporta JSON)
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
    
    # ==================== OAUTH2 ====================
    
    def add_oauth_user(self, user_id, access_token, refresh_token, expires_at):
        """Adicionar/atualizar usuário OAuth2"""
        self.cursor.execute("""
            INSERT OR REPLACE INTO oauth_users 
            (user_id, access_token, refresh_token, expires_at, added_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, access_token, refresh_token, expires_at, int(datetime.utcnow().timestamp())))
        self.conn.commit()
        self.add_log('oauth', user_id, None, 'registered', 'OAuth2 autorizado')
        self.increment_stat('oauth_registrations')
    
    def get_oauth_user(self, user_id):
        """Obter dados OAuth2 de um usuário"""
        self.cursor.execute("SELECT * FROM oauth_users WHERE user_id = ?", (user_id,))
        row = self.cursor.fetchone()
        return dict(row) if row else None
    
    def get_all_oauth_users(self):
        """Obter todos os usuários OAuth2"""
        self.cursor.execute("SELECT * FROM oauth_users")
        return [dict(row) for row in self.cursor.fetchall()]
    
    def remove_oauth_user(self, user_id):
        """Remover usuário OAuth2"""
        self.cursor.execute("DELETE FROM oauth_users WHERE user_id = ?", (user_id,))
        self.conn.commit()
        self.add_log('oauth', user_id, None, 'removed', 'OAuth2 revogado')
    
    def update_last_pulled(self, user_id):
        """Atualizar timestamp do último pull"""
        self.cursor.execute("""
            UPDATE oauth_users SET last_pulled = ? WHERE user_id = ?
        """, (int(datetime.utcnow().timestamp()), user_id))
        self.conn.commit()
    
    def get_expired_tokens(self):
        """Obter tokens que expiram em menos de 24h"""
        threshold = int((datetime.utcnow() + timedelta(hours=24)).timestamp())
        self.cursor.execute("""
            SELECT * FROM oauth_users WHERE expires_at < ?
        """, (threshold,))
        return [dict(row) for row in self.cursor.fetchall()]
    
    # ==================== TICKETS ====================
    
    def create_ticket(self, channel_id, user_id, ticket_type):
        """Criar novo ticket"""
        self.cursor.execute("""
            INSERT INTO tickets (channel_id, user_id, type, created_at)
            VALUES (?, ?, ?, ?)
        """, (channel_id, user_id, ticket_type, int(datetime.utcnow().timestamp())))
        self.conn.commit()
        self.increment_stat('tickets_opened')
        return self.cursor.lastrowid
    
    def get_ticket(self, channel_id):
        """Obter ticket por canal"""
        self.cursor.execute("SELECT * FROM tickets WHERE channel_id = ?", (channel_id,))
        row = self.cursor.fetchone()
        return dict(row) if row else None
    
    def close_ticket(self, channel_id, closed_by, transcript):
        """Fechar ticket"""
        self.cursor.execute("""
            UPDATE tickets 
            SET status = 'closed', closed_at = ?, closed_by = ?, transcript = ?
            WHERE channel_id = ?
        """, (int(datetime.utcnow().timestamp()), closed_by, transcript, channel_id))
        self.conn.commit()
        self.increment_stat('tickets_closed')
    
    def rate_ticket(self, ticket_id, rating, service_rating=None, product_rating=None, feedback=None):
        """Avaliar ticket"""
        self.cursor.execute("""
            INSERT INTO ratings 
            (ticket_id, rating, service_rating, product_rating, feedback, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ticket_id, rating, service_rating, product_rating, feedback, 
              int(datetime.utcnow().timestamp())))
        self.conn.commit()
    
    def get_user_tickets(self, user_id):
        """Obter tickets de um usuário"""
        self.cursor.execute("""
            SELECT * FROM tickets WHERE user_id = ? ORDER BY created_at DESC
        """, (user_id,))
        return [dict(row) for row in self.cursor.fetchall()]
    
    # ==================== CONFIG (CORRIGIDO) ====================
    
    def get_config(self, guild_id):
        """Obter configurações do servidor"""
        self.cursor.execute("SELECT * FROM config WHERE guild_id = ?", (guild_id,))
        row = self.cursor.fetchone()
        
        if row:
            try:
                config_data = json.loads(row['config_data'])
                return config_data
            except:
                return {}
        return None
    
    def set_config(self, guild_id, key, value):
        """Definir configuração específica"""
        # Obter config atual
        current_config = self.get_config(guild_id) or {}
        
        # Atualizar chave
        current_config[key] = value
        current_config['updated_at'] = int(datetime.utcnow().timestamp())
        
        # Salvar
        config_json = json.dumps(current_config)
        
        self.cursor.execute("""
            INSERT OR REPLACE INTO config (guild_id, config_data, updated_at)
            VALUES (?, ?, ?)
        """, (guild_id, config_json, current_config['updated_at']))
        
        self.conn.commit()
    
    def set_full_config(self, guild_id, config_dict):
        """Definir configuração completa"""
        config_dict['updated_at'] = int(datetime.utcnow().timestamp())
        config_json = json.dumps(config_dict)
        
        self.cursor.execute("""
            INSERT OR REPLACE INTO config (guild_id, config_data, updated_at)
            VALUES (?, ?, ?)
        """, (guild_id, config_json, config_dict['updated_at']))
        
        self.conn.commit()
    
    # ==================== BLACKLIST ====================
    
    def add_to_blacklist(self, user_id, reason, added_by):
        """Adicionar à blacklist"""
        self.cursor.execute("""
            INSERT OR REPLACE INTO blacklist (user_id, reason, added_by, added_at)
            VALUES (?, ?, ?, ?)
        """, (user_id, reason, added_by, int(datetime.utcnow().timestamp())))
        self.conn.commit()
        self.add_log('blacklist', user_id, None, 'added', reason)
    
    def remove_from_blacklist(self, user_id):
        """Remover da blacklist"""
        self.cursor.execute("DELETE FROM blacklist WHERE user_id = ?", (user_id,))
        self.conn.commit()
        self.add_log('blacklist', user_id, None, 'removed', 'Removido da blacklist')
    
    def is_blacklisted(self, user_id):
        """Verificar se está na blacklist"""
        self.cursor.execute("SELECT * FROM blacklist WHERE user_id = ?", (user_id,))
        return self.cursor.fetchone() is not None
    
    def get_all_blacklisted(self):
        """Obter todos da blacklist"""
        self.cursor.execute("SELECT * FROM blacklist")
        return [dict(row) for row in self.cursor.fetchall()]
    
    # ==================== LOGS ====================
    
    def add_log(self, log_type, user_id, guild_id, action, details):
        """Adicionar log"""
        self.cursor.execute("""
            INSERT INTO logs (type, user_id, guild_id, action, details, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (log_type, user_id, guild_id, action, details, 
              int(datetime.utcnow().timestamp())))
        self.conn.commit()
    
    def get_logs(self, limit=100):
        """Obter logs recentes"""
        self.cursor.execute("""
            SELECT * FROM logs ORDER BY timestamp DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in self.cursor.fetchall()]
    
    # ==================== ESTATÍSTICAS ====================
    
    def increment_stat(self, stat_type):
        """Incrementar estatística do dia"""
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
    
    def get_stats(self, days=7):
        """Obter estatísticas"""
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
    
    # ==================== BACKUP ====================
    
    def backup(self):
        """Criar backup do banco de dados"""
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        backup_path = f'backups/backup_{timestamp}.db'
        
        try:
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"💾 Backup criado: {backup_path}")
            
            # Manter apenas últimos 7 backups
            backups = sorted(
                [f for f in os.listdir('backups') if f.startswith('backup_')],
                reverse=True
            )
            for old_backup in backups[7:]:
                os.remove(os.path.join('backups', old_backup))
                
            return backup_path
        except Exception as e:
            logger.error(f"Erro ao criar backup: {e}")
            return None
    
    def export_json(self):
        """Exportar dados para JSON"""
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
    
    def get_all_tickets(self):
        """Obter todos os tickets"""
        self.cursor.execute("SELECT * FROM tickets ORDER BY created_at DESC")
        return [dict(row) for row in self.cursor.fetchall()]
    
    def close(self):
        """Fechar conexão"""
        self.conn.close()
        logger.info("🔒 Banco de dados fechado")