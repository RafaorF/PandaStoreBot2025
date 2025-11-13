import discord
from discord.ext import commands
from discord import app_commands
import stripe
import os
import logging
from datetime import datetime
from utils import EmbedBuilder, Config, Permissions

logger = logging.getLogger('PandaBot.Payments')

# Configurar Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

class Payments(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    
    @app_commands.command(name="pagar", description="Criar link de pagamento")
    @app_commands.describe(
        valor="Valor em centavos (ex: 1000 = R$10,00)",
        moeda="Moeda (brl, usd, eur)",
        produto="Nome do produto (opcional)"
    )
    @app_commands.check(lambda interaction: Permissions.is_staff(interaction.user))
    async def pagar_command(
        self, 
        interaction: discord.Interaction, 
        valor: int,
        moeda: str = "brl",
        produto: str = None
    ):
        """Criar checkout do Stripe"""
        
        # Validar moeda
        moedas_validas = ['brl', 'usd', 'eur']
        if moeda.lower() not in moedas_validas:
            embed = EmbedBuilder.error(
                "Moeda Inválida",
                f"Use uma das moedas válidas: {', '.join(moedas_validas)}",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Validar valor mínimo (Stripe requer mínimo de 50 centavos)
        if valor < 50:
            embed = EmbedBuilder.error(
                "Valor Inválido",
                "O valor mínimo é 50 centavos (0.50).",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        try:
            await interaction.response.defer()
            
            # Nome do produto
            product_name = produto or "Produto Panda Store"
            
            # URL de sucesso/cancelamento
            base_url = os.getenv('REDIRECT_URI', 'https://seu-dominio.railway.app').split('/oauth')[0]
            success_url = f"{base_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
            cancel_url = f"{base_url}/payment/cancel"
            
            # Criar sessão de checkout
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card', 'paypal'],
                line_items=[{
                    'price_data': {
                        'currency': moeda.lower(),
                        'unit_amount': valor,
                        'product_data': {
                            'name': product_name,
                            'description': f"Compra realizada no {interaction.guild.name}",
                            'images': [interaction.guild.icon.url] if interaction.guild.icon else []
                        },
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'guild_id': str(interaction.guild.id),
                    'channel_id': str(interaction.channel.id),
                    'user_id': str(interaction.user.id),
                    'username': interaction.user.name,
                    'product': product_name,
                    'staff_id': str(interaction.user.id),  # Quem criou o link
                    'timestamp': str(int(datetime.utcnow().timestamp()))
                }
            )
            
            # Formatação do valor
            valor_formatado = self.format_currency(valor, moeda)
            
            # Embed com link de pagamento
            embed = EmbedBuilder.create_embed(
                "💳 Link de Pagamento Criado",
                f"Clique no botão abaixo para realizar o pagamento.",
                color=Config.COLORS['success'],
                thumbnail=interaction.guild.icon.url if interaction.guild.icon else None,
                fields=[
                    {
                        "name": "🛒 Produto",
                        "value": product_name,
                        "inline": True
                    },
                    {
                        "name": "💰 Valor",
                        "value": valor_formatado,
                        "inline": True
                    },
                    {
                        "name": "💳 Moeda",
                        "value": moeda.upper(),
                        "inline": True
                    },
                    {
                        "name": "⏰ Validade",
                        "value": "24 horas",
                        "inline": True
                    },
                    {
                        "name": "🔒 Segurança",
                        "value": "Pagamento processado via Stripe",
                        "inline": True
                    },
                    {
                        "name": "📧 Confirmação",
                        "value": "Você receberá um recibo por email",
                        "inline": True
                    }
                ],
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            
            # View com botão de pagamento
            view = PaymentView(checkout_session.url)
            
            await interaction.followup.send(embed=embed, view=view)
            
            # Log
            log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
            if log_channel:
                log_embed = EmbedBuilder.info(
                    "💳 Link de Pagamento Criado",
                    f"**Produto:** {product_name}\n**Valor:** {valor_formatado}\n**Moeda:** {moeda.upper()}\n**Criado por:** {interaction.user.mention}\n**Canal:** {interaction.channel.mention}",
                    thumbnail=interaction.user.display_avatar.url,
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                await log_channel.send(embed=log_embed)
            
            # Salvar no banco de dados (opcional)
            self.bot.db.add_log(
                'payment', 
                str(interaction.user.id), 
                str(interaction.guild.id),
                'checkout_created',
                f"Produto: {product_name}, Valor: {valor_formatado}, Session: {checkout_session.id}"
            )
            
        except stripe.error.StripeError as e:
            logger.error(f"Erro do Stripe: {e}")
            embed = EmbedBuilder.error(
                "Erro ao Criar Pagamento",
                f"Ocorreu um erro com o Stripe:\n```{str(e)}```",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        except Exception as e:
            logger.error(f"Erro ao criar pagamento: {e}")
            embed = EmbedBuilder.error(
                "Erro Inesperado",
                f"Não foi possível criar o link de pagamento:\n```{str(e)}```",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    def format_currency(self, amount_cents: int, currency: str) -> str:
        """Formatar valor em moeda"""
        symbols = {
            'brl': 'R$',
            'usd': '$',
            'eur': '€'
        }
        symbol = symbols.get(currency.lower(), currency.upper())
        value = amount_cents / 100
        return f"{symbol} {value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    
    async def handle_successful_payment(self, session):
        """Processar pagamento bem-sucedido"""
        try:
            metadata = session.metadata
            
            guild_id = metadata.get('guild_id')
            channel_id = metadata.get('channel_id')
            user_id = metadata.get('user_id')
            username = metadata.get('username')
            product = metadata.get('product')
            
            if not all([guild_id, channel_id]):
                logger.error("Metadados incompletos no pagamento")
                return
            
            # Buscar canal
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                logger.error(f"Canal {channel_id} não encontrado")
                return
            
            guild = self.bot.get_guild(int(guild_id))
            
            # Formatar valor
            amount = session.amount_total
            currency = session.currency
            valor_formatado = self.format_currency(amount, currency)
            
            # Embed de confirmação no canal
            embed = EmbedBuilder.success(
                "✅ Pagamento Confirmado!",
                f"O pagamento foi processado com sucesso!",
                thumbnail=guild.icon.url if guild and guild.icon else None,
                fields=[
                    {
                        "name": "🛒 Produto",
                        "value": product or "Produto",
                        "inline": True
                    },
                    {
                        "name": "💰 Valor Pago",
                        "value": valor_formatado,
                        "inline": True
                    },
                    {
                        "name": "👤 Cliente",
                        "value": username,
                        "inline": True
                    },
                    {
                        "name": "📧 Email",
                        "value": session.customer_details.email if session.customer_details else "N/A",
                        "inline": True
                    },
                    {
                        "name": "🔢 ID da Transação",
                        "value": f"`{session.payment_intent}`",
                        "inline": False
                    },
                    {
                        "name": "✅ Status",
                        "value": "**PAGO**",
                        "inline": True
                    },
                    {
                        "name": "📅 Data",
                        "value": f"<t:{int(datetime.utcnow().timestamp())}:F>",
                        "inline": True
                    }
                ],
                footer_icon=guild.icon.url if guild and guild.icon else None
            )
            
            await channel.send(embed=embed)
            
            # Tentar enviar DM ao usuário
            if user_id:
                try:
                    user = await self.bot.fetch_user(int(user_id))
                    
                    dm_embed = EmbedBuilder.success(
                        "✅ Pagamento Confirmado!",
                        f"Seu pagamento foi processado com sucesso!",
                        thumbnail=guild.icon.url if guild and guild.icon else None,
                        fields=[
                            {
                                "name": "🛒 Produto",
                                "value": product or "Produto",
                                "inline": False
                            },
                            {
                                "name": "💰 Valor",
                                "value": valor_formatado,
                                "inline": True
                            },
                            {
                                "name": "📧 Recibo",
                                "value": f"Enviado para {session.customer_details.email}" if session.customer_details else "Verifique seu email",
                                "inline": False
                            },
                            {
                                "name": "🔢 ID da Transação",
                                "value": f"`{session.payment_intent}`",
                                "inline": False
                            }
                        ],
                        footer_icon=guild.icon.url if guild and guild.icon else None
                    )
                    
                    await user.send(embed=dm_embed)
                    logger.info(f"✅ DM de confirmação enviado para {username}")
                
                except Exception as e:
                    logger.warning(f"Não foi possível enviar DM para {user_id}: {e}")
            
            # Log no canal de logs
            log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
            if log_channel:
                log_embed = EmbedBuilder.success(
                    "💳 Pagamento Recebido",
                    f"Um pagamento foi confirmado via Stripe!",
                    fields=[
                        {
                            "name": "Cliente",
                            "value": username,
                            "inline": True
                        },
                        {
                            "name": "Produto",
                            "value": product or "N/A",
                            "inline": True
                        },
                        {
                            "name": "Valor",
                            "value": valor_formatado,
                            "inline": True
                        },
                        {
                            "name": "Email",
                            "value": session.customer_details.email if session.customer_details else "N/A",
                            "inline": True
                        },
                        {
                            "name": "ID Stripe",
                            "value": f"`{session.id}`",
                            "inline": False
                        }
                    ],
                    footer_icon=guild.icon.url if guild and guild.icon else None
                )
                await log_channel.send(embed=log_embed)
            
            # Salvar no banco de dados
            self.bot.db.add_log(
                'payment',
                user_id,
                guild_id,
                'payment_completed',
                f"Produto: {product}, Valor: {valor_formatado}, Session: {session.id}"
            )
            
            logger.info(f"✅ Pagamento processado: {valor_formatado} de {username}")
            
        except Exception as e:
            logger.error(f"Erro ao processar pagamento bem-sucedido: {e}")

class PaymentView(discord.ui.View):
    """View com botão de pagamento"""
    
    def __init__(self, payment_url: str):
        super().__init__(timeout=None)
        
        # Adicionar botão com link do Stripe
        self.add_item(discord.ui.Button(
            label="Pagar com Stripe",
            emoji="💳",
            style=discord.ButtonStyle.link,
            url=payment_url
        ))

async def setup(bot):

    await bot.add_cog(Payments(bot))
