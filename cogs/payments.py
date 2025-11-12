import discord
from discord.ext import commands
from discord import app_commands
import logging
from datetime import datetime
from utils import EmbedBuilder, Config, Permissions
import secrets

logger = logging.getLogger('PandaBot.Payments')

class Payments(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pending_payments = {}  # {payment_id: dados}
    
    @app_commands.command(name="pagar", description="Criar link de pagamento")
    @app_commands.describe(
        valor="Valor a cobrar (ex: 5.00)",
        moeda="Moeda (BRL/EUR/USD)",
        usuario="Usuário que vai pagar",
        produto="Nome do produto (opcional)"
    )
    @app_commands.check(lambda interaction: Permissions.is_staff(interaction.user))
    async def pagar_command(
        self,
        interaction: discord.Interaction,
        valor: float,
        moeda: str,
        usuario: discord.Member,
        produto: str = "Produto Digital"
    ):
        """Criar cobrança"""
        
        # Validar moeda
        moedas_validas = {'BRL': 'R$', 'EUR': '€', 'USD': '$', 'GBP': '£'}
        moeda_upper = moeda.upper()
        
        if moeda_upper not in moedas_validas:
            embed = EmbedBuilder.error(
                "Moeda Inválida",
                f"Moedas aceitas: BRL, EUR, USD, GBP",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        if valor <= 0:
            embed = EmbedBuilder.error(
                "Valor Inválido",
                "O valor deve ser maior que zero.",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Gerar ID único
        payment_id = secrets.token_hex(8)
        symbol = moedas_validas[moeda_upper]
        
        # Salvar dados do pagamento
        self.pending_payments[payment_id] = {
            'user_id': str(usuario.id),
            'staff_id': str(interaction.user.id),
            'guild_id': str(interaction.guild.id),
            'channel_id': str(interaction.channel.id),
            'valor': valor,
            'moeda': moeda_upper,
            'symbol': symbol,
            'produto': produto,
            'status': 'pendente',
            'created_at': datetime.utcnow().isoformat()
        }
        
        # Criar embed de cobrança
        embed = EmbedBuilder.create_embed(
            "💳 Pagamento Criado",
            f"{usuario.mention}, você tem um pagamento pendente!",
            color=Config.COLORS['warning'],
            thumbnail=interaction.guild.icon.url if interaction.guild.icon else None,
            fields=[
                {"name": "🛒 Produto", "value": produto, "inline": True},
                {"name": "💰 Valor", "value": f"**{symbol} {valor:.2f}**", "inline": True},
                {"name": "💱 Moeda", "value": moeda_upper, "inline": True},
                {"name": "👤 Criado por", "value": interaction.user.mention, "inline": True},
                {"name": "🔖 ID do Pagamento", "value": f"`{payment_id}`", "inline": True},
                {"name": "\u200b", "value": "\u200b", "inline": True},
                {
                    "name": "📋 Como Pagar",
                    "value": "**PIX (Brasil):**\n"
                            "• Chave: `suachavepix@exemplo.com`\n"
                            "• Nome: Panda Store\n\n"
                            "**PayPal:**\n"
                            "• paypal.me/pandastore\n\n"
                            "**Após pagar, envie o comprovante aqui!**",
                    "inline": False
                }
            ],
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        view = PaymentView(self.bot, payment_id, usuario)
        
        # Enviar no canal
        await interaction.response.send_message(
            content=f"{usuario.mention} 💳 **Novo Pagamento**",
            embed=embed,
            view=view
        )
        
        # Tentar enviar DM
        try:
            dm_embed = EmbedBuilder.warning(
                "💳 Novo Pagamento",
                f"Você tem um novo pagamento de **{symbol} {valor:.2f}**!",
                fields=[
                    {"name": "🛒 Produto", "value": produto},
                    {"name": "💰 Valor", "value": f"{symbol} {valor:.2f}"},
                    {"name": "🔖 ID", "value": f"`{payment_id}`"}
                ],
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await usuario.send(embed=dm_embed)
        except:
            logger.warning(f"Não foi possível enviar DM para {usuario.id}")
        
        # Log
        log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
        if log_channel:
            log_embed = EmbedBuilder.warning(
                "💳 NOVO PAGAMENTO CRIADO",
                f"**Cliente:** {usuario.mention}\n"
                f"**Staff:** {interaction.user.mention}\n"
                f"**Valor:** {symbol} {valor:.2f}\n"
                f"**Produto:** {produto}\n"
                f"**ID:** `{payment_id}`\n"
                f"**Status:** ⏳ Aguardando Pagamento",
                thumbnail=usuario.display_avatar.url,
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await log_channel.send(embed=log_embed)
        
        # Salvar no banco
        self.bot.db.add_log(
            'payment',
            str(usuario.id),
            str(interaction.guild.id),
            'created',
            f"⏳ AGUARDANDO: {symbol} {valor:.2f} - {produto} - ID: {payment_id}"
        )
    
    @app_commands.command(name="confirmar-pagamento", description="Confirmar que o pagamento foi recebido")
    @app_commands.describe(payment_id="ID do pagamento")
    @app_commands.check(lambda interaction: Permissions.is_staff(interaction.user))
    async def confirmar_command(self, interaction: discord.Interaction, payment_id: str):
        """Confirmar pagamento manualmente"""
        
        payment_data = self.pending_payments.get(payment_id)
        
        if not payment_data:
            embed = EmbedBuilder.error(
                "Pagamento Não Encontrado",
                f"Nenhum pagamento com ID `{payment_id}` foi encontrado.",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        if payment_data['status'] == 'confirmado':
            embed = EmbedBuilder.warning(
                "Já Confirmado",
                "Este pagamento já foi confirmado anteriormente.",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Atualizar status
        payment_data['status'] = 'confirmado'
        payment_data['confirmed_by'] = str(interaction.user.id)
        payment_data['confirmed_at'] = datetime.utcnow().isoformat()
        
        # Buscar informações
        user = await self.bot.fetch_user(int(payment_data['user_id']))
        guild = self.bot.get_guild(int(payment_data['guild_id']))
        channel = guild.get_channel(int(payment_data['channel_id']))
        
        symbol = payment_data['symbol']
        valor = payment_data['valor']
        produto = payment_data['produto']
        
        # Criar recibo
        timestamp = int(datetime.utcnow().timestamp())
        
        receipt_embed = EmbedBuilder.success(
            "✅ PAGAMENTO CONFIRMADO",
            "**O pagamento foi confirmado e aprovado!**",
            thumbnail=user.display_avatar.url,
            fields=[
                {
                    "name": "━━━━━━ 📋 INFORMAÇÕES DO CLIENTE ━━━━━━",
                    "value": f"**Cliente:** {user.mention}\n**Nome:** `{user.name}`\n**ID:** `{user.id}`",
                    "inline": False
                },
                {
                    "name": "━━━━━━ 🛒 DETALHES DA COMPRA ━━━━━━",
                    "value": f"**Produto:** {produto}\n**Confirmado por:** {interaction.user.mention}",
                    "inline": False
                },
                {
                    "name": "💰 Valor",
                    "value": f"**{symbol} {valor:.2f}**",
                    "inline": True
                },
                {
                    "name": "💱 Moeda",
                    "value": payment_data['moeda'],
                    "inline": True
                },
                {
                    "name": "✅ Status",
                    "value": "**CONFIRMADO**",
                    "inline": True
                },
                {
                    "name": "📅 Data",
                    "value": f"<t:{timestamp}:F>",
                    "inline": True
                },
                {
                    "name": "🔖 ID do Pagamento",
                    "value": f"`{payment_id}`",
                    "inline": True
                },
                {
                    "name": "\u200b",
                    "value": "\u200b",
                    "inline": True
                },
                {
                    "name": "━━━━━━ 📝 OBSERVAÇÕES ━━━━━━",
                    "value": "✅ Pagamento confirmado com sucesso\n✅ Produto será entregue em breve\n✅ Guarde este recibo para referência",
                    "inline": False
                }
            ],
            footer_icon=guild.icon.url if guild.icon else None
        )
        
        # Enviar recibo no canal de compra
        if channel:
            await channel.send(
                content=f"🎉 {user.mention} **PAGAMENTO CONFIRMADO!** 🎉",
                embed=receipt_embed
            )
        
        # Enviar DM ao cliente
        try:
            dm_embed = EmbedBuilder.success(
                "✅ Pagamento Confirmado!",
                f"Seu pagamento foi confirmado!\n\n"
                f"**Produto:** {produto}\n"
                f"**Valor:** {symbol} {valor:.2f}\n"
                f"**Data:** <t:{timestamp}:F>\n\n"
                f"🎉 Obrigado pela sua compra!",
                thumbnail=guild.icon.url if guild.icon else None,
                footer_icon=guild.icon.url if guild.icon else None
            )
            await user.send(embed=dm_embed)
        except:
            logger.warning(f"Não foi possível enviar DM para {user.id}")
        
        # Log
        log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
        if log_channel:
            log_embed = EmbedBuilder.success(
                "✅ PAGAMENTO CONFIRMADO",
                f"**Cliente:** {user.mention}\n"
                f"**Staff:** {interaction.user.mention}\n"
                f"**Valor:** {symbol} {valor:.2f}\n"
                f"**Produto:** {produto}\n"
                f"**ID:** `{payment_id}`",
                thumbnail=user.display_avatar.url,
                footer_icon=guild.icon.url if guild.icon else None
            )
            await log_channel.send(embed=log_embed)
        
        # Salvar no banco
        self.bot.db.add_log(
            'payment',
            str(user.id),
            str(guild.id),
            'confirmed',
            f"✅ CONFIRMADO: {symbol} {valor:.2f} - {produto} - ID: {payment_id} - Por: {interaction.user.name}"
        )
        
        # Responder
        success_embed = EmbedBuilder.success(
            "Pagamento Confirmado",
            f"O pagamento de **{symbol} {valor:.2f}** foi confirmado!\n\n"
            f"Recibo enviado para {user.mention}",
            footer_icon=guild.icon.url if guild.icon else None
        )
        await interaction.response.send_message(embed=success_embed, ephemeral=True)
    
    @app_commands.command(name="cancelar-pagamento", description="Cancelar um pagamento pendente")
    @app_commands.describe(payment_id="ID do pagamento")
    @app_commands.check(lambda interaction: Permissions.is_staff(interaction.user))
    async def cancelar_command(self, interaction: discord.Interaction, payment_id: str):
        """Cancelar pagamento"""
        
        payment_data = self.pending_payments.get(payment_id)
        
        if not payment_data:
            embed = EmbedBuilder.error(
                "Pagamento Não Encontrado",
                f"Nenhum pagamento com ID `{payment_id}` foi encontrado.",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Remover pagamento
        del self.pending_payments[payment_id]
        
        user = await self.bot.fetch_user(int(payment_data['user_id']))
        symbol = payment_data['symbol']
        valor = payment_data['valor']
        
        # Log
        log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
        if log_channel:
            log_embed = EmbedBuilder.error(
                "❌ PAGAMENTO CANCELADO",
                f"**Cliente:** {user.mention}\n"
                f"**Cancelado por:** {interaction.user.mention}\n"
                f"**Valor:** {symbol} {valor:.2f}\n"
                f"**ID:** `{payment_id}`",
                thumbnail=user.display_avatar.url,
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await log_channel.send(embed=log_embed)
        
        # Salvar no banco
        self.bot.db.add_log(
            'payment',
            str(user.id),
            str(interaction.guild.id),
            'cancelled',
            f"❌ CANCELADO: {symbol} {valor:.2f} - ID: {payment_id} - Por: {interaction.user.name}"
        )
        
        embed = EmbedBuilder.success(
            "Pagamento Cancelado",
            f"O pagamento `{payment_id}` foi cancelado.",
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="listar-pagamentos", description="Ver pagamentos pendentes")
    @app_commands.check(lambda interaction: Permissions.is_staff(interaction.user))
    async def listar_command(self, interaction: discord.Interaction):
        """Listar pagamentos pendentes"""
        
        if not self.pending_payments:
            embed = EmbedBuilder.info(
                "Sem Pagamentos Pendentes",
                "Não há pagamentos pendentes no momento.",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        description = ""
        for payment_id, data in list(self.pending_payments.items())[:10]:
            user = await self.bot.fetch_user(int(data['user_id']))
            symbol = data['symbol']
            valor = data['valor']
            status = "✅ Confirmado" if data['status'] == 'confirmado' else "⏳ Pendente"
            
            description += f"\n**ID:** `{payment_id}`\n"
            description += f"👤 {user.mention} | {symbol} {valor:.2f} | {status}\n"
        
        embed = EmbedBuilder.create_embed(
            "💳 Pagamentos Pendentes",
            description,
            color=Config.COLORS['info'],
            fields=[
                {"name": "📊 Total", "value": str(len(self.pending_payments)), "inline": True}
            ],
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class PaymentView(discord.ui.View):
    def __init__(self, bot, payment_id: str, user: discord.Member):
        super().__init__(timeout=None)
        self.bot = bot
        self.payment_id = payment_id
        self.user = user
    
    @discord.ui.button(label="✅ Confirmar Pagamento (Staff)", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Botão para staff confirmar"""
        if not Permissions.is_staff(interaction.user):
            return await interaction.response.send_message("❌ Apenas staff pode confirmar!", ephemeral=True)
        
        # Executar comando de confirmação
        cog = self.bot.get_cog('Payments')
        if cog:
            await cog.confirmar_command.__call__(interaction, self.payment_id)
    
    @discord.ui.button(label="❓ Ajuda", style=discord.ButtonStyle.secondary, emoji="❓")
    async def help_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Botão de ajuda"""
        embed = EmbedBuilder.info(
            "❓ Como Pagar",
            "**Métodos de Pagamento:**\n\n"
            "**💳 PIX (Brasil)**\n"
            "• Copie a chave PIX fornecida acima\n"
            "• Faça a transferência no seu app bancário\n"
            "• Envie o comprovante aqui no chat\n\n"
            "**💰 PayPal**\n"
            "• Acesse o link fornecido\n"
            "• Complete o pagamento\n"
            "• Envie o comprovante aqui\n\n"
            "**📸 Enviar Comprovante:**\n"
            "• Tire um print/foto do comprovante\n"
            "• Envie aqui neste canal\n"
            "• Aguarde a confirmação da staff\n\n"
            "**⏰ Após Confirmar:**\n"
            "• A staff verificará seu pagamento\n"
            "• Você receberá uma notificação\n"
            "• Seu produto será entregue!\n\n"
            "**📧 Dúvidas?**\n"
            "Entre em contato com a staff!",
            thumbnail=interaction.guild.icon.url if interaction.guild.icon else None,
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Payments(bot))
