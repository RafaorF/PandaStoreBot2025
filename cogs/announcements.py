import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils import EmbedBuilder, Config, Permissions

logger = logging.getLogger('PandaBot.Announcements')

class Announcements(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="avisos", description="Enviar avisos personalizados")
    @app_commands.describe(canal="Canal onde enviar o aviso")
    @app_commands.check(lambda interaction: Permissions.is_staff(interaction.user))
    async def avisos_command(self, interaction: discord.Interaction, canal: discord.TextChannel):
        """Enviar avisos personalizados"""
        
        modal = AnnouncementModal(self.bot, canal)
        await interaction.response.send_modal(modal)
    
    @app_commands.command(name="regras", description="Enviar regras do servidor")
    @app_commands.describe(canal="Canal onde enviar as regras")
    @app_commands.check(lambda interaction: Permissions.is_staff(interaction.user))
    async def regras_command(self, interaction: discord.Interaction, canal: discord.TextChannel):
        """Enviar regras do servidor"""
        
        modal = RulesModal(self.bot, canal)
        await interaction.response.send_modal(modal)
    
    @app_commands.command(name="termos", description="Enviar termos de compra")
    @app_commands.describe(canal="Canal onde enviar os termos")
    @app_commands.check(lambda interaction: Permissions.is_staff(interaction.user))
    async def termos_command(self, interaction: discord.Interaction, canal: discord.TextChannel):
        """Enviar termos de compra"""
        
        embed = EmbedBuilder.create_embed(
            "📜 Termos de Compra - Panda Store",
            Config.TERMS_OF_SERVICE,
            color=Config.COLORS['info'],
            thumbnail=interaction.guild.icon.url if interaction.guild.icon else None,
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        try:
            await canal.send(embed=embed)
            
            success_embed = EmbedBuilder.success(
                "Termos Enviados",
                f"Termos de compra enviados em {canal.mention}",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.response.send_message(embed=success_embed, ephemeral=True)
            
            # Log
            log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
            if log_channel:
                log_embed = EmbedBuilder.info(
                    "📜 Termos Enviados",
                    f"**Canal:** {canal.mention}\n**Enviado por:** {interaction.user.mention}",
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                await log_channel.send(embed=log_embed)
            
        except Exception as e:
            logger.error(f"Erro ao enviar termos: {e}")
            error_embed = EmbedBuilder.error(
                "Erro",
                f"Não foi possível enviar os termos: {str(e)}",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

class AnnouncementModal(discord.ui.Modal, title="Enviar Aviso"):
    titulo = discord.ui.TextInput(
        label="Título do Aviso",
        placeholder="Ex: Atualização Importante",
        style=discord.TextStyle.short,
        required=True,
        max_length=100
    )
    
    mensagem = discord.ui.TextInput(
        label="Mensagem",
        placeholder="Digite o aviso aqui...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=2000
    )
    
    cor = discord.ui.TextInput(
        label="Cor (hex)",
        placeholder="Ex: #FF0000 para vermelho",
        style=discord.TextStyle.short,
        required=False,
        max_length=7
    )
    
    imagem_url = discord.ui.TextInput(
        label="URL da Imagem (opcional)",
        placeholder="https://exemplo.com/imagem.png",
        style=discord.TextStyle.short,
        required=False
    )
    
    def __init__(self, bot, canal):
        super().__init__()
        self.bot = bot
        self.canal = canal
    
    async def on_submit(self, interaction: discord.Interaction):
        # Parsear cor
        try:
            if self.cor.value:
                color = int(self.cor.value.replace('#', ''), 16)
            else:
                color = Config.COLORS['info']
        except:
            color = Config.COLORS['info']
        
        # Criar embed
        embed = EmbedBuilder.create_embed(
            f"📢 {self.titulo.value}",
            self.mensagem.value,
            color=color,
            thumbnail=interaction.guild.icon.url if interaction.guild.icon else None,
            image=self.imagem_url.value if self.imagem_url.value else None,
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        try:
            await self.canal.send(embed=embed)
            
            success_embed = EmbedBuilder.success(
                "Aviso Enviado",
                f"Aviso enviado com sucesso em {self.canal.mention}",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.response.send_message(embed=success_embed, ephemeral=True)
            
            # Log
            log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
            if log_channel:
                log_embed = EmbedBuilder.info(
                    "📢 Aviso Enviado",
                    f"**Canal:** {self.canal.mention}\n**Título:** {self.titulo.value}\n**Enviado por:** {interaction.user.mention}",
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                await log_channel.send(embed=log_embed)
            
        except Exception as e:
            logger.error(f"Erro ao enviar aviso: {e}")
            error_embed = EmbedBuilder.error(
                "Erro",
                f"Não foi possível enviar o aviso: {str(e)}",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

class RulesModal(discord.ui.Modal, title="Enviar Regras"):
    titulo = discord.ui.TextInput(
        label="Título",
        placeholder="Ex: Regras do Servidor",
        style=discord.TextStyle.short,
        required=True,
        max_length=100
    )
    
    regras = discord.ui.TextInput(
        label="Regras",
        placeholder="Digite as regras...\nUse uma linha para cada regra.",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=2000
    )
    
    def __init__(self, bot, canal):
        super().__init__()
        self.bot = bot
        self.canal = canal
    
    async def on_submit(self, interaction: discord.Interaction):
        # Processar regras (adicionar números)
        regras_list = self.regras.value.strip().split('\n')
        regras_formatadas = '\n'.join([f"**{i+1}.** {regra.strip()}" for i, regra in enumerate(regras_list) if regra.strip()])
        
        embed = EmbedBuilder.create_embed(
            f"📋 {self.titulo.value}",
            regras_formatadas,
            color=Config.COLORS['warning'],
            thumbnail=interaction.guild.icon.url if interaction.guild.icon else None,
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        try:
            await self.canal.send(embed=embed)
            
            success_embed = EmbedBuilder.success(
                "Regras Enviadas",
                f"Regras enviadas em {self.canal.mention}",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.response.send_message(embed=success_embed, ephemeral=True)
            
            # Log
            log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
            if log_channel:
                log_embed = EmbedBuilder.info(
                    "📋 Regras Enviadas",
                    f"**Canal:** {self.canal.mention}\n**Enviado por:** {interaction.user.mention}",
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                await log_channel.send(embed=log_embed)
            
        except Exception as e:
            logger.error(f"Erro ao enviar regras: {e}")
            error_embed = EmbedBuilder.error(
                "Erro",
                f"Não foi possível enviar as regras: {str(e)}",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Announcements(bot))