import os
import shutil
import json
import logging
from datetime import datetime
from pathlib import Path
import asyncio

logger = logging.getLogger('PandaBot.BackupManager')

class BackupManager:
    """Gerenciador de backups com persistência garantida"""
    
    def __init__(self, db):
        self.db = db
        self.backup_dir = Path('backups')
        self.data_dir = Path('data')
        self.persistent_backup_file = self.data_dir / 'oauth_backup.json'
        
        # Criar diretórios
        self.backup_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)
        
        logger.info("💾 BackupManager inicializado")
    
    def create_oauth_snapshot(self):
        """Criar snapshot JSON dos dados OAuth2 - SEMPRE atualizado"""
        try:
            oauth_users = self.db.get_all_oauth_users()
            tickets = self.db.get_all_tickets()
            blacklist = self.db.get_all_blacklisted()
            
            snapshot = {
                'timestamp': datetime.utcnow().isoformat(),
                'version': '1.0',
                'oauth_users': oauth_users,
                'tickets': tickets,
                'blacklist': blacklist,
                'stats': self.db.get_stats()
            }
            
            # Salvar snapshot
            with open(self.persistent_backup_file, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Snapshot OAuth2 criado: {len(oauth_users)} usuários")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao criar snapshot: {e}")
            return False
    
    def restore_from_snapshot(self):
        """Restaurar dados do snapshot JSON"""
        if not self.persistent_backup_file.exists():
            logger.warning("⚠️ Nenhum snapshot encontrado para restaurar")
            return False
        
        try:
            with open(self.persistent_backup_file, 'r', encoding='utf-8') as f:
                snapshot = json.load(f)
            
            # Restaurar OAuth2 users
            restored_count = 0
            for user_data in snapshot.get('oauth_users', []):
                try:
                    self.db.add_oauth_user(
                        user_data['user_id'],
                        user_data['access_token'],
                        user_data['refresh_token'],
                        user_data['expires_at']
                    )
                    restored_count += 1
                except Exception as e:
                    logger.error(f"Erro ao restaurar usuário {user_data.get('user_id')}: {e}")
            
            logger.info(f"✅ Snapshot restaurado: {restored_count} usuários OAuth2")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao restaurar snapshot: {e}")
            return False
    
    def create_full_backup(self):
        """Criar backup completo do banco SQLite"""
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        backup_path = self.backup_dir / f'backup_{timestamp}.db'
        
        try:
            # Forçar commit
            self.db.conn.commit()
            
            # Checkpoint WAL
            self.db.cursor.execute("PRAGMA wal_checkpoint(FULL)")
            
            # Copiar arquivo
            shutil.copy2(self.db.db_path, backup_path)
            
            # Também criar snapshot JSON
            self.create_oauth_snapshot()
            
            logger.info(f"💾 Backup completo criado: {backup_path}")
            
            # Limpar backups antigos (manter últimos 10)
            self._cleanup_old_backups(keep=10)
            
            return str(backup_path)
        except Exception as e:
            logger.error(f"❌ Erro ao criar backup: {e}")
            return None
    
    def _cleanup_old_backups(self, keep=10):
        """Remover backups antigos"""
        try:
            backups = sorted(
                [f for f in self.backup_dir.glob('backup_*.db')],
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            for old_backup in backups[keep:]:
                old_backup.unlink()
                logger.info(f"🗑️ Backup antigo removido: {old_backup.name}")
        except Exception as e:
            logger.error(f"Erro ao limpar backups: {e}")
    
    async def auto_backup_loop(self, interval_minutes=30):
        """Loop de backup automático"""
        while True:
            try:
                await asyncio.sleep(interval_minutes * 60)
                self.create_oauth_snapshot()
                logger.info("🔄 Backup automático executado")
            except Exception as e:
                logger.error(f"Erro no loop de backup: {e}")
                await asyncio.sleep(60)  # Esperar 1 minuto em caso de erro
    
    def verify_integrity(self):
        """Verificar integridade do banco de dados"""
        try:
            self.db.cursor.execute("PRAGMA integrity_check")
            result = self.db.cursor.fetchone()[0]
            
            if result == "ok":
                logger.info("✅ Integridade do banco verificada: OK")
                return True
            else:
                logger.error(f"❌ Problema de integridade: {result}")
                return False
        except Exception as e:
            logger.error(f"❌ Erro ao verificar integridade: {e}")
            return False