import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils import EmbedBuilder, Config, Permissions
import os

logger = logging.getLogger('PandaBot.Verification')

class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="setup-verificacao", description="Configurar sistema de verificação")
    @app_commands.describe(canal="Canal onde enviar o painel de verificação")
    @app_commands.check(lambda interaction: Permissions.is_staff(interaction.user))
    async def setup_verificacao_command(self, interaction: discord.Interaction, canal: discord.TextChannel):
        """Configurar painel de verificação"""
        
        # Verificar se há cargo configurado
        config = self.bot.db.get_config(str(interaction.guild.id))
        
        if not config or not config.get('verified_role'):
            embed = EmbedBuilder.warning(
                "Configuração Incompleta",
                "Configure o cargo de verificado primeiro usando `/config`!",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        verified_role = interaction.guild.get_role(int(config['verified_role']))
        
        if not verified_role:
            embed = EmbedBuilder.error(
                "Erro",
                "Cargo de verificado não encontrado!",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Criar embed de verificação
        embed = EmbedBuilder.create_embed(
            "✅ Sistema de Verificação",
            f"Bem-vindo ao **{interaction.guild.name}**!\n\n"
            "Para ter acesso completo ao servidor, você precisa se verificar abaixo.\n\n"
            "**Como funciona:**\n"
            "1️⃣ Clique no botão **Verificar** abaixo\n"
            "2️⃣ Autorize\n"
            "3️⃣ Receba automaticamente o cargo de verificado\n"
            "4️⃣ Tenha acesso total ao servidor!\n\n"
            "**Benefícios:**\n"
            "✅ Acesso completo ao servidor\n"
            "✅ Proteção contra bots\n"
            "✅ Retorno automático do cargo se sair\n"
            "✅ 100% seguro e confiável",
            color=Config.COLORS['success'],
            thumbnail=interaction.guild.icon.url if interaction.guild.icon else None,
            fields=[
                {
                    "name": "🎯 Cargo Verificado",
                    "value": verified_role.mention,
                    "inline": True
                },
                {
                    "name": "🔒 Privacidade",
                    "value": "Seus dados estão seguros!",
                    "inline": True
                }
            ],
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        # View com botão
        view = VerificationView(self.bot)
        
        try:
            await canal.send(embed=embed, view=view)
            
            success_embed = EmbedBuilder.success(
                "Verificação Configurada",
                f"Painel de verificação enviado em {canal.mention}!",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.response.send_message(embed=success_embed, ephemeral=True)
            
            # Log
            log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
            if log_channel:
                log_embed = EmbedBuilder.info(
                    "✅ Verificação Configurada",
                    f"**Canal:** {canal.mention}\n**Configurado por:** {interaction.user.mention}",
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                await log_channel.send(embed=log_embed)
            
        except Exception as e:
            logger.error(f"Erro ao configurar verificação: {e}")
            error_embed = EmbedBuilder.error(
                "Erro",
                f"Não foi possível configurar: {str(e)}",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

class VerificationView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        
        # Adicionar botão de verificação
        oauth_cog = bot.get_cog('OAuth')
        if oauth_cog:
            auth_url = oauth_cog.generate_auth_url()
            self.add_item(discord.ui.Button(
                label="Verificar",
                emoji="✅",
                style=discord.ButtonStyle.link,
                url=auth_url
            ))
    
    @discord.ui.button(label="Como Funciona?", style=discord.ButtonStyle.secondary, emoji="❓", custom_id="verification_help")
    async def help_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Botão de ajuda"""
        
        embed = EmbedBuilder.info(
            "❓ Como Funciona a Verificação?",
            "**Passo a Passo:**\n\n"
            "1️⃣ **Clique em 'Verificar'**\n"
            "Você será redirecionado para a página oficial do Discord.\n\n"
            "2️⃣ **Autorize as Permissões**\n\n"
            "3️⃣ **Receba o Cargo**\n"
            "Automaticamente você receberá o cargo de verificado!\n\n"
            "4️⃣ **Proteção Automática**\n"
            "Se você sair do servidor, e entrar de volta recebera o cargo verificado automaticamente.\n\n"
            "**É Seguro?**\n"
            "✅ Sim! O bot usa o sistema oficial OAuth2 do Discord.\n"
            "✅ Apenas armazenamos o necessário.\n"
            "✅ Você pode revogar a autorização a qualquer momento.\n\n"
            "**Dúvidas?**\n"
            "Abra um ticket e nossa equipe te ajudará!",
            thumbnail=interaction.guild.icon.url if interaction.guild.icon else None,
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

# Listener para dar cargo após OAuth2
@commands.Cog.listener()
async def on_member_update(self, before: discord.Member, after: discord.Member):
    """Dar cargo de verificado após OAuth2"""
    pass  # A lógica está no web_server.py no callback OAuth2

async def setup(bot):
    await bot.add_cog(Verification(bot))
