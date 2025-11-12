import discord
from discord.ext import commands
from discord import app_commands
import logging
from datetime import timedelta
from utils import EmbedBuilder, Config, Permissions

logger = logging.getLogger('PandaBot.Moderation')

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="kick", description="Expulsar um membro do servidor")
    @app_commands.describe(member="Membro a ser expulso", reason="Motivo da expulsão")
    @app_commands.check(lambda interaction: Permissions.is_staff(interaction.user))
    async def kick_command(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Não especificado"):
        """Expulsar membro"""
        
        if member.top_role >= interaction.user.top_role:
            embed = EmbedBuilder.error(
                "Erro",
                "Você não pode expulsar este membro (hierarquia de cargos).",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        try:
            # Enviar DM
            try:
                dm_embed = EmbedBuilder.warning(
                    f"Expulso de {interaction.guild.name}",
                    f"**Motivo:** {reason}\n**Moderador:** {interaction.user.name}",
                    thumbnail=interaction.guild.icon.url if interaction.guild.icon else None,
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                await member.send(embed=dm_embed)
            except:
                pass
            
            await member.kick(reason=f"{interaction.user.name}: {reason}")
            
            # Resposta
            embed = EmbedBuilder.success(
                "Membro Expulso",
                f"**{member.mention}** foi expulso do servidor.",
                fields=[
                    {"name": "Motivo", "value": reason, "inline": False},
                    {"name": "Moderador", "value": interaction.user.mention, "inline": True}
                ],
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.response.send_message(embed=embed)
            
            # Log
            log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
            if log_channel:
                log_embed = EmbedBuilder.warning(
                    "👢 Membro Expulso",
                    f"**Membro:** {member.mention}\n**Moderador:** {interaction.user.mention}\n**Motivo:** {reason}",
                    thumbnail=member.display_avatar.url,
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                await log_channel.send(embed=log_embed)
            
            self.bot.db.add_log('moderation', str(member.id), str(interaction.guild.id), 'kick', reason)
            
        except Exception as e:
            logger.error(f"Erro ao expulsar {member}: {e}")
            embed = EmbedBuilder.error("Erro", f"Não foi possível expulsar o membro: {str(e)}", footer_icon=interaction.guild.icon.url if interaction.guild.icon else None)
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="ban", description="Banir um membro do servidor")
    @app_commands.describe(member="Membro a ser banido", reason="Motivo do banimento", delete_days="Dias de mensagens a deletar (0-7)")
    @app_commands.check(lambda interaction: Permissions.is_staff(interaction.user))
    async def ban_command(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Não especificado", delete_days: int = 0):
        """Banir membro"""
        
        if member.top_role >= interaction.user.top_role:
            embed = EmbedBuilder.error("Erro", "Você não pode banir este membro (hierarquia de cargos).", footer_icon=interaction.guild.icon.url if interaction.guild.icon else None)
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        delete_days = max(0, min(7, delete_days))
        
        try:
            # Enviar DM
            try:
                dm_embed = EmbedBuilder.error(
                    f"Banido de {interaction.guild.name}",
                    f"**Motivo:** {reason}\n**Moderador:** {interaction.user.name}",
                    thumbnail=interaction.guild.icon.url if interaction.guild.icon else None,
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                await member.send(embed=dm_embed)
            except:
                pass
            
            await member.ban(reason=f"{interaction.user.name}: {reason}", delete_message_days=delete_days)
            
            embed = EmbedBuilder.success(
                "Membro Banido",
                f"**{member.mention}** foi banido do servidor.",
                fields=[
                    {"name": "Motivo", "value": reason, "inline": False},
                    {"name": "Moderador", "value": interaction.user.mention, "inline": True},
                    {"name": "Mensagens Deletadas", "value": f"{delete_days} dias", "inline": True}
                ],
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.response.send_message(embed=embed)
            
            # Log
            log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
            if log_channel:
                log_embed = EmbedBuilder.error(
                    "🔨 Membro Banido",
                    f"**Membro:** {member.mention}\n**Moderador:** {interaction.user.mention}\n**Motivo:** {reason}",
                    thumbnail=member.display_avatar.url,
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                await log_channel.send(embed=log_embed)
            
            self.bot.db.add_log('moderation', str(member.id), str(interaction.guild.id), 'ban', reason)
            
        except Exception as e:
            logger.error(f"Erro ao banir {member}: {e}")
            embed = EmbedBuilder.error("Erro", f"Não foi possível banir o membro: {str(e)}", footer_icon=interaction.guild.icon.url if interaction.guild.icon else None)
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="unban", description="Desbanir um usuário")
    @app_commands.describe(user_id="ID do usuário a ser desbanido")
    @app_commands.check(lambda interaction: Permissions.is_staff(interaction.user))
    async def unban_command(self, interaction: discord.Interaction, user_id: str):
        """Desbanir usuário"""
        
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user, reason=f"Desbanido por {interaction.user.name}")
            
            embed = EmbedBuilder.success(
                "Usuário Desbanido",
                f"**{user.name}** foi desbanido do servidor.",
                fields=[
                    {"name": "Moderador", "value": interaction.user.mention, "inline": True}
                ],
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.response.send_message(embed=embed)
            
            # Log
            log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
            if log_channel:
                log_embed = EmbedBuilder.success(
                    "✅ Usuário Desbanido",
                    f"**Usuário:** {user.mention}\n**Moderador:** {interaction.user.mention}",
                    thumbnail=user.display_avatar.url,
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                await log_channel.send(embed=log_embed)
            
            self.bot.db.add_log('moderation', str(user.id), str(interaction.guild.id), 'unban', f"Por {interaction.user.name}")
            
        except discord.NotFound:
            embed = EmbedBuilder.error("Erro", "Usuário não encontrado ou não está banido.", footer_icon=interaction.guild.icon.url if interaction.guild.icon else None)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Erro ao desbanir: {e}")
            embed = EmbedBuilder.error("Erro", f"Não foi possível desbanir: {str(e)}", footer_icon=interaction.guild.icon.url if interaction.guild.icon else None)
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="mute", description="Mutar um membro")
    @app_commands.describe(member="Membro a ser mutado", duration="Duração (ex: 10m, 1h, 1d)", reason="Motivo")
    @app_commands.check(lambda interaction: Permissions.is_staff(interaction.user))
    async def mute_command(self, interaction: discord.Interaction, member: discord.Member, duration: str = "10m", reason: str = "Não especificado"):
        """Mutar membro com timeout"""
        
        if member.top_role >= interaction.user.top_role:
            embed = EmbedBuilder.error("Erro", "Você não pode mutar este membro.", footer_icon=interaction.guild.icon.url if interaction.guild.icon else None)
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Parsear duração
        try:
            amount = int(duration[:-1])
            unit = duration[-1].lower()
            
            if unit == 'm':
                delta = timedelta(minutes=amount)
            elif unit == 'h':
                delta = timedelta(hours=amount)
            elif unit == 'd':
                delta = timedelta(days=amount)
            else:
                raise ValueError("Unidade inválida")
            
            if delta > timedelta(days=28):
                raise ValueError("Duração máxima: 28 dias")
            
        except:
            embed = EmbedBuilder.error("Erro", "Formato de duração inválido! Use: 10m, 1h, 1d", footer_icon=interaction.guild.icon.url if interaction.guild.icon else None)
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        try:
            await member.timeout(delta, reason=f"{interaction.user.name}: {reason}")
            
            embed = EmbedBuilder.success(
                "Membro Mutado",
                f"**{member.mention}** foi mutado por **{duration}**.",
                fields=[
                    {"name": "Motivo", "value": reason, "inline": False},
                    {"name": "Moderador", "value": interaction.user.mention, "inline": True},
                    {"name": "Duração", "value": duration, "inline": True}
                ],
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.response.send_message(embed=embed)
            
            # Log
            log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
            if log_channel:
                log_embed = EmbedBuilder.warning(
                    "🔇 Membro Mutado",
                    f"**Membro:** {member.mention}\n**Moderador:** {interaction.user.mention}\n**Duração:** {duration}\n**Motivo:** {reason}",
                    thumbnail=member.display_avatar.url,
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                await log_channel.send(embed=log_embed)
            
            self.bot.db.add_log('moderation', str(member.id), str(interaction.guild.id), 'mute', f"{duration} - {reason}")
            
        except Exception as e:
            logger.error(f"Erro ao mutar: {e}")
            embed = EmbedBuilder.error("Erro", f"Não foi possível mutar: {str(e)}", footer_icon=interaction.guild.icon.url if interaction.guild.icon else None)
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="unmute", description="Desmutar um membro")
    @app_commands.describe(member="Membro a ser desmutado")
    @app_commands.check(lambda interaction: Permissions.is_staff(interaction.user))
    async def unmute_command(self, interaction: discord.Interaction, member: discord.Member):
        """Desmutar membro"""
        
        try:
            await member.timeout(None, reason=f"Desmutado por {interaction.user.name}")
            
            embed = EmbedBuilder.success(
                "Membro Desmutado",
                f"**{member.mention}** foi desmutado.",
                fields=[
                    {"name": "Moderador", "value": interaction.user.mention, "inline": True}
                ],
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.response.send_message(embed=embed)
            
            # Log
            log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
            if log_channel:
                log_embed = EmbedBuilder.success(
                    "🔊 Membro Desmutado",
                    f"**Membro:** {member.mention}\n**Moderador:** {interaction.user.mention}",
                    thumbnail=member.display_avatar.url,
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                await log_channel.send(embed=log_embed)
            
            self.bot.db.add_log('moderation', str(member.id), str(interaction.guild.id), 'unmute', f"Por {interaction.user.name}")
            
        except Exception as e:
            logger.error(f"Erro ao desmutar: {e}")
            embed = EmbedBuilder.error("Erro", f"Não foi possível desmutar: {str(e)}", footer_icon=interaction.guild.icon.url if interaction.guild.icon else None)
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="clear", description="Limpar mensagens do canal")
    @app_commands.describe(amount="Quantidade de mensagens a deletar (1-100)")
    @app_commands.check(lambda interaction: Permissions.is_staff(interaction.user))
    async def clear_command(self, interaction: discord.Interaction, amount: int = 10):
        """Limpar mensagens"""
        
        amount = max(1, min(100, amount))
        
        try:
            await interaction.response.defer(ephemeral=True)
            
            deleted = await interaction.channel.purge(limit=amount)
            
            embed = EmbedBuilder.success(
                "Mensagens Limpas",
                f"**{len(deleted)}** mensagens foram deletadas.",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Log
            log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
            if log_channel and log_channel.id != interaction.channel.id:
                log_embed = EmbedBuilder.info(
                    "🧹 Mensagens Limpas",
                    f"**Canal:** {interaction.channel.mention}\n**Quantidade:** {len(deleted)}\n**Moderador:** {interaction.user.mention}",
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                await log_channel.send(embed=log_embed)
            
        except Exception as e:
            logger.error(f"Erro ao limpar mensagens: {e}")
            embed = EmbedBuilder.error("Erro", f"Não foi possível limpar mensagens: {str(e)}", footer_icon=interaction.guild.icon.url if interaction.guild.icon else None)
            await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Moderation(bot))