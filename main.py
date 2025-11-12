import discord
from discord.ext import commands, tasks
import os
import asyncio
from dotenv import load_dotenv
from datetime import datetime
import logging

# Importar módulos
from database import Database
from web_server import WebServer
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
        self.web_server = None
        self.start_time = datetime.utcnow()
        
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
        
        logger.info("✅ Setup concluído!")
    
    @tasks.loop(minutes=30)
    async def background_tasks(self):
        """Tarefas periódicas"""
        try:
            # Verificar e renovar tokens OAuth2 expirados
            expired = self.db.get_expired_tokens()
            for user_data in expired:
                from cogs.oauth import refresh_user_token
                await refresh_user_token(self, user_data['user_id'])
            
            # Backup automático a cada 6 horas
            if datetime.utcnow().hour % 6 == 0:
                self.db.backup()
                logger.info("💾 Backup automático realizado")
                
        except Exception as e:
            logger.error(f"Erro nas tarefas de background: {e}")
    
    @background_tasks.before_loop
    async def before_background_tasks(self):
        await self.wait_until_ready()
    
    async def on_ready(self):
        logger.info(f"✅ Bot online como {self.user.name}#{self.user.discriminator}")
        logger.info(f"📊 Conectado em {len(self.guilds)} servidores")
        logger.info(f"👥 Servindo {len(self.users)} usuários")
        
        # Estatísticas do banco
        stats = self.db.get_stats()
        logger.info(f"🔐 {stats['total_users']} usuários com OAuth2")
        logger.info(f"🎫 {stats['total_tickets']} tickets registrados")
        
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
                name=f"{len(self.guilds)} servidores | /ajuda"
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

def main():
    """Função principal"""
    # Verificar variáveis de ambiente
    required_vars = ['BOT_TOKEN', 'CLIENT_ID', 'CLIENT_SECRET', 'GUILD_ID', 'OWNER_ID']
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        logger.error(f"❌ Variáveis de ambiente faltando: {', '.join(missing)}")
        return
    
    bot = PandaBot()
    
    try:
        bot.run(os.getenv('BOT_TOKEN'))
    except KeyboardInterrupt:
        logger.info("🔄 Bot desligado pelo usuário")
    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}")
    finally:
        bot.db.close()

if __name__ == "__main__":
    main()