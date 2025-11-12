import discord
from discord.ext import commands
from discord import app_commands
import logging
import os
import stripe
from datetime import datetime, timezone
from utils import EmbedBuilder, Config, Permissions

logger = logging.getLogger('PandaBot.Payments')

# Configurar Stripe
stripe_key = os.getenv('STRIPE_SECRET_KEY')
if stripe_key:
    stripe.api_key = stripe_key
else:
    logger.warning("⚠️ STRIPE_SECRET_KEY não configurada - sistema de pagamentos desabilitado")

class Payments(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
        self.pending_payments = {}  # {session_id: {user_id, channel_id, amount, product}}
    
    @app_commands.command(name="cobrar", description="Criar cobrança via Stripe")
    @app_commands.describe(
        valor="Valor a cobrar (ex: 5.00)",
        moeda="Moeda (BRL, EUR, USD)",
        usuario="Usuário que vai pagar",
        produto="Nome do produto/serviço (opcional)"
    )
    @app_commands.check(lambda interaction: Permissions.is_staff(interaction.user))
    async def cobrar_command(
        self,
        interaction: discord.Interaction,
        valor: float,
        moeda: str,
        usuario: discord.Member,
        produto: str = "Produto Digital"
    ):
        """Criar link de pagamento Stripe"""
        
        if not stripe_key:
            embed = EmbedBuilder.error(
                "Sistema Desabilitado",
                "O sistema de pagamentos não está configurado. Configure STRIPE_SECRET_KEY no .env",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Validar moeda
        moedas_validas = ['BRL', 'EUR', 'USD', 'GBP']
        moeda = moeda.upper()
        
        if moeda not in moedas_validas:
            embed = EmbedBuilder.error(
                "Moeda Inválida",
                f"Moedas aceitas: {', '.join(moedas_validas)}",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Validar valor
        if valor <= 0:
            embed = EmbedBuilder.error(
                "Valor Inválido",
                "O valor deve ser maior que zero.",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        await interaction.response.defer()
        
        try:
            # Converter valor para centavos (Stripe usa centavos)
            amount_cents = int(valor * 100)
            
            # Símbolos de moeda
            currency_symbols = {
                'BRL': 'R$',
                'EUR': '€',
                'USD': '$',
                'GBP': '£'
            }
            
            symbol = currency_symbols.get(moeda, moeda)
            
            # Criar sessão de checkout do Stripe
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': moeda.lower(),
                        'product_data': {
                            'name': produto,
                            'description': f'Compra em {interaction.guild.name}',
                        },
                        'unit_amount': amount_cents,
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=os.getenv('STRIPE_SUCCESS_URL', 'https://pandastore.railway.app/payment/success'),
                cancel_url=os.getenv('STRIPE_CANCEL_URL', 'https://pandastore.railway.app/payment/cancel'),
                customer_email=f"{usuario.id}@discord.user",
                metadata={
                    'user_id': str(usuario.id),
                    'guild_id': str(interaction.guild.id),
                    'channel_id': str(interaction.channel.id),
                    'staff_id': str(interaction.user.id),
                    'produto': produto
                }
            )
            
            # Salvar informações do pagamento pendente
            self.pending_payments[session.id] = {
                'user_id': str(usuario.id),
                'guild_id': str(interaction.guild.id),
                'channel_id': str(interaction.channel.id),
                'staff_id': str(interaction.user.id),
                'amount': valor,
                'currency': moeda,
                'produto': produto,
                'created_at': datetime.utcnow().isoformat()
            }
            
            # Criar embed de cobrança
            embed = EmbedBuilder.create_embed(
                "💳 Cobrança Criada",
                f"{usuario.mention}, você tem uma cobrança pendente!",
                color=Config.COLORS['warning'],
                thumbnail=interaction.guild.icon.url if interaction.guild.icon else None,
                fields=[
                    {"name": "🛒 Produto", "value": produto, "inline": True},
                    {"name": "💰 Valor", "value": f"**{symbol} {valor:.2f}**", "inline": True},
                    {"name": "💱 Moeda", "value": moeda, "inline": True},
                    {"name": "👤 Solicitado por", "value": interaction.user.mention, "inline": True},
                    {"name": "⏰ Expira em", "value": "24 horas", "inline": True},
                    {"name": "📋 Instruções", "value": "1️⃣ Clique no botão **Pagar Agora**\n2️⃣ Complete o pagamento com cartão\n3️⃣ Aguarde a confirmação automática", "inline": False}
                ],
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            
            # View com botão de pagamento
            view = PaymentView(session.url, session.id)
            
            # Enviar para o usuário e no canal
            await interaction.followup.send(content=usuario.mention, embed=embed, view=view)
            
            # Tentar enviar DM
            try:
                dm_embed = EmbedBuilder.warning(
                    "💳 Nova Cobrança",
                    f"Você tem uma nova cobrança de **{symbol} {valor:.2f}** em {interaction.guild.name}!",
                    fields=[
                        {"name": "Produto", "value": produto},
                        {"name": "Valor", "value": f"{symbol} {valor:.2f}"}
                    ],
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                await usuario.send(embed=dm_embed, view=view)
            except:
                logger.warning(f"Não foi possível enviar DM para {usuario.id}")
            
            # Log
            log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
            if log_channel:
                log_embed = EmbedBuilder.create_embed(
                    "💳 NOVA COBRANÇA CRIADA",
                    "Uma nova cobrança foi criada e está aguardando pagamento.",
                    color=Config.COLORS['warning'],
                    thumbnail=usuario.display_avatar.url,
                    fields=[
                        {"name": "👤 Cliente", "value": f"{usuario.mention}\n`{usuario.name}` (`{usuario.id}`)", "inline": True},
                        {"name": "👮 Criado por (Staff)", "value": f"{interaction.user.mention}\n`{interaction.user.name}`", "inline": True},
                        {"name": "💰 Valor", "value": f"**{symbol} {valor:.2f}**\n({moeda})", "inline": True},
                        {"name": "🛒 Produto/Serviço", "value": produto, "inline": True},
                        {"name": "📅 Data de Criação", "value": f"<t:{int(datetime.utcnow().timestamp())}:F>", "inline": True},
                        {"name": "⏰ Validade", "value": "24 horas", "inline": True},
                        {"name": "🔖 Session ID", "value": f"`{session.id}`", "inline": False},
                        {"name": "📍 Canal da Cobrança", "value": interaction.channel.mention, "inline": True},
                        {"name": "🔄 Status", "value": "⏳ **AGUARDANDO PAGAMENTO**", "inline": True}
                    ],
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                await log_channel.send(embed=log_embed)
            
            # Salvar no banco de dados
            self.bot.db.add_log(
                'payment',
                str(usuario.id),
                str(interaction.guild.id),
                'created',
                f"⏳ CRIADA: {symbol} {valor:.2f} - {produto} - Session: {session.id} - Staff: {interaction.user.name}"
            )
            
        except stripe.error.StripeError as e:
            logger.error(f"Erro do Stripe: {e}")
            embed = EmbedBuilder.error(
                "Erro ao Criar Cobrança",
                f"Erro do Stripe: {str(e)}",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        except Exception as e:
            logger.error(f"Erro ao criar cobrança: {e}")
            embed = EmbedBuilder.error(
                "Erro",
                f"Ocorreu um erro: {str(e)}",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="pagamentos", description="Ver histórico de pagamentos")
    @app_commands.describe(usuario="Ver pagamentos de um usuário específico (opcional)")
    @app_commands.check(lambda interaction: Permissions.is_staff(interaction.user))
    async def pagamentos_command(self, interaction: discord.Interaction, usuario: discord.Member = None):
        """Ver histórico de pagamentos"""
        
        await interaction.response.defer(ephemeral=True)
        
        # Buscar logs de pagamento
        logs = self.bot.db.get_logs(limit=50)
        payment_logs = [log for log in logs if log['type'] == 'payment']
        
        if usuario:
            payment_logs = [log for log in payment_logs if log['user_id'] == str(usuario.id)]
        
        if not payment_logs:
            embed = EmbedBuilder.warning(
                "Sem Pagamentos",
                "Nenhum pagamento encontrado.",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Criar embed com histórico
        description = ""
        for log in payment_logs[:10]:  # Mostrar últimos 10
            user = await self.bot.fetch_user(int(log['user_id']))
            timestamp = datetime.fromtimestamp(log['timestamp']).strftime("%d/%m/%Y %H:%M")
            action = "✅ Pago" if log['action'] == 'completed' else "📝 Criado" if log['action'] == 'created' else "❌ Cancelado"
            description += f"\n**{timestamp}** - {action}\n{user.mention}: {log['details']}\n"
        
        embed = EmbedBuilder.create_embed(
            "💳 Histórico de Pagamentos",
            description or "Nenhum pagamento encontrado",
            color=Config.COLORS['info'],
            thumbnail=usuario.display_avatar.url if usuario else interaction.guild.icon.url,
            fields=[
                {"name": "📊 Total de Registros", "value": str(len(payment_logs)), "inline": True}
            ],
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

class PaymentView(discord.ui.View):
    def __init__(self, payment_url: str, session_id: str):
        super().__init__(timeout=None)
        self.payment_url = payment_url
        self.session_id = session_id
        
        # Adicionar botão de pagamento
        self.add_item(discord.ui.Button(
            label="💳 Pagar Agora",
            style=discord.ButtonStyle.link,
            url=payment_url,
            emoji="💳"
        ))
    
    @discord.ui.button(label="❓ Ajuda", style=discord.ButtonStyle.secondary, emoji="❓")
    async def help_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Botão de ajuda"""
        embed = EmbedBuilder.info(
            "❓ Como Pagar",
            "**Passo a Passo:**\n\n"
            "1️⃣ **Clique em 'Pagar Agora'**\n"
            "Você será redirecionado para a página segura do Stripe.\n\n"
            "2️⃣ **Preencha os Dados**\n"
            "• Número do cartão\n"
            "• Data de validade\n"
            "• CVV\n"
            "• Email (opcional)\n\n"
            "3️⃣ **Confirme o Pagamento**\n"
            "Após confirmar, você receberá uma notificação instantânea!\n\n"
            "**🔒 Segurança:**\n"
            "✅ Processamento via Stripe (certificado PCI DSS)\n"
            "✅ Dados criptografados\n"
            "✅ Não armazenamos informações de cartão\n\n"
            "**💳 Métodos Aceitos:**\n"
            "• Visa, Mastercard, American Express\n"
            "• Apple Pay, Google Pay\n\n"
            "**📧 Dúvidas?**\n"
            "Abra um ticket e nossa equipe te ajudará!",
            thumbnail=interaction.guild.icon.url if interaction.guild.icon else None,
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="📋 Status", style=discord.ButtonStyle.primary, emoji="📋")
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Verificar status do pagamento"""
        try:
            session = stripe.checkout.Session.retrieve(self.session_id)
            
            status_map = {
                'complete': ('✅ Completo', Config.COLORS['success']),
                'expired': ('❌ Expirado', Config.COLORS['error']),
                'open': ('⏳ Aguardando Pagamento', Config.COLORS['warning'])
            }
            
            status_text, color = status_map.get(session.status, ('❓ Desconhecido', Config.COLORS['info']))
            
            embed = EmbedBuilder.create_embed(
                "📋 Status do Pagamento",
                f"**Status Atual:** {status_text}",
                color=color,
                fields=[
                    {"name": "🆔 ID da Sessão", "value": f"`{self.session_id[:30]}...`", "inline": False}
                ],
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Erro ao verificar status: {e}")
            embed = EmbedBuilder.error(
                "Erro",
                "Não foi possível verificar o status do pagamento.",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Payments(bot))
