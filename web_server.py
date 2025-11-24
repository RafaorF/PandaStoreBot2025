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
        
        # ===================== PÁGINAS PÚBLICAS =====================
        @self.app.route('/')
        async def home():
            """Landing page principal"""
            stats = self.bot.db.get_stats()
            return await render_template('home.html',
                                        bot_name=self.bot.user.name if self.bot.user else 'PandaBot',
                                        bot_avatar=self.bot.user.display_avatar.url if self.bot.user else '',
                                        guilds=len(self.bot.guilds),
                                        users=len(self.bot.users),
                                        oauth_users=stats['total_users'],
                                        tickets=stats['total_tickets'])
        
        @self.app.route('/features')
        async def features():
            """Página de funcionalidades"""
            return await render_template('features.html',
                                        bot_name=self.bot.user.name if self.bot.user else 'PandaBot')
        
        @self.app.route('/commands')
        async def commands():
            """Página de comandos"""
            # Organizar comandos por categoria
            commands_list = {
                'OAuth2': [
                    {'name': '/oauth', 'description': 'Sistema de autorização OAuth2', 'usage': '/oauth'},
                    {'name': '/puxar', 'description': 'Puxar usuários de volta ao servidor', 'usage': '/puxar [user_id]'},
                    {'name': '/puxarlist', 'description': 'Ver lista de usuários OAuth2', 'usage': '/puxarlist [page]'},
                ],
                'Tickets': [
                    {'name': '/setup-tickets', 'description': 'Configurar painel de tickets', 'usage': '/setup-tickets'},
                ],
                'Moderação': [
                    {'name': '/kick', 'description': 'Expulsar um membro', 'usage': '/kick <membro> [motivo]'},
                    {'name': '/ban', 'description': 'Banir um membro', 'usage': '/ban <membro> [motivo]'},
                    {'name': '/unban', 'description': 'Desbanir um usuário', 'usage': '/unban <user_id>'},
                    {'name': '/mute', 'description': 'Mutar um membro', 'usage': '/mute <membro> [duração] [motivo]'},
                    {'name': '/unmute', 'description': 'Desmutar um membro', 'usage': '/unmute <membro>'},
                    {'name': '/clear', 'description': 'Limpar mensagens', 'usage': '/clear [quantidade]'},
                ],
                'Utilidades': [
                    {'name': '/ping', 'description': 'Ver latência do bot', 'usage': '/ping'},
                    {'name': '/serverinfo', 'description': 'Informações do servidor', 'usage': '/serverinfo'},
                    {'name': '/userinfo', 'description': 'Informações de um usuário', 'usage': '/userinfo [usuário]'},
                    {'name': '/botinfo', 'description': 'Informações do bot', 'usage': '/botinfo'},
                    {'name': '/avatar', 'description': 'Ver avatar de um usuário', 'usage': '/avatar [usuário]'},
                ],
                'Configuração': [
                    {'name': '/config', 'description': 'Painel de configuração', 'usage': '/config'},
                    {'name': '/setup-verificacao', 'description': 'Sistema de verificação', 'usage': '/setup-verificacao <canal>'},
                ],
                'Anúncios': [
                    {'name': '/avisos', 'description': 'Enviar avisos personalizados', 'usage': '/avisos <canal>'},
                    {'name': '/regras', 'description': 'Enviar regras do servidor', 'usage': '/regras <canal>'},
                    {'name': '/termos', 'description': 'Enviar termos de compra', 'usage': '/termos <canal>'},
                ],
                'Enquetes': [
                    {'name': '/enquete', 'description': 'Criar enquete personalizada', 'usage': '/enquete <pergunta> <opções>'},
                    {'name': '/enquete-simples', 'description': 'Criar enquete sim/não', 'usage': '/enquete-simples <pergunta>'},
                ],
                'Pagamentos': [
                    {'name': '/pagar', 'description': 'Criar link de pagamento Stripe', 'usage': '/pagar <valor> [moeda]'},
                ],
            }
            
            return await render_template('commands.html',
                                        bot_name=self.bot.user.name if self.bot.user else 'PandaBot',
                                        commands=commands_list)
        
        @self.app.route('/docs')
        async def docs():
            """Página de documentação"""
            return await render_template('docs.html',
                                        bot_name=self.bot.user.name if self.bot.user else 'PandaBot')
        
        @self.app.route('/status')
        async def status():
            """Página de status do bot"""
            stats = self.bot.db.get_stats()
            uptime = datetime.utcnow() - self.bot.start_time
            
            # Status dos serviços
            services = {
                'discord': {'status': 'online' if self.bot.is_ready() else 'offline', 'latency': round(self.bot.latency * 1000)},
                'database': {'status': 'online', 'users': stats['total_users']},
                'oauth': {'status': 'online', 'active': stats['total_users']},
                'tickets': {'status': 'online', 'total': stats['total_tickets']},
                'stripe': {'status': 'online' if os.getenv('STRIPE_SECRET_KEY') else 'disabled'}
            }
            
            return await render_template('status.html',
                                        bot_name=self.bot.user.name if self.bot.user else 'PandaBot',
                                        uptime_seconds=int(uptime.total_seconds()),
                                        guilds=len(self.bot.guilds),
                                        users=len(self.bot.users),
                                        services=services)
        
        @self.app.route('/invite')
        async def invite():
            """Redirecionar para link de convite"""
            invite_url = f"https://discord.com/api/oauth2/authorize?client_id={self.client_id}&permissions=8&scope=bot%20applications.commands"
            return redirect(invite_url)
        
        @self.app.route('/support')
        async def support():
            """Redirecionar para servidor de suporte"""
            support_url = os.getenv('SUPPORT_SERVER', 'https://discord.gg/VmjEN8xCYP')
            return redirect(support_url)
        
        # ===================== OAUTH2 =====================
        @self.app.route('/oauth/callback')
        async def oauth_callback():
            """Callback do OAuth2"""
            code = request.args.get('code')
            
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
                    member = guild.get_member(int(user_id))
                    
                    if not member:
                        result = await self.add_user_to_guild(user_id, guild_id, access_token)
                        if result:
                            logger.info(f"✅ {username} foi puxado automaticamente")
                            import asyncio
                            await asyncio.sleep(2)
                            member = guild.get_member(int(user_id))
                    
                    # Adicionar cargo
                    if member and config and config.get('verified_role'):
                        try:
                            role = guild.get_role(int(config['verified_role']))
                            if role:
                                await member.add_roles(role, reason="OAuth2 autorizado")
                                logger.info(f"✅ Cargo {role.name} adicionado a {username}")
                        except Exception as e:
                            logger.error(f"Erro ao adicionar cargo: {e}")
                
                return await render_template('success.html', username=username)
                
            except Exception as e:
                logger.error(f"Erro no callback OAuth2: {e}")
                return await render_template('error.html', error=str(e))
        
        # ===================== DASHBOARD ADMIN =====================
        @self.app.route('/dashboard')
        async def dashboard():
            """Painel administrativo"""
            auth = request.headers.get('Authorization') or request.cookies.get('auth')
            
            if auth != self.web_password:
                return await render_template('login.html')
            
            stats = self.bot.db.get_stats()
            backups = self.bot.db.get_all_backups()
            
            return await render_template('dashboard.html',
                                        stats=stats,
                                        guilds=len(self.bot.guilds),
                                        users=len(self.bot.users),
                                        backups=backups)
        
        # ===================== API =====================
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
            """API de estatísticas públicas"""
            stats = self.bot.db.get_stats()
            uptime = datetime.utcnow() - self.bot.start_time
            
            return jsonify({
                'guilds': len(self.bot.guilds),
                'users': len(self.bot.users),
                'oauth_users': stats['total_users'],
                'tickets': stats['total_tickets'],
                'uptime': int(uptime.total_seconds()),
                'status': 'online' if self.bot.is_ready() else 'offline',
                'latency': round(self.bot.latency * 1000)
            })
        
        @self.app.route('/api/backup/create', methods=['POST'])
        async def api_create_backup():
            """API para criar backup"""
            auth = request.headers.get('Authorization') or request.cookies.get('auth')
            if auth != self.web_password:
                return jsonify({'error': 'Não autorizado'}), 401
            
            try:
                backup_path = self.bot.db.backup()
                if backup_path:
                    return jsonify({'success': True, 'backup': backup_path})
                return jsonify({'success': False, 'error': 'Erro ao criar backup'}), 500
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/backup/download/<filename>')
        async def api_download_backup(filename):
            """API para download de backup"""
            auth = request.args.get('auth') or request.cookies.get('auth')
            if auth != self.web_password:
                return jsonify({'error': 'Não autorizado'}), 401
            
            if not filename.startswith('backup_') or not filename.endswith('.db'):
                return jsonify({'error': 'Arquivo inválido'}), 400
            
            filepath = os.path.join('backups', filename)
            
            if not os.path.exists(filepath):
                return jsonify({'error': 'Arquivo não encontrado'}), 404
            
            return await send_file(filepath, mimetype='application/octet-stream', 
                                  as_attachment=True, attachment_filename=filename)
        
        @self.app.route('/health')
        async def health():
            """Health check"""
            return jsonify({
                'status': 'online',
                'guilds': len(self.bot.guilds),
                'users': len(self.bot.users),
                'oauth_users': self.bot.db.get_stats()['total_users']
            })
        
        # ===================== STRIPE WEBHOOKS =====================
        @self.app.route('/webhook/stripe', methods=['POST'])
        async def stripe_webhook():
            """Webhook do Stripe"""
            payload = await request.get_data()
            sig_header = request.headers.get('Stripe-Signature')
            
            try:
                payments_cog = self.bot.get_cog('Payments')
                if not payments_cog or not payments_cog.webhook_secret:
                    return jsonify({'error': 'Configuration error'}), 500
                
                event = stripe.Webhook.construct_event(payload, sig_header, payments_cog.webhook_secret)
            except:
                return jsonify({'error': 'Invalid request'}), 400
            
            if event['type'] == 'checkout.session.completed':
                session = event['data']['object']
                payments_cog = self.bot.get_cog('Payments')
                if payments_cog:
                    await payments_cog.handle_successful_payment(session)
            
            return jsonify({'success': True})
        
        @self.app.route('/payment/success')
        async def payment_success():
            """Página de sucesso do pagamento"""
            return await render_template('payment_success.html')
        
        @self.app.route('/payment/cancel')
        async def payment_cancel():
            """Página de cancelamento"""
            return await render_template('payment_cancel.html')
    
    # ===================== MÉTODOS AUXILIARES =====================
    async def exchange_code(self, code):
        """Trocar código por tokens"""
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.redirect_uri
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(f'{self.api_endpoint}/oauth2/token',
                                   data=data,
                                   headers={'Content-Type': 'application/x-www-form-urlencoded'}) as resp:
                return await resp.json() if resp.status == 200 else None
    
    async def get_user_info(self, access_token):
        """Obter informações do usuário"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f'{self.api_endpoint}/users/@me',
                                  headers={'Authorization': f'Bearer {access_token}'}) as resp:
                return await resp.json() if resp.status == 200 else None
    
    async def add_user_to_guild(self, user_id, guild_id, access_token):
        """Adicionar usuário ao servidor"""
        headers = {
            'Authorization': f'Bot {os.getenv("BOT_TOKEN")}',
            'Content-Type': 'application/json'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.put(f'{self.api_endpoint}/guilds/{guild_id}/members/{user_id}',
                                  headers=headers, json={'access_token': access_token}) as resp:
                return resp.status in [200, 201, 204]
    
    async def start(self):
        """Iniciar servidor web"""
        port = int(os.getenv('PORT', 3000))
        logger.info(f"🌐 Servidor web iniciando na porta {port}...")
        await self.app.run_task(host='0.0.0.0', port=port)