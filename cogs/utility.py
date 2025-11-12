import discord
from discord.ext import commands
from discord import app_commands
import logging
from datetime import datetime
from utils import EmbedBuilder, Config, Formatters
import psutil
import os

logger = logging.getLogger('PandaBot.Utility')

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="ping", description="Ver latência do bot")
    async def ping_command(self, interaction: discord.Interaction):
        """Mostrar ping do bot"""
        
        latency = round(self.bot.latency * 1000)
        
        if latency < 100:
            color = Config.COLORS['success']
            status = "Excelente"
        elif latency < 200:
            color = Config.COLORS['info']
            status = "Bom"
        else:
            color = Config.COLORS['warning']
            status = "Alto"
        
        embed = EmbedBuilder.create_embed(
            "🏓 Pong!",
            f"**Latência:** {latency}ms\n**Status:** {status}",
            color=color,
            thumbnail=self.bot.user.display_avatar.url,
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="serverinfo", description="Informações do servidor")
    async def serverinfo_command(self, interaction: discord.Interaction):
        """Informações detalhadas do servidor"""
        
        guild = interaction.guild
        
        # Contar membros
        total_members = guild.member_count
        bots = len([m for m in guild.members if m.bot])
        humans = total_members - bots
        
        # Contar canais
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        
        # Emojis e stickers
        emojis = len(guild.emojis)
        stickers = len(guild.stickers)
        
        # Boost
        boost_level = guild.premium_tier
        boost_count = guild.premium_subscription_count
        
        # Dono
        owner = guild.owner
        
        embed = EmbedBuilder.create_embed(
            f"📊 Informações de {guild.name}",
            f"**ID:** {guild.id}",
            color=Config.COLORS['info'],
            thumbnail=guild.icon.url if guild.icon else None,
            image=guild.banner.url if guild.banner else None,
            fields=[
                {
                    "name": "👑 Dono",
                    "value": owner.mention if owner else "Desconhecido",
                    "inline": True
                },
                {
                    "name": "📅 Criado em",
                    "value": f"<t:{int(guild.created_at.timestamp())}:F>",
                    "inline": True
                },
                {
                    "name": "👥 Membros",
                    "value": f"**Total:** {total_members}\n**Humanos:** {humans}\n**Bots:** {bots}",
                    "inline": True
                },
                {
                    "name": "📁 Canais",
                    "value": f"**Texto:** {text_channels}\n**Voz:** {voice_channels}\n**Categorias:** {categories}",
                    "inline": True
                },
                {
                    "name": "😀 Emojis/Stickers",
                    "value": f"**Emojis:** {emojis}\n**Stickers:** {stickers}",
                    "inline": True
                },
                {
                    "name": "🚀 Boost",
                    "value": f"**Nível:** {boost_level}\n**Boosts:** {boost_count}",
                    "inline": True
                },
                {
                    "name": "🏷️ Cargos",
                    "value": str(len(guild.roles)),
                    "inline": True
                },
                {
                    "name": "🔒 Nível de Verificação",
                    "value": str(guild.verification_level),
                    "inline": True
                }
            ],
            footer_icon=guild.icon.url if guild.icon else None
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="userinfo", description="Informações de um usuário")
    @app_commands.describe(user="Usuário para ver informações")
    async def userinfo_command(self, interaction: discord.Interaction, user: discord.Member = None):
        """Informações de usuário"""
        
        user = user or interaction.user
        
        # Cargos (excluindo @everyone)
        roles = [role.mention for role in user.roles if role.name != "@everyone"]
        roles_text = ", ".join(roles) if roles else "Nenhum"
        if len(roles_text) > 1024:
            roles_text = roles_text[:1021] + "..."
        
        # Status
        status_emoji = {
            discord.Status.online: "🟢 Online",
            discord.Status.idle: "🟡 Ausente",
            discord.Status.dnd: "🔴 Não Perturbe",
            discord.Status.offline: "⚫ Offline"
        }
        
        status = status_emoji.get(user.status, "⚫ Offline")
        
        # Atividade
        activity = "Nenhuma"
        if user.activity:
            if isinstance(user.activity, discord.Spotify):
                activity = f"🎵 Ouvindo **{user.activity.title}** de **{user.activity.artist}**"
            elif isinstance(user.activity, discord.Game):
                activity = f"🎮 Jogando **{user.activity.name}**"
            elif isinstance(user.activity, discord.Streaming):
                activity = f"📺 Transmitindo **{user.activity.name}**"
            elif isinstance(user.activity, discord.CustomActivity):
                activity = f"💬 {user.activity.name}" if user.activity.name else "Nenhuma"
        
        embed = EmbedBuilder.create_embed(
            f"👤 Informações de {user.name}",
            f"**ID:** {user.id}",
            color=user.color if user.color != discord.Color.default() else Config.COLORS['info'],
            thumbnail=user.display_avatar.url,
            fields=[
                {
                    "name": "📝 Nome Completo",
                    "value": f"{user.name}#{user.discriminator}" if user.discriminator != "0" else user.name,
                    "inline": True
                },
                {
                    "name": "📊 Status",
                    "value": status,
                    "inline": True
                },
                {
                    "name": "🎭 Apelido",
                    "value": user.nick or "Nenhum",
                    "inline": True
                },
                {
                    "name": "📅 Conta Criada",
                    "value": f"<t:{int(user.created_at.timestamp())}:F>",
                    "inline": False
                },
                {
                    "name": "📅 Entrou em",
                    "value": f"<t:{int(user.joined_at.timestamp())}:F>" if user.joined_at else "Desconhecido",
                    "inline": False
                },
                {
                    "name": "🤖 Bot?",
                    "value": "Sim" if user.bot else "Não",
                    "inline": True
                },
                {
                    "name": "🚀 Boost?",
                    "value": "Sim" if user.premium_since else "Não",
                    "inline": True
                },
                {
                    "name": "🎮 Atividade",
                    "value": activity,
                    "inline": False
                },
                {
                    "name": f"🏷️ Cargos [{len(roles)}]",
                    "value": roles_text,
                    "inline": False
                }
            ],
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="botinfo", description="Informações do bot")
    async def botinfo_command(self, interaction: discord.Interaction):
        """Informações do bot"""
        
        # Uptime
        uptime = datetime.utcnow() - self.bot.start_time
        uptime_text = Formatters.format_duration(int(uptime.total_seconds()))
        
        # Stats do banco
        stats = self.bot.db.get_stats()
        
        # Memória
        process = psutil.Process(os.getpid())
        memory = process.memory_info().rss / 1024 ** 2  # MB
        
        # CPU
        cpu_percent = process.cpu_percent()
        
        embed = EmbedBuilder.create_embed(
            f"🤖 {self.bot.user.name}",
            "Bot Discord profissional com OAuth2 e Tickets",
            color=Config.COLORS['panda'],
            thumbnail=self.bot.user.display_avatar.url,
            fields=[
                {
                    "name": "📊 Estatísticas",
                    "value": f"**Servidores:** {len(self.bot.guilds)}\n**Usuários:** {len(self.bot.users)}\n**Comandos:** {len(self.bot.tree.get_commands())}",
                    "inline": True
                },
                {
                    "name": "⏱️ Uptime",
                    "value": uptime_text,
                    "inline": True
                },
                {
                    "name": "🏓 Latência",
                    "value": f"{round(self.bot.latency * 1000)}ms",
                    "inline": True
                },
                {
                    "name": "💾 Memória",
                    "value": f"{memory:.2f} MB",
                    "inline": True
                },
                {
                    "name": "🔧 CPU",
                    "value": f"{cpu_percent:.1f}%",
                    "inline": True
                },
                {
                    "name": "🐍 Python",
                    "value": f"discord.py {discord.__version__}",
                    "inline": True
                },
                {
                    "name": "🔐 OAuth2",
                    "value": f"**{stats['total_users']}** usuários",
                    "inline": True
                },
                {
                    "name": "🎫 Tickets",
                    "value": f"**{stats['total_tickets']}** registrados",
                    "inline": True
                },
                {
                    "name": "🚫 Blacklist",
                    "value": f"**{stats['total_blacklisted']}** usuários",
                    "inline": True
                }
            ],
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="avatar", description="Ver avatar de um usuário")
    @app_commands.describe(user="Usuário para ver o avatar")
    async def avatar_command(self, interaction: discord.Interaction, user: discord.Member = None):
        """Mostrar avatar"""
        
        user = user or interaction.user
        
        embed = EmbedBuilder.create_embed(
            f"🖼️ Avatar de {user.name}",
            f"[PNG]({user.display_avatar.with_format('png').url}) | [JPG]({user.display_avatar.with_format('jpg').url}) | [WEBP]({user.display_avatar.with_format('webp').url})",
            color=user.color if user.color != discord.Color.default() else Config.COLORS['info'],
            image=user.display_avatar.url,
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="banner", description="Ver banner do servidor")
    async def banner_command(self, interaction: discord.Interaction):
        """Mostrar banner do servidor"""
        
        if not interaction.guild.banner:
            embed = EmbedBuilder.warning(
                "Sem Banner",
                "Este servidor não tem um banner configurado.",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        embed = EmbedBuilder.create_embed(
            f"🎨 Banner de {interaction.guild.name}",
            f"[Link Direto]({interaction.guild.banner.url})",
            color=Config.COLORS['info'],
            image=interaction.guild.banner.url,
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Utility(bot))