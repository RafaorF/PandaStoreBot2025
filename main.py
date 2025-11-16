import discord
from discord.ext import commands, tasks
import os
import asyncio
from dotenv import load_dotenv
from datetime import datetime, timezone
import logging
import signal
import sys

# Importar módulos
from database import Database
from web_server import WebServer
from backup_manager import BackupManager
from utils import Logger, Config

load_dotenv()

# Configurar logging
Logger.setup()
logger = logging.getLogger('PandaBot')

class PandaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(
            command_prefix=commands.when_mentioned_or(os.getenv('PREFIX', '!')),
            intents=intents,
            help_command=None
        )
        
        self.db = Database()
        self.backup_manager = BackupManager(self.db)
        self.web_server = None
        self.start_time = datetime.now(timezone.utc)
        
        # 🔄 VERIFICAR E RESTAURAR DADOS NO INÍCIO
        logger.info("🔍 Verificando dados existentes...")
        oauth_count = len(self.db.get_all_oauth_users())
        
        if oauth_count == 0:
            logger.warning("⚠️ Nenhum dado OAuth2 no banco, tentando restaurar do snapshot...")
            if self.backup_manager.restore_from_snapshot():
                oauth_count = len(self.db.get_all_oauth_users())
                logger.info(f"✅ {oauth_count} usuários OAuth2 restaurados do snapshot!")
            else:
                logger.warning("⚠️ Nenhum snapshot disponível para restaurar")
        else:
            logger.info(f"✅ {oauth_count} usuários OAuth2 carregados do banco")
        
        # Verificar integridade
        self.backup_manager.verify_integrity()
        
        # Criar backup inicial
        logger.info("💾 Criando backup inicial...")
        self.backup_manager.create_full_backup()
        
    async def setup_hook(self):
        """Carregar cogs e inicializar componentes"""
        logger.info("🔄 Carregando extensões...")
        
        extensions = [
            'cogs.oauth',
            'cogs.tickets',
            'cogs.moderation',
            'cogs.utility',
            'cogs.config',
            'cogs.verification',
            'cogs.announcements',
            'cogs.polls',
            'cogs.events',
            'cogs.payments'
        ]
        
        for ext in extensions:
            try:
                await self.load_extension(ext)
                logger.info(f"✅ {ext} carregado")
            except Exception as e:
                logger.error(f"❌ Erro ao carregar {ext}: {e}")
        
        # Iniciar servidor web
        self.web_server = WebServer(self)
        asyncio.create_task(self.web_server.start())
        
        # Iniciar tarefas de background
        self.background_tasks.start()
        self.snapshot_backup.start()
        self.hourly_backup.start()
        
        logger.info("✅ Setup concluído!")
    
    @tasks.loop(minutes=30)
    async def background_tasks(self):
        """Tarefas periódicas a cada 30 minutos"""
        try:
            # Verificar e renovar tokens OAuth2 expirados
            expired = self.db.get_expired_tokens()
            if expired:
                logger.info(f"🔄 Renovando {len(expired)} tokens expirados...")
                oauth_cog = self.get_cog('OAuth')
                if oauth_cog:
                    for user_data in expired:
                        try:
                            await oauth_cog.refresh_token(user_data['user_id'])
                        except Exception as e:
                            logger.error(f"Erro ao renovar token para {user_data['user_id']}: {e}")
            
            # Log de status
            stats = self.db.get_stats()
            logger.info(f"📊 Status: {stats['total_users']} OAuth2 | {len(self.guilds)} servidores | {len(self.users)} usuários")
                
        except Exception as e:
            logger.error(f"Erro nas tarefas de background: {e}")
    
    @tasks.loop(minutes=10)
    async def snapshot_backup(self):
        """Criar snapshot JSON a cada 10 minutos - CRÍTICO PARA PERSISTÊNCIA"""
        try:
            self.backup_manager.create_oauth_snapshot()
            logger.info("💾 Snapshot OAuth2 atualizado")
        except Exception as e:
            logger.error(f"❌ Erro no snapshot automático: {e}")
    
    @tasks.loop(hours=6)
    async def hourly_backup(self):
        """Backup completo a cada 6 horas"""
        try:
            backup_path = self.backup_manager.create_full_backup()
            if backup_path:
                logger.info(f"💾 Backup completo criado: {backup_path}")
            else:
                logger.warning("⚠️ Falha ao criar backup completo")
        except Exception as e:
            logger.error(f"❌ Erro no backup automático: {e}")
    
    @background_tasks.before_loop
    async def before_background_tasks(self):
        await self.wait_until_ready()
    
    @snapshot_backup.before_loop
    async def before_snapshot_backup(self):
        await self.wait_until_ready()
    
    @hourly_backup.before_loop
    async def before_hourly_backup(self):
        await self.wait_until_ready()
    
    async def on_ready(self):
        logger.info(f"✅ Bot online como {self.user.name}#{self.user.discriminator}")
        logger.info(f"📊 Conectado em {len(self.guilds)} servidores")
        logger.info(f"👥 Servindo {len(self.users)} usuários")
        
        # Estatísticas do banco
        stats = self.db.get_stats()
        logger.info(f"🔐 {stats['total_users']} usuários com OAuth2")
        logger.info(f"🎫 {stats['total_tickets']} tickets registrados")
        logger.info(f"🚫 {stats['total_blacklisted']} usuários na blacklist")
        
        # Verificar integridade dos dados OAuth2
        oauth_users = self.db.get_all_oauth_users()
        logger.info(f"✅ Verificação: {len(oauth_users)} registros OAuth2 carregados do banco")
        
        # Criar snapshot imediato após inicialização
        self.backup_manager.create_oauth_snapshot()
        logger.info("💾 Snapshot inicial criado após inicialização")
        
        # Sincronizar comandos slash
        try:
            synced = await self.tree.sync()
            logger.info(f"✅ {len(synced)} comandos slash sincronizados")
        except Exception as e:
            logger.error(f"Erro ao sincronizar comandos: {e}")
        
        # Status do bot
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} servidores | /oauth"
            ),
            status=discord.Status.online
        )
    
    async def on_command_error(self, ctx, error):
        """Tratamento de erros"""
        if isinstance(error, commands.CommandNotFound):
            return
        
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(embed=discord.Embed(
                title="🚫 Sem Permissão",
                description="Você não tem permissão para usar este comando.",
                color=Config.COLORS['error']
            ))
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(embed=discord.Embed(
                title="⚠️ Argumento Faltando",
                description=f"Argumento obrigatório faltando: `{error.param.name}`",
                color=Config.COLORS['warning']
            ))
        else:
            logger.error(f"Erro no comando {ctx.command}: {error}")
            await ctx.send(embed=discord.Embed(
                title="❌ Erro",
                description="Ocorreu um erro ao executar o comando.",
                color=Config.COLORS['error']
            ))
    
    async def close(self):
        """Fechar bot e salvar dados"""
        logger.info("🔄 Encerrando bot...")
        
        # ✅ BACKUP FINAL CRÍTICO antes de fechar
        logger.info("💾 Criando backup final CRÍTICO...")
        self.backup_manager.create_full_backup()
        
        # Garantir que snapshot está atualizado
        self.backup_manager.create_oauth_snapshot()
        
        # Forçar commit final
        self.db.conn.commit()
        logger.info("✅ Dados salvos com sucesso")
        
        # Fechar banco de dados
        self.db.close()
        
        # Fechar bot
        await super().close()
        logger.info("✅ Bot encerrado com sucesso")

