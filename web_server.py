from quart import Quart, request, jsonify, render_template, redirect, send_file
import aiohttp
import os
import logging
from datetime import datetime, timedelta
from utils import Config
import discord
import stripe

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

logger = logging.getLogger('PandaBot.WebServer')

class WebServer:
    def __init__(self, bot):
        self.bot = bot
        self.app = Quart(__name__, 
                        template_folder='web/templates',
                        static_folder='web/static')
        self.setup_routes()
        
        self.client_id = os.getenv('CLIENT_ID')
        self.client_secret = os.getenv('CLIENT_SECRET')
        self.redirect_uri = os.getenv('REDIRECT_URI')
        self.oauth_scopes = os.getenv('OAUTH_SCOPES', 'identify guilds.join').split()
        self.api_endpoint = 'https://discord.com/api/v10'
        self.web_password = os.getenv('WEB_PASSWORD', 'admin123')
    
    def setup_routes(self):
        """Configurar rotas do servidor"""
        
        @self.app.route('/')
        async def index():
            """Página inicial"""
            return await render_template('index.html', 
                                        bot_name=self.bot.user.name if self.bot.user else 'PandaBot',
                                        guild_count=len(self.bot.guilds))
        
        @self.app.route('/oauth/callback')
        async def oauth_callback():
            """Callback do OAuth2"""
            code = request.args.get('code')
            state = request.args.get('state')
            
            if not code:
                return await render_template('error.html', 
                                           error='Código de autorização não fornecido'), 400
            
            try:
                # Trocar código por tokens
                token_data = await self.exchange_code(code)
                
                if not token_data:
                    return await render_template('error.html', 
                                               error='Erro ao obter tokens de acesso')
                
                access_token = token_data['access_token']
                refresh_token = token_data['refresh_token']
                expires_in = token_data['expires_in']
                
                # Obter informações do usuário
                user_info = await self.get_user_info(access_token)
                
                if not user_info:
                    return await render_template('error.html', 
                                               error='Erro ao obter informações do usuário')
                
                user_id = user_info['id']
                username = user_info['username']
                
                # Salvar no banco
                expires_at = int((datetime.utcnow() + timedelta(seconds=expires_in)).timestamp())
                self.bot.db.add_oauth_user(user_id, access_token, refresh_token, expires_at)
                
                logger.info(f"✅ {username} ({user_id}) autorizou OAuth2")
                
                # Auto-puxar e dar cargo
                guild_id = os.getenv('GUILD_ID')
                guild = self.bot.get_guild(int(guild_id))
                
                if guild:
                    config = self.bot.db.get_config(guild_id)
                    
                    # Verificar se usuário já está no servidor
                    member = guild.get_member(int(user_id))
                    
                    if not member:
                        # Puxar para o servidor
                        result = await self.add_user_to_guild(user_id, guild_id, access_token)
                        
                        if result:
                            logger.info(f"✅ {username} foi puxado automaticamente")
                            
                            # Aguardar um pouco para garantir que o membro foi adicionado
                            import asyncio
                            await asyncio.sleep(2)
                            
                            # Buscar membro novamente
                            member = guild.get_member(int(user_id))
                    
                    # Adicionar cargo de verificado
                    if member and config and config.get('verified_role'):
                        try:
                            role = guild.get_role(int(config['verified_role']))
                            if role:
                                await member.add_roles(role, reason="OAuth2 autorizado")
                                logger.info(f"✅ Cargo {role.name} adicionado a {username}")
                        except Exception as e:
                            logger.error(f"Erro ao adicionar cargo a {username}: {e}")
                
                # Notificar em logs
                if guild:
                    config = self.bot.db.get_config(guild_id)
                    log_channel_id = int(config.get('log_channel', Config.LOG_CHANNEL_ID)) if config else Config.LOG_CHANNEL_ID
                    log_channel = self.bot.get_channel(log_channel_id)
                    if log_channel:
                        embed = discord.Embed(
                            title="🔐 Nova Autorização OAuth2",
                            description=f"**{username}** autorizou o sistema OAuth2!",
                            color=Config.COLORS['success'],
                            timestamp=datetime.utcnow()
                        )
                        embed.add_field(name="ID do Usuário", value=user_id)
                        
                        # Verificar se o cargo foi adicionado
                        if config and config.get('verified_role'):
                            role = guild.get_role(int(config['verified_role']))
                            if role:
                                embed.add_field(name="Cargo Adicionado", value=role.mention, inline=False)
                        
                        embed.set_footer(text="Panda Store")
                        await log_channel.send(embed=embed)
                
                return await render_template('success.html', username=username)
                
            except Exception as e:
                logger.error(f"Erro no callback OAuth2: {e}")
                return await render_template('error.html', error=str(e))
        
        @self.app.route('/dashboard')
        async def dashboard():
            """Painel administrativo"""
            auth = request.headers.get('Authorization') or request.cookies.get('auth')
            
            if auth != self.web_password:
                return await render_template('login.html')
            
            stats = self.bot.db.get_stats()
            
            return await render_template('dashboard.html',
                                        stats=stats,
                                        guilds=len(self.bot.guilds),
                                        users=len(self.bot.users))
        
        @self.app.route('/api/login', methods=['POST'])
        async def api_login():
            """API de login"""
            data = await request.get_json()
            password = data.get('password')
            
            if password == self.web_password:
                response = jsonify({'success': True})
                response.set_cookie('auth', password, max_age=86400)
                return response
            
            return jsonify({'success': False, 'error': 'Senha incorreta'}), 401
        
        @self.app.route('/api/stats')
        async def api_stats():
            """API de estatísticas"""
            auth = request.headers.get('Authorization') or request.cookies.get('auth')
            if auth != self.web_password:
                return jsonify({'error': 'Não autorizado'}), 401
            
            stats = self.bot.db.get_stats()
            return jsonify(stats)
        
        @self.app.route('/health')
        async def health():
            """Health check para Railway"""
            return jsonify({
                'status': 'online',
                'guilds': len(self.bot.guilds),
                'users': len(self.bot.users)
            })
        
        # ===================== ROTAS DO STRIPE =====================
        @self.app.route('/webhook/stripe', methods=['POST'])
        async def stripe_webhook():
            """Webhook do Stripe"""
            payload = await request.get_data()
            sig_header = request.headers.get('Stripe-Signature')
            
            try:
                payments_cog = self.bot.get_cog('Payments')
                if not payments_cog or not payments_cog.webhook_secret:
                    logger.error("Webhook secret não configurado")
                    return jsonify({'error': 'Configuration error'}), 500
                
                event = stripe.Webhook.construct_event(
                    payload, sig_header, payments_cog.webhook_secret
                )
            except ValueError:
                logger.error("Payload inválido do Stripe")
                return jsonify({'error': 'Invalid payload'}), 400
            except stripe.error.SignatureVerificationError:
                logger.error("Assinatura inválida do Stripe")
                return jsonify({'error': 'Invalid signature'}), 400
            
            if event['type'] == 'checkout.session.completed':
                session = event['data']['object']
                payments_cog = self.bot.get_cog('Payments')
                if payments_cog:
                    await payments_cog.handle_successful_payment(session)
                    logger.info(f"✅ Pagamento processado: {session['id']}")
            
            return jsonify({'success': True})

        @self.app.route('/payment/success')
        async def payment_success():
            """Página de sucesso do pagamento"""
            return await render_template('payment_success.html')

        @self.app.route('/payment/cancel')
        async def payment_cancel():
            """Página de cancelamento do pagamento"""
            return await render_template('payment_cancel.html')
    
    async def exchange_code(self, code):
        """Trocar código por tokens"""
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.redirect_uri
        }
        
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'{self.api_endpoint}/oauth2/token',
                data=data,
                headers=headers
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
    
    async def get_user_info(self, access_token):
        """Obter informações do usuário"""
        headers = {'Authorization': f'Bearer {access_token}'}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f'{self.api_endpoint}/users/@me',
                headers=headers
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
    
    async def add_user_to_guild(self, user_id, guild_id, access_token):
        """Adicionar usuário ao servidor"""
        headers = {
            'Authorization': f'Bot {os.getenv("BOT_TOKEN")}',
            'Content-Type': 'application/json'
        }
        
        data = {'access_token': access_token}
        
        async with aiohttp.ClientSession() as session:
            async with session.put(
                f'{self.api_endpoint}/guilds/{guild_id}/members/{user_id}',
                headers=headers,
                json=data
            ) as resp:
                return resp.status in [200, 201, 204]
    
    async def start(self):
        """Iniciar servidor web"""
        port = int(os.getenv('PORT', 3000))
        logger.info(f"🌐 Servidor web iniciando na porta {port}...")
        await self.app.run_task(host='0.0.0.0', port=port)