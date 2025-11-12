import logging
import discord
from datetime import datetime
import os
from typing import Optional

class Config:
    """Configurações centralizadas"""
    
    # IDs fixos
    STAFF_ROLE_ID = 1156588514364883065
    LOG_CHANNEL_ID = 1192914692180545718
    TICKET_CATEGORY_ID = 1161185466473795714
    CART_CATEGORY_ID = 1160644873272172627
    RATING_CHANNEL_ID = 1149436350064492647
    
    # Cores
    COLORS = {
        'success': 0x00FF00,
        'error': 0xFF0000,
        'warning': 0xFFA500,
        'info': 0x0099FF,
        'primary': 0x5865F2,
        'panda': 0x2ECC71
    }
    
    # Emojis
    EMOJIS = {
        'success': '✅',
        'error': '❌',
        'warning': '⚠️',
        'info': 'ℹ️',
        'ticket': '🎫',
        'cart': '🛒',
        'lock': '🔒',
        'unlock': '🔓',
        'trash': '🗑️',
        'add': '➕',
        'star': '⭐',
        'panda': '🐼'
    }
    
    # Mensagens
    TERMS_OF_SERVICE = """
**📜 Termos de Compra - Panda Store**

**1. Condições Gerais**
• Todas as vendas são finais
• Garantia de 7 dias para produtos digitais
• Suporte disponível 24/7

**2. Pagamentos**
• Aceitamos PIX, Cartão e Criptomoedas
• Pagamento deve ser efetuado em até 24h
• Após confirmação, entrega em até 2h

**3. Entrega**
• Produtos digitais: Entrega imediata
• Contas: Verificar funcionalidade em 24h
• Problemas: Abrir ticket em até 48h

**4. Reembolsos**
• Apenas em caso de produto não funcional
• Análise em até 48h
• Reembolso em até 7 dias úteis

**5. Proibições**
• Revenda sem autorização
• Compartilhamento de produtos
• Uso indevido resultará em ban

Ao comprar, você concorda com estes termos.
"""

class Logger:
    """Sistema de logging customizado"""
    
    @staticmethod
    def setup():
        """Configurar sistema de logs"""
        os.makedirs('logs', exist_ok=True)
        
        # Formato do log
        log_format = logging.Formatter(
            '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Handler para arquivo
        file_handler = logging.FileHandler(
            f'logs/bot_{datetime.now().strftime("%Y%m%d")}.log',
            encoding='utf-8'
        )
        file_handler.setFormatter(log_format)
        file_handler.setLevel(logging.INFO)
        
        # Handler para console
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_format)
        console_handler.setLevel(logging.INFO)
        
        # Configurar logger raiz
        logger = logging.getLogger('PandaBot')
        logger.setLevel(logging.INFO)
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger

class EmbedBuilder:
    """Construtor de embeds padronizados"""
    
    @staticmethod
    def create_embed(
        title: str,
        description: str,
        color: int = Config.COLORS['primary'],
        thumbnail: Optional[str] = None,
        image: Optional[str] = None,
        footer_text: str = "Panda Store",
        footer_icon: Optional[str] = None,
        fields: Optional[list] = None
    ) -> discord.Embed:
        """Criar embed padronizado"""
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.utcnow()
        )
        
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        
        if image:
            embed.set_image(url=image)
        
        if fields:
            for field in fields:
                embed.add_field(
                    name=field.get('name', 'Campo'),
                    value=field.get('value', 'Valor'),
                    inline=field.get('inline', False)
                )
        
        embed.set_footer(
            text=footer_text,
            icon_url=footer_icon
        )
        
        return embed
    
    @staticmethod
    def success(title: str, description: str, **kwargs) -> discord.Embed:
        """Embed de sucesso"""
        return EmbedBuilder.create_embed(
            title=f"{Config.EMOJIS['success']} {title}",
            description=description,
            color=Config.COLORS['success'],
            **kwargs
        )
    
    @staticmethod
    def error(title: str, description: str, **kwargs) -> discord.Embed:
        """Embed de erro"""
        return EmbedBuilder.create_embed(
            title=f"{Config.EMOJIS['error']} {title}",
            description=description,
            color=Config.COLORS['error'],
            **kwargs
        )
    
    @staticmethod
    def warning(title: str, description: str, **kwargs) -> discord.Embed:
        """Embed de aviso"""
        return EmbedBuilder.create_embed(
            title=f"{Config.EMOJIS['warning']} {title}",
            description=description,
            color=Config.COLORS['warning'],
            **kwargs
        )
    
    @staticmethod
    def info(title: str, description: str, **kwargs) -> discord.Embed:
        """Embed de informação"""
        return EmbedBuilder.create_embed(
            title=f"{Config.EMOJIS['info']} {title}",
            description=description,
            color=Config.COLORS['info'],
            **kwargs
        )

