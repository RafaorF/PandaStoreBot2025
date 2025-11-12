import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils import EmbedBuilder, Config, Permissions

logger = logging.getLogger('PandaBot.Config')

class BotConfig(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="config", description="Configurar o bot (Apenas Staff)")
    @app_commands.check(lambda interaction: Permissions.is_staff(interaction.user))
    async def config_command(self, interaction: discord.Interaction):
        """Painel de configuração interativo"""
        
        guild_config = self.bot.db.get_config(str(interaction.guild.id))
        
        if not guild_config:
            # Criar configuração padrão
            self.bot.db.set_config(str(interaction.guild.id), 'staff_role', str(Config.STAFF_ROLE_ID))
            self.bot.db.set_config(str(interaction.guild.id), 'log_channel', str(Config.LOG_CHANNEL_ID))
            self.bot.db.set_config(str(interaction.guild.id), 'auto_pull', 1)
            guild_config = self.bot.db.get_config(str(interaction.guild.id))
        
        embed = self.create_config_embed(interaction.guild, guild_config)
        view = ConfigView(self.bot)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    def create_config_embed(self, guild, config):
        """Criar embed de configuração"""
        
        verified_role = guild.get_role(int(config['verified_role'])) if config.get('verified_role') else None
        staff_role = guild.get_role(int(config.get('staff_role', Config.STAFF_ROLE_ID)))
        log_channel = guild.get_channel(int(config.get('log_channel', Config.LOG_CHANNEL_ID)))
        welcome_channel = guild.get_channel(int(config['welcome_channel'])) if config.get('welcome_channel') else None
        goodbye_channel = guild.get_channel(int(config['goodbye_channel'])) if config.get('goodbye_channel') else None
        
        fields = [
            {
                "name": "👥 Cargo de Verificado",
                "value": verified_role.mention if verified_role else "`Não configurado`",
                "inline": True
            },
            {
                "name": "👮 Cargo de Staff",
                "value": staff_role.mention if staff_role else "`Não configurado`",
                "inline": True
            },
            {
                "name": "📋 Canal de Logs",
                "value": log_channel.mention if log_channel else "`Não configurado`",
                "inline": True
            },
            {
                "name": "👋 Canal de Boas-Vindas",
                "value": welcome_channel.mention if welcome_channel else "`Não configurado`",
                "inline": True
            },
            {
                "name": "👋 Canal de Despedida",
                "value": goodbye_channel.mention if goodbye_channel else "`Não configurado`",
                "inline": True
            },
            {
                "name": "🔄 Auto-Puxar",
                "value": "✅ **Ativado**" if config.get('auto_pull') else "❌ **Desativado**",
                "inline": True
            }
        ]
        
        if config.get('welcome_message'):
            fields.append({
                "name": "💬 Mensagem de Boas-Vindas",
                "value": config['welcome_message'][:100] + "..." if len(config.get('welcome_message', '')) > 100 else config.get('welcome_message', 'Não configurado'),
                "inline": False
            })
        
        embed = EmbedBuilder.create_embed(
            "⚙️ Painel de Configurações",
            "Configure todas as funcionalidades do bot usando os botões abaixo.",
            color=Config.COLORS['primary'],
            thumbnail=guild.icon.url if guild.icon else None,
            fields=fields,
            footer_icon=guild.icon.url if guild.icon else None
        )
        
        return embed

