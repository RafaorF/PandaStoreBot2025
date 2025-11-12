from quart import Quart, request, jsonify, render_template_string, redirect
import aiohttp
import os
import logging
from datetime import datetime, timedelta
from utils import Config

logger = logging.getLogger('PandaBot.WebServer')

class WebServer:
    def __init__(self, bot):
        self.bot = bot
        self.app = Quart(__name__)
        self.setup_routes()
        
        self.client_id = os.getenv('CLIENT_ID')
        self.client_secret = os.getenv('CLIENT_SECRET')
        self.redirect_uri = os.getenv('REDIRECT_URI')
        self.oauth_scopes = os.getenv('OAUTH_SCOPES', 'identify guilds.join').split()
        self.api_endpoint = 'https://discord.com/api/v10'
    
    def setup_routes(self):
        """Configurar rotas do servidor"""
        
        @self.app.route('/')
        async def index():
            """Página inicial"""
            return await render_template_string("""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Panda Store Bot</title>
                <style>
                    * { margin: 0; padding: 0; box-sizing: border-box; }
                    body { 
                        font-family: 'Segoe UI', sans-serif;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        min-height: 100vh;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                    }
                    .container {
                        background: white;
                        padding: 50px;
                        border-radius: 20px;
                        box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                        text-align: center;
                        max-width: 500px;
                    }
                    h1 { color: #2c3e50; margin-bottom: 20px; }
                    .panda { font-size: 80px; margin-bottom: 20px; }
                    p { color: #7f8c8d; margin-bottom: 30px; }
                    .btn {
                        display: inline-block;
                        padding: 15px 30px;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        text-decoration: none;
                        border-radius: 10px;
                        font-weight: bold;
                        transition: transform 0.2s;
                    }
                    .btn:hover { transform: translateY(-2px); }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="panda">🐼</div>
                    <h1>Panda Store Bot</h1>
                    <p>Sistema OAuth2 e Gerenciamento de Tickets</p>
                    <a href="/dashboard" class="btn">Acessar Painel</a>
                </div>
            </body>
            </html>
            """)
        
        @self.app.route('/oauth/callback')
        async def oauth_callback():
            """Callback do OAuth2"""
            code = request.args.get('code')
            
            if not code:
                return "Código de autorização não fornecido", 400
            
            try:
                # Trocar código por tokens
                token_data = await self.exchange_code(code)
                
                if not token_data:
                    return await self.error_page("Erro ao obter tokens de acesso")
                
                access_token = token_data['access_token']
                refresh_token = token_data['refresh_token']
                expires_in = token_data['expires_in']
                
                # Obter informações do usuário
                user_info = await self.get_user_info(access_token)
                
                if not user_info:
                    return await self.error_page("Erro ao obter informações do usuário")
                
                user_id = user_info['id']
                username = user_info['username']
                
                # Salvar no banco
                expires_at = int((datetime.utcnow() + timedelta(seconds=expires_in)).timestamp())
                self.bot.db.add_oauth_user(user_id, access_token, refresh_token, expires_at)
                
                logger.info(f"✅ {username} ({user_id}) autorizou OAuth2")
                
                # Auto-puxar se configurado
                guild_id = os.getenv('GUILD_ID')
                config = self.bot.db.get_config(guild_id)
                
                if config and config.get('auto_pull'):
                    guild = self.bot.get_guild(int(guild_id))
                    if guild:
                        result = await self.add_user_to_guild(user_id, guild_id, access_token)
                        
                        if result:
                            logger.info(f"✅ {username} foi puxado automaticamente")
                            
                            # Adicionar cargo de verificado
                            if config.get('verified_role'):
                                try:
                                    member = await guild.fetch_member(int(user_id))
                                    role = guild.get_role(int(config['verified_role']))
                                    if role:
                                        await member.add_roles(role)
                                except:
                                    pass
                
                # Notificar em logs
                log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
                if log_channel:
                    embed = discord.Embed(
                        title="🔐 Nova Autorização OAuth2",
                        description=f"**{username}** autorizou o sistema OAuth2!",
                        color=Config.COLORS['success'],
                        timestamp=datetime.utcnow()
                    )
                    embed.add_field(name="ID do Usuário", value=user_id)
                    embed.set_footer(text="Panda Store")
                    await log_channel.send(embed=embed)
                
                return await self.success_page(username)
                
            except Exception as e:
                logger.error(f"Erro no callback OAuth2: {e}")
                return await self.error_page(str(e))
        
        @self.app.route('/dashboard')
        async def dashboard():
            """Painel administrativo"""
            auth = request.headers.get('Authorization')
            
            if auth != os.getenv('WEB_PASSWORD'):
                return await render_template_string("""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Login - Panda Store</title>
                    <style>
                        * { margin: 0; padding: 0; box-sizing: border-box; }
                        body { 
                            font-family: 'Segoe UI', sans-serif;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            min-height: 100vh;
                            display: flex;
                            justify-content: center;
                            align-items: center;
                        }
                        .login-box {
                            background: white;
                            padding: 40px;
                            border-radius: 15px;
                            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
                            max-width: 400px;
                            width: 100%;
                        }
                        h1 { color: #2c3e50; margin-bottom: 30px; text-align: center; }
                        input {
                            width: 100%;
                            padding: 15px;
                            border: 2px solid #ecf0f1;
                            border-radius: 8px;
                            margin-bottom: 20px;
                            font-size: 16px;
                        }
                        button {
                            width: 100%;
                            padding: 15px;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            color: white;
                            border: none;
                            border-radius: 8px;
                            font-size: 16px;
                            font-weight: bold;
                            cursor: pointer;
                        }
                    </style>
                </head>
                <body>
                    <div class="login-box">
                        <h1>🔐 Login do Painel</h1>
                        <input type="password" id="password" placeholder="Digite a senha">
                        <button onclick="login()">Entrar</button>
                    </div>
                    <script>
                        function login() {
                            const password = document.getElementById('password').value;
                            fetch('/dashboard', {
                                headers: { 'Authorization': password }
                            }).then(r => {
                                if (r.ok) window.location.reload();
                                else alert('Senha incorreta');
                            });
                        }
                    </script>
                </body>
                </html>
                """)
            
            # Dashboard completo (código HTML do painel)
            return "Dashboard em desenvolvimento"
        
        @self.app.route('/api/stats')
        async def api_stats():
            """API de estatísticas"""
            auth = request.headers.get('Authorization')
            if auth != os.getenv('WEB_PASSWORD'):
                return jsonify({'error': 'Não autorizado'}), 401
            
            stats = self.bot.db.get_stats(7)
            return jsonify(stats)
        
        @self.app.route('/health')
        async def health():
            """Health check para Railway"""
            return jsonify({
                'status': 'online',
                'guilds': len(self.bot.guilds),
                'users': len(self.bot.users)
            })
    
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
    
    async def success_page(self, username):
        """Página de sucesso"""
        return await render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Sucesso - OAuth2</title>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body { 
                    font-family: 'Segoe UI', sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                }
                .container {
                    background: white;
                    padding: 40px;
                    border-radius: 15px;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.3);
                    text-align: center;
                    max-width: 500px;
                }
                .success { color: #2ecc71; font-size: 60px; margin-bottom: 20px; }
                h1 { color: #2c3e50; margin-bottom: 10px; }
                p { color: #7f8c8d; margin-bottom: 20px; }
                .info {
                    background: #ecf0f1;
                    padding: 20px;
                    border-radius: 10px;
                    margin-top: 20px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success">✅</div>
                <h1>Autorização Concluída!</h1>
                <p>Olá, <strong>{{ username }}</strong>!</p>
                <p>Você autorizou o bot com sucesso. Agora você pode ser adicionado de volta ao servidor automaticamente!</p>
                <div class="info">
                    <p><strong>Status:</strong> ✅ Ativo</p>
                    <p><strong>Validade:</strong> 7 dias (renovado automaticamente)</p>
                </div>
                <p style="margin-top: 30px; font-size: 14px;">Você pode fechar esta janela.</p>
            </div>
        </body>
        </html>
        """, username=username)
    
    async def error_page(self, error):
        """Página de erro"""
        return await render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Erro - OAuth2</title>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body { 
                    font-family: 'Segoe UI', sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                }
                .container {
                    background: white;
                    padding: 40px;
                    border-radius: 15px;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.3);
                    text-align: center;
                    max-width: 500px;
                }
                .error { color: #e74c3c; font-size: 60px; margin-bottom: 20px; }
                h1 { color: #2c3e50; margin-bottom: 10px; }
                p { color: #7f8c8d; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="error">❌</div>
                <h1>Erro na Autorização</h1>
                <p>{{ error }}</p>
                <p style="margin-top: 20px;">Tente novamente usando <strong>/oauth</strong> no Discord.</p>
            </div>
        </body>
        </html>
        """, error=error)
    
    async def start(self):
        """Iniciar servidor web"""
        port = int(os.getenv('PORT', 3000))
        logger.info(f"🌐 Servidor web iniciando na porta {port}...")
        await self.app.run_task(host='0.0.0.0', port=port)