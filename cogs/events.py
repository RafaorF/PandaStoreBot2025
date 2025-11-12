import discord
from discord.ext import commands
import logging
from utils import EmbedBuilder, Config

logger = logging.getLogger('PandaBot.Events')

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Evento quando membro entra no servidor"""
        
        config = self.bot.db.get_config(str(member.guild.id))
        
        if not config or not config.get('welcome_channel'):
            return
        
        welcome_channel = member.guild.get_channel(int(config['welcome_channel']))
        
        if not welcome_channel:
            return
        
        # Mensagem personalizada ou padrão
        message = config.get('welcome_message', 'Bem-vindo(a) ao servidor, {user}!')
        message = message.replace('{user}', member.mention).replace('{server}', member.guild.name)
        
        # Criar embed de boas-vindas
        embed = EmbedBuilder.create_embed(
            f"👋 Bem-vindo(a) ao {member.guild.name}!",
            message,
            color=Config.COLORS['success'],
            thumbnail=member.display_avatar.url,
            image=member.guild.banner.url if member.guild.banner else None,
            fields=[
                {
                    "name": "👤 Membro",
                    "value": f"{member.mention}\n{member.name}",
                    "inline": True
                },
                {
                    "name": "📊 Membro #",
                    "value": str(member.guild.member_count),
                    "inline": True
                },
                {
                    "name": "📅 Conta Criada",
                    "value": f"<t:{int(member.created_at.timestamp())}:R>",
                    "inline": True
                }
            ],
            footer_icon=member.guild.icon.url if member.guild.icon else None
        )
        
        try:
            await welcome_channel.send(f"{member.mention}", embed=embed)
            logger.info(f"✅ Boas-vindas enviadas para {member.name}")
        except Exception as e:
            logger.error(f"Erro ao enviar boas-vindas: {e}")
        
        # Log
        log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
        if log_channel:
            log_embed = EmbedBuilder.info(
                "👋 Membro Entrou",
                f"**{member.mention}** entrou no servidor!",
                thumbnail=member.display_avatar.url,
                fields=[
                    {"name": "ID", "value": str(member.id), "inline": True},
                    {"name": "Conta Criada", "value": f"<t:{int(member.created_at.timestamp())}:R>", "inline": True},
                    {"name": "Total de Membros", "value": str(member.guild.member_count), "inline": True}
                ],
                footer_icon=member.guild.icon.url if member.guild.icon else None
            )
            
            try:
                await log_channel.send(embed=log_embed)
            except:
                pass
    
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Evento quando membro sai do servidor"""
        
        config = self.bot.db.get_config(str(member.guild.id))
        
        # Mensagem de despedida
        if config and config.get('goodbye_channel'):
            goodbye_channel = member.guild.get_channel(int(config['goodbye_channel']))
            
            if goodbye_channel:
                embed = EmbedBuilder.create_embed(
                    f"👋 Até Logo!",
                    f"**{member.name}** saiu do servidor.",
                    color=Config.COLORS['warning'],
                    thumbnail=member.display_avatar.url,
                    fields=[
                        {
                            "name": "👤 Membro",
                            "value": f"{member.name}\n#{member.discriminator}" if member.discriminator != "0" else member.name,
                            "inline": True
                        },
                        {
                            "name": "📊 Membros Restantes",
                            "value": str(member.guild.member_count),
                            "inline": True
                        }
                    ],
                    footer_icon=member.guild.icon.url if member.guild.icon else None
                )
                
                try:
                    await goodbye_channel.send(embed=embed)
                except Exception as e:
                    logger.error(f"Erro ao enviar despedida: {e}")
        
        # Log
        log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
        if log_channel:
            log_embed = EmbedBuilder.warning(
                "👋 Membro Saiu",
                f"**{member.name}** saiu do servidor!",
                thumbnail=member.display_avatar.url,
                fields=[
                    {"name": "ID", "value": str(member.id), "inline": True},
                    {"name": "Entrou em", "value": f"<t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "Desconhecido", "inline": True},
                    {"name": "Total de Membros", "value": str(member.guild.member_count), "inline": True}
                ],
                footer_icon=member.guild.icon.url if member.guild.icon else None
            )
            
            try:
                await log_channel.send(embed=log_embed)
            except:
                pass
        
        # Verificar se tem OAuth2 e auto-puxar está ativo
        oauth_data = self.bot.db.get_oauth_user(str(member.id))
        
        if oauth_data and config and config.get('auto_pull'):
            logger.info(f"🔄 {member.name} tem OAuth2 - tentando puxar de volta...")
            
            # Tentar puxar de volta
            try:
                oauth_cog = self.bot.get_cog('OAuth')
                if oauth_cog:
                    # Verificar e renovar token se necessário
                    access_token = oauth_data['access_token']
                    
                    # Tentar adicionar de volta
                    import aiohttp
                    headers = {
                        'Authorization': f'Bot {self.bot.http.token}',
                        'Content-Type': 'application/json'
                    }
                    
                    data = {'access_token': access_token}
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.put(
                            f'https://discord.com/api/v10/guilds/{member.guild.id}/members/{member.id}',
                            headers=headers,
                            json=data
                        ) as resp:
                            if resp.status in [200, 201, 204]:
                                logger.info(f"✅ {member.name} foi puxado de volta com sucesso!")
                                
                                # Notificar em logs
                                if log_channel:
                                    pull_embed = EmbedBuilder.success(
                                        "🔄 Membro Puxado de Volta",
                                        f"**{member.name}** foi automaticamente adicionado de volta ao servidor via OAuth2!",
                                        thumbnail=member.display_avatar.url,
                                        footer_icon=member.guild.icon.url if member.guild.icon else None
                                    )
                                    await log_channel.send(embed=pull_embed)
                                
                                # Atualizar banco
                                self.bot.db.update_last_pulled(str(member.id))
                                self.bot.db.increment_stat('successful_pulls')
                            else:
                                logger.warning(f"⚠️ Falha ao puxar {member.name}: Status {resp.status}")
                                self.bot.db.increment_stat('failed_pulls')
            
            except Exception as e:
                logger.error(f"Erro ao tentar puxar {member.name}: {e}")
                self.bot.db.increment_stat('failed_pulls')
    
    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        """Evento quando membro é banido"""
        
        log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
        if not log_channel:
            return
        
        # Tentar obter informações do ban
        try:
            ban_entry = await guild.fetch_ban(user)
            reason = ban_entry.reason or "Nenhum motivo fornecido"
        except:
            reason = "Nenhum motivo fornecido"
        
        embed = EmbedBuilder.error(
            "🔨 Membro Banido",
            f"**{user.name}** foi banido do servidor!",
            thumbnail=user.display_avatar.url,
            fields=[
                {"name": "ID", "value": str(user.id), "inline": True},
                {"name": "Motivo", "value": reason, "inline": False}
            ],
            footer_icon=guild.icon.url if guild.icon else None
        )
        
        try:
            await log_channel.send(embed=embed)
        except:
            pass
    
    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        """Evento quando membro é desbanido"""
        
        log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
        if not log_channel:
            return
        
        embed = EmbedBuilder.success(
            "✅ Membro Desbanido",
            f"**{user.name}** foi desbanido do servidor!",
            thumbnail=user.display_avatar.url,
            fields=[
                {"name": "ID", "value": str(user.id), "inline": True}
            ],
            footer_icon=guild.icon.url if guild.icon else None
        )
        
        try:
            await log_channel.send(embed=embed)
        except:
            pass
    
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        """Evento quando canal é criado"""
        
        log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
        if not log_channel or channel.id == log_channel.id:
            return
        
        embed = EmbedBuilder.info(
            "📁 Canal Criado",
            f"Canal **{channel.name}** foi criado!",
            fields=[
                {"name": "Tipo", "value": str(channel.type), "inline": True},
                {"name": "ID", "value": str(channel.id), "inline": True}
            ],
            footer_icon=channel.guild.icon.url if channel.guild.icon else None
        )
        
        try:
            await log_channel.send(embed=embed)
        except:
            pass
    
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Evento quando canal é deletado"""
        
        log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
        if not log_channel:
            return
        
        embed = EmbedBuilder.warning(
            "🗑️ Canal Deletado",
            f"Canal **{channel.name}** foi deletado!",
            fields=[
                {"name": "Tipo", "value": str(channel.type), "inline": True},
                {"name": "ID", "value": str(channel.id), "inline": True}
            ],
            footer_icon=channel.guild.icon.url if channel.guild.icon else None
        )
        
        try:
            await log_channel.send(embed=embed)
        except:
            pass
    
    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        """Evento quando cargo é criado"""
        
        log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
        if not log_channel:
            return
        
        embed = EmbedBuilder.info(
            "👑 Cargo Criado",
            f"Cargo {role.mention} foi criado!",
            fields=[
                {"name": "ID", "value": str(role.id), "inline": True},
                {"name": "Cor", "value": str(role.color), "inline": True}
            ],
            footer_icon=role.guild.icon.url if role.guild.icon else None
        )
        
        try:
            await log_channel.send(embed=embed)
        except:
            pass
    
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        """Evento quando cargo é deletado"""
        
        log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
        if not log_channel:
            return
        
        embed = EmbedBuilder.warning(
            "🗑️ Cargo Deletado",
            f"Cargo **{role.name}** foi deletado!",
            fields=[
                {"name": "ID", "value": str(role.id), "inline": True}
            ],
            footer_icon=role.guild.icon.url if role.guild.icon else None
        )
        
        try:
            await log_channel.send(embed=embed)
        except:
            pass

async def setup(bot):
    await bot.add_cog(Events(bot))