class Permissions:
    """Verificador de permissões"""
    
    @staticmethod
    def is_owner(user_id: int) -> bool:
        """Verificar se é o dono"""
        return str(user_id) == os.getenv('OWNER_ID')
    
    @staticmethod
    def is_staff(member: discord.Member) -> bool:
        """Verificar se é staff"""
        staff_role = discord.utils.get(member.roles, id=Config.STAFF_ROLE_ID)
        return staff_role is not None or member.guild_permissions.administrator
    
    @staticmethod
    def has_permission(member: discord.Member, permission: str) -> bool:
        """Verificar permissão específica"""
        return getattr(member.guild_permissions, permission, False)

class Views:
    """Views customizadas para botões"""
    
    class ConfirmView(discord.ui.View):
        """View de confirmação"""
        
        def __init__(self, timeout=60):
            super().__init__(timeout=timeout)
            self.value = None
        
        @discord.ui.button(label="Confirmar", style=discord.ButtonStyle.green, emoji="✅")
        async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.value = True
            self.stop()
        
        @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.red, emoji="❌")
        async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.value = False
            self.stop()
    
    class RatingView(discord.ui.View):
        """View de avaliação com estrelas"""
        
        def __init__(self, ticket_type: str):
            super().__init__(timeout=300)
            self.ticket_type = ticket_type
            self.service_rating = None
            self.product_rating = None
            self.feedback = None
        
        @discord.ui.select(
            placeholder="Avalie o atendimento (1-5 estrelas)",
            options=[
                discord.SelectOption(label="⭐ 1 - Péssimo", value="1"),
                discord.SelectOption(label="⭐⭐ 2 - Ruim", value="2"),
                discord.SelectOption(label="⭐⭐⭐ 3 - Regular", value="3"),
                discord.SelectOption(label="⭐⭐⭐⭐ 4 - Bom", value="4"),
                discord.SelectOption(label="⭐⭐⭐⭐⭐ 5 - Excelente", value="5"),
            ]
        )
        async def service_select(self, interaction: discord.Interaction, select: discord.ui.Select):
            self.service_rating = int(select.values[0])
            await interaction.response.send_message(
                f"✅ Avaliação do atendimento: {select.values[0]} estrelas",
                ephemeral=True
            )
        
        @discord.ui.button(label="Enviar Avaliação", style=discord.ButtonStyle.green, emoji="📤")
        async def submit(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not self.service_rating:
                await interaction.response.send_message(
                    "❌ Por favor, avalie o atendimento primeiro!",
                    ephemeral=True
                )
                return
            
            self.stop()
            await interaction.response.send_message(
                "✅ Avaliação enviada com sucesso! Obrigado pelo feedback.",
                ephemeral=True
            )

class TranscriptGenerator:
    """Gerador de transcrições de tickets"""
    
    @staticmethod
    async def generate(channel: discord.TextChannel) -> str:
        """Gerar transcrição do canal"""
        messages = []
        
        async for message in channel.history(limit=None, oldest_first=True):
            timestamp = message.created_at.strftime("%d/%m/%Y %H:%M:%S")
            author = f"{message.author.name}#{message.author.discriminator}"
            content = message.content or "[Arquivo/Embed]"
            
            messages.append(f"[{timestamp}] {author}: {content}")
            
            # Adicionar anexos
            if message.attachments:
                for attachment in message.attachments:
                    messages.append(f"  └─ Anexo: {attachment.url}")
            
            # Adicionar embeds
            if message.embeds:
                for embed in message.embeds:
                    if embed.title:
                        messages.append(f"  └─ Embed: {embed.title}")
        
        transcript = "\n".join(messages)
        
        # Salvar em arquivo
        filename = f"transcript_{channel.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        filepath = f"data/{filename}"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"Transcrição do Ticket: {channel.name}\n")
            f.write(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            f.write("=" * 50 + "\n\n")
            f.write(transcript)
        
        return filepath

class Formatters:
    """Formatadores de texto"""
    
    @staticmethod
    def format_datetime(timestamp: int) -> str:
        """Formatar timestamp para string legível"""
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%d/%m/%Y às %H:%M:%S")
    
    @staticmethod
    def format_duration(seconds: int) -> str:
        """Formatar duração em segundos"""
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if secs > 0 or not parts:
            parts.append(f"{secs}s")
        
        return " ".join(parts)
    
    @staticmethod
    def format_user(user: discord.User) -> str:
        """Formatar usuário"""
        if user.discriminator == "0":
            return f"@{user.name}"
        return f"{user.name}#{user.discriminator}"