class ConfigView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot
    
    @discord.ui.button(label="Cargo Verificado", style=discord.ButtonStyle.primary, emoji="✅", row=0)
    async def verified_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RoleConfigModal(self.bot, "verified_role", "Cargo de Verificado")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Cargo Staff", style=discord.ButtonStyle.primary, emoji="👮", row=0)
    async def staff_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RoleConfigModal(self.bot, "staff_role", "Cargo de Staff")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Canal de Logs", style=discord.ButtonStyle.primary, emoji="📋", row=0)
    async def log_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ChannelConfigModal(self.bot, "log_channel", "Canal de Logs")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Boas-Vindas", style=discord.ButtonStyle.secondary, emoji="👋", row=1)
    async def welcome_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ChannelConfigModal(self.bot, "welcome_channel", "Canal de Boas-Vindas")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Despedida", style=discord.ButtonStyle.secondary, emoji="👋", row=1)
    async def goodbye_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = ChannelConfigModal(self.bot, "goodbye_channel", "Canal de Despedida")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Auto-Puxar", style=discord.ButtonStyle.success, emoji="🔄", row=1)
    async def auto_pull(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = self.bot.db.get_config(str(interaction.guild.id))
        current = config.get('auto_pull', 0)
        new_value = 0 if current else 1
        
        self.bot.db.set_config(str(interaction.guild.id), 'auto_pull', new_value)
        
        embed = EmbedBuilder.success(
            "Auto-Puxar Atualizado",
            f"Auto-puxar {'**ativado**' if new_value else '**desativado**'}!",
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Atualizar embed principal
        config = self.bot.db.get_config(str(interaction.guild.id))
        cog = self.bot.get_cog('BotConfig')
        new_embed = cog.create_config_embed(interaction.guild, config)
        await interaction.message.edit(embed=new_embed)
    
    @discord.ui.button(label="Mensagem Boas-Vindas", style=discord.ButtonStyle.secondary, emoji="💬", row=2)
    async def welcome_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = WelcomeMessageModal(self.bot)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Atualizar", style=discord.ButtonStyle.secondary, emoji="🔄", row=2)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = self.bot.db.get_config(str(interaction.guild.id))
        cog = self.bot.get_cog('BotConfig')
        new_embed = cog.create_config_embed(interaction.guild, config)
        
        await interaction.response.edit_message(embed=new_embed)

class RoleConfigModal(discord.ui.Modal):
    def __init__(self, bot, config_key, title):
        super().__init__(title=f"Configurar {title}")
        self.bot = bot
        self.config_key = config_key
        
        self.role_id = discord.ui.TextInput(
            label="ID do Cargo",
            placeholder="Cole o ID do cargo aqui",
            style=discord.TextStyle.short,
            required=True
        )
        self.add_item(self.role_id)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            role = interaction.guild.get_role(int(self.role_id.value))
            
            if not role:
                return await interaction.response.send_message("❌ Cargo não encontrado!", ephemeral=True)
            
            self.bot.db.set_config(str(interaction.guild.id), self.config_key, str(role.id))
            
            embed = EmbedBuilder.success(
                "Cargo Configurado",
                f"Cargo configurado para: {role.mention}",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Atualizar embed principal
            config = self.bot.db.get_config(str(interaction.guild.id))
            cog = self.bot.get_cog('BotConfig')
            new_embed = cog.create_config_embed(interaction.guild, config)
            await interaction.message.edit(embed=new_embed)
            
        except ValueError:
            await interaction.response.send_message("❌ ID inválido!", ephemeral=True)

class ChannelConfigModal(discord.ui.Modal):
    def __init__(self, bot, config_key, title):
        super().__init__(title=f"Configurar {title}")
        self.bot = bot
        self.config_key = config_key
        
        self.channel_id = discord.ui.TextInput(
            label="ID do Canal",
            placeholder="Cole o ID do canal aqui",
            style=discord.TextStyle.short,
            required=True
        )
        self.add_item(self.channel_id)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel = interaction.guild.get_channel(int(self.channel_id.value))
            
            if not channel:
                return await interaction.response.send_message("❌ Canal não encontrado!", ephemeral=True)
            
            self.bot.db.set_config(str(interaction.guild.id), self.config_key, str(channel.id))
            
            embed = EmbedBuilder.success(
                "Canal Configurado",
                f"Canal configurado para: {channel.mention}",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Atualizar embed principal
            config = self.bot.db.get_config(str(interaction.guild.id))
            cog = self.bot.get_cog('BotConfig')
            new_embed = cog.create_config_embed(interaction.guild, config)
            await interaction.message.edit(embed=new_embed)
            
        except ValueError:
            await interaction.response.send_message("❌ ID inválido!", ephemeral=True)

class WelcomeMessageModal(discord.ui.Modal, title="Configurar Mensagem de Boas-Vindas"):
    message = discord.ui.TextInput(
        label="Mensagem",
        placeholder="Use {user} para mencionar, {server} para nome do servidor",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )
    
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
    
    async def on_submit(self, interaction: discord.Interaction):
        # Salvar mensagem no DB
        self.bot.db.set_config(str(interaction.guild.id), 'welcome_message', self.message.value)
        
        # Criar preview
        preview = self.message.value.replace('{user}', interaction.user.mention).replace('{server}', interaction.guild.name)
        
        embed = EmbedBuilder.success(
            "Mensagem Configurada",
            f"**Preview:**\n{preview}",
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        # Responder ao modal
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Atualizar embed principal do painel de configuração
        config = self.bot.db.get_config(str(interaction.guild.id))
        cog = self.bot.get_cog('BotConfig')
        new_embed = cog.create_config_embed(interaction.guild, config)
        
        # Envia uma nova mensagem com o embed atualizado ou usa edit_message de uma interação que existe
        # Aqui vamos enviar uma nova mensagem efêmera (mais seguro)
        await interaction.followup.send(embed=new_embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(BotConfig(bot))