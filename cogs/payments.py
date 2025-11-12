import discord
from discord.ext import commands
from discord import app_commands
import stripe
from utils import EmbedBuilder, Config
from decimal import Decimal, InvalidOperation
from fastapi import FastAPI, Request
import uvicorn
import asyncio
import threading
import os

STRIPE_SECRET_KEY = "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"  # tua secret key
STRIPE_PUBLIC_KEY = "pk_live_51SSgyhFSG1ZAEoAWhgtctMZg0kXkfCnhsc6ayfSe9pdCFk8p7a48mzYaCFntEtlibkdbUBeHZut2vz9C2KQwN0Ij00grN5lSek"  # opcional
STRIPE_WEBHOOK_SECRET = "whsec_6kspzWeOMkomdd5s28L29K8r2p1vGaV1"  # do painel Stripe
stripe.api_key = STRIPE_SECRET_KEY

# ====================================
# FASTAPI PARA WEBHOOK
# ====================================
app = FastAPI()
sessions_channels = {}
bot_instance = None

@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        return {"error": str(e)}, 400

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        session_id = session['id']
        amount = session['amount_total'] / 100
        currency = session['currency'].upper()

        if session_id in sessions_channels and bot_instance:
            channel_id = sessions_channels[session_id]
            channel = bot_instance.get_channel(channel_id)
            if channel:
                asyncio.run_coroutine_threadsafe(
                    channel.send(f"✅ Pagamento confirmado! 💰 {amount} {currency}"),
                    bot_instance.loop
                )
            del sessions_channels[session_id]

    return {"status": "ok"}

# ===============================
# COG DE PAGAMENTOS
# ===============================
class Payments(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="pagamento",
        description="Gerar link de pagamento Stripe"
    )
    @app_commands.describe(
        valor="Valor do pagamento (ex: 5 para 5 EUR, 0.05 para 5 centimos)",
        moeda="Moeda (ex: eur, usd, brl)"
    )
    async def pagamento(self, interaction: discord.Interaction, valor: str, moeda: str):
        await interaction.response.defer(ephemeral=False)
        try:
            valor_decimal = Decimal(valor)
            unit_amount = int(valor_decimal * 100)
            if unit_amount < 1:
                raise ValueError("O valor mínimo é 0.01")

            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                mode="payment",
                line_items=[{
                    "price_data": {
                        "currency": moeda.lower(),
                        "product_data": {"name": f"Pagamento {moeda.upper()}"},
                        "unit_amount": unit_amount,
                    },
                    "quantity": 1,
                }],
                success_url="https://discord.com",
                cancel_url="https://discord.com"
            )

            sessions_channels[session.id] = interaction.channel.id

            embed = EmbedBuilder.create_embed(
                "💳 Pagamento Criado",
                f"O valor de **{valor_decimal.normalize()} {moeda.upper()}** foi gerado!\n\n"
                f"👉 [Clique aqui para pagar]({session.url})",
                color=Config.COLORS['info']
            )

            await interaction.followup.send(embed=embed, ephemeral=False)

        except InvalidOperation:
            await interaction.followup.send(
                "⚠️ O valor precisa ser um número válido, como `5` ou `0.05`.",
                ephemeral=False
            )
        except Exception as e:
            error_embed = EmbedBuilder.error(
                "Erro ao gerar pagamento",
                f"Detalhes: `{e}`"
            )
            await interaction.followup.send(embed=error_embed, ephemeral=False)

# ===============================
# SETUP DO COG
# ===============================
async def setup(bot):
    global bot_instance
    bot_instance = bot
    await bot.add_cog(Payments(bot))

# ===============================
# RODAR FASTAPI EM THREAD
# ===============================
def run_fastapi():
    port = int(os.environ.get("PORT", 3000))  # usa PORT da ENV ou 3000
    uvicorn.run(app, host="0.0.0.0", port=port)

threading.Thread(target=run_fastapi, daemon=True).start()