def signal_handler(signum, frame):
    """Handler para sinais de término"""
    logger.info(f"🛑 Recebido sinal {signum}, encerrando...")
    sys.exit(0)

def main():
    """Função principal"""
    # Verificar variáveis de ambiente
    required_vars = ['BOT_TOKEN', 'CLIENT_ID', 'CLIENT_SECRET', 'GUILD_ID', 'OWNER_ID']
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        logger.error(f"❌ Variáveis de ambiente faltando: {', '.join(missing)}")
        return
    
    # Registrar handlers de sinal
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    bot = PandaBot()
    
    try:
        logger.info("🚀 Iniciando bot...")
        bot.run(os.getenv('BOT_TOKEN'))
    except KeyboardInterrupt:
        logger.info("🔄 Bot desligado pelo usuário")
    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}")
    finally:
        # Garantir que o banco seja fechado corretamente
        try:
            if hasattr(bot, 'backup_manager'):
                logger.info("💾 Salvando dados finais...")
                bot.backup_manager.create_full_backup()
                bot.backup_manager.create_oauth_snapshot()
            if hasattr(bot, 'db'):
                bot.db.conn.commit()
                bot.db.close()
        except Exception as e:
            logger.error(f"Erro ao fechar banco: {e}")

if __name__ == "__main__":
    main()