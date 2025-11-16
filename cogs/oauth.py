import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os
from datetime import datetime, timedelta
import logging
from utils import EmbedBuilder, Config, Permissions

logger = logging.getLogger('PandaBot.OAuth')

class OAuth(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client_id = os.getenv('CLIENT_ID')
        self.client_secret = os.getenv('CLIENT_SECRET')
        self.redirect_uri = os.getenv('REDIRECT_URI')
        self.api_endpoint = 'https://discord.com/api/v10'
    
    def generate_auth_url(self, user_id=None):
        """Gerar URL de autorização OAuth2"""
        scopes = os.getenv('OAUTH_SCOPES', 'identify guilds.join')
        redirect_uri = self.redirect_uri or "https://pandastore.railway.app/oauth/callback"

        base = "https://discord.com/oauth2/authorize"
        url = (
        f"{base}?client_id={self.client_id}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&scope={scopes.replace(' ', '+')}"
    )
        if user_id:
           url += f"&state={user_id}"

        return url
    
    @app_commands.command(name="oauth", description="Sistema de autorização OAuth2")
    async def oauth_command(self, interaction: discord.Interaction):
        """Comando principal de OAuth2"""
        
        # Verificar blacklist
        if self.bot.db.is_blacklisted(str(interaction.user.id)):
            blacklist_data = self.bot.db.get_all_blacklisted()
            user_blacklist = next((b for b in blacklist_data if b['user_id'] == str(interaction.user.id)), None)
            
            embed = EmbedBuilder.error(
                "Acesso Negado",
                "Você está na blacklist e não pode usar este sistema.",
                fields=[{"name": "Motivo", "value": user_blacklist.get('reason', 'Não especificado')}],
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Verificar se usuário já tem OAuth2
        user_data = self.bot.db.get_oauth_user(str(interaction.user.id))
        
        if user_data:
            # Usuário já autorizado
            expires_at = user_data['expires_at']
            expires_in = expires_at - int(datetime.utcnow().timestamp())
            days = expires_in // 86400
            hours = (expires_in % 86400) // 3600
            
            embed = EmbedBuilder.success(
                "OAuth2 Ativo",
                "Sua autorização OAuth2 está ativa e funcionando!",
                thumbnail=interaction.user.display_avatar.url,
                fields=[
                    {"name": "📅 Autorizado em", "value": f"<t:{user_data['added_at']}:F>", "inline": True},
                    {"name": "⏰ Expira em", "value": f"{days}d {hours}h", "inline": True},
                    {"name": "🔄 Renovação", "value": "**Automática**", "inline": True},
                    {"name": "🛡️ Status", "value": "**Protegido**", "inline": True},
                    {"name": "🔄 Último Pull", "value": f"<t:{user_data['last_pulled']}:R>" if user_data['last_pulled'] else "Nunca", "inline": True}
                ],
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            
            view = OAuthActiveView(self)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            # Usuário não autorizado
            auth_url = self.generate_auth_url(interaction.user.id)
            
            embed = EmbedBuilder.create_embed(
                "🔐 Sistema de Autorização OAuth2",
                "Autorize o bot a te adicionar de volta ao servidor automaticamente caso você saia!",
                color=Config.COLORS['panda'],
                thumbnail=interaction.user.display_avatar.url,
                fields=[
                    {
                        "name": "📋 Como funciona?",
                        "value": "• Clique em **Autorizar OAuth2**\n• Você será redirecionado para o Discord\n• Autorize as permissões necessárias\n• Pronto! Você estará protegido 🛡️"
                    },
                    {
                        "name": "✨ Benefícios",
                        "value": "✅ Retorno automático ao servidor\n✅ Recuperação de cargos\n✅ Sem perder seu histórico\n✅ 100% seguro e confiável\n✅ Renovação automática"
                    },
                    {
                        "name": "🔒 Privacidade",
                        "value": "Apenas armazenamos as permissões necessárias para te adicionar de volta."
                    },
                    {
                        "name": "⏱️ Validade",
                        "value": "A autorização dura 7 dias e é **renovada automaticamente**!"
                    }
                ],
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            
            view = OAuthAuthView(auth_url)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @app_commands.command(name="puxarlist", description="Ver lista de usuários com OAuth2 autorizado")
    @app_commands.describe(page="Página da lista (padrão: 1)")
    @app_commands.check(lambda interaction: Permissions.is_staff(interaction.user))
    async def puxarlist_command(self, interaction: discord.Interaction, page: int = 1):
        """Ver lista completa de usuários OAuth2"""
        
        await interaction.response.defer(ephemeral=True)
        
        # Obter todos os usuários OAuth2
        oauth_users = self.bot.db.get_all_oauth_users()
        
        if not oauth_users:
            embed = EmbedBuilder.warning(
                "Lista Vazia",
                "Nenhum usuário tem OAuth2 autorizado ainda.",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Paginação
        per_page = 10
        total_pages = (len(oauth_users) - 1) // per_page + 1
        page = max(1, min(page, total_pages))
        
        start = (page - 1) * per_page
        end = start + per_page
        page_users = oauth_users[start:end]
        
        # Criar lista formatada
        user_list = []
        current_time = int(datetime.utcnow().timestamp())
        
        for user_data in page_users:
            try:
                user = await self.bot.fetch_user(int(user_data['user_id']))
                
                # Verificar se está no servidor
                member = interaction.guild.get_member(int(user_data['user_id']))
                status = "🟢 No servidor" if member else "🔴 Fora"
                
                # Verificar expiração do token
                expires_at = user_data['expires_at']
                time_left = expires_at - current_time
                
                if time_left > 86400:  # Mais de 1 dia
                    days = time_left // 86400
                    token_status = f"✅ {days}d"
                elif time_left > 0:
                    hours = time_left // 3600
                    token_status = f"⚠️ {hours}h"
                else:
                    token_status = "❌ Expirado"
                
                # Último pull
                if user_data.get('last_pulled') and user_data['last_pulled'] > 0:
                    last_pull = f"<t:{user_data['last_pulled']}:R>"
                else:
                    last_pull = "Nunca"
                
                user_list.append(
                    f"**{user.name}** ({status})\n"
                    f"├ ID: `{user.id}`\n"
                    f"├ Token: {token_status}\n"
                    f"└ Último pull: {last_pull}"
                )
            except Exception as e:
                logger.error(f"Erro ao buscar usuário {user_data['user_id']}: {e}")
                user_list.append(
                    f"**Usuário Desconhecido**\n"
                    f"├ ID: `{user_data['user_id']}`\n"
                    f"└ ⚠️ Erro ao carregar dados"
                )
        
        # Estatísticas gerais
        total_users = len(oauth_users)
        users_in_server = sum(1 for u in oauth_users if interaction.guild.get_member(int(u['user_id'])))
        users_out = total_users - users_in_server
        
        # Tokens expirados
        expired_tokens = sum(1 for u in oauth_users if u['expires_at'] < current_time)
        
        embed = EmbedBuilder.create_embed(
            "📋 Lista de Usuários OAuth2",
            "\n\n".join(user_list),
            color=Config.COLORS['info'],
            thumbnail=interaction.guild.icon.url if interaction.guild.icon else None,
            fields=[
                {
                    "name": "📊 Estatísticas",
                    "value": f"**Total:** {total_users}\n**No servidor:** 🟢 {users_in_server}\n**Fora:** 🔴 {users_out}\n**Tokens expirados:** ❌ {expired_tokens}",
                    "inline": True
                },
                {
                    "name": "📄 Paginação",
                    "value": f"Página **{page}** de **{total_pages}**\nUse `/puxarlist page:{page+1}` para próxima",
                    "inline": True
                }
            ],
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="puxar", description="Puxar usuário(s) de volta ao servidor (Staff)")
    @app_commands.describe(user_id="ID do usuário para puxar (opcional)")
    @app_commands.check(lambda interaction: Permissions.is_staff(interaction.user))
    async def puxar_command(self, interaction: discord.Interaction, user_id: str = None):
        """Puxar um ou todos os usuários manualmente"""
        
        await interaction.response.defer(ephemeral=True)
        
        # Obter lista de usuários OAuth
        if user_id:
            oauth_users = [self.bot.db.get_oauth_user(user_id)]
        else:
            oauth_users = self.bot.db.get_all_oauth_users()

        if not oauth_users or all(u is None for u in oauth_users):
            embed = EmbedBuilder.error(
                "Erro",
                "Nenhum usuário OAuth2 encontrado." if not user_id else f"Usuário `{user_id}` não tem OAuth2 autorizado.",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        total_puxados = 0
        total_falhados = 0
        
        for user_data in oauth_users:
            if not user_data:
                continue
            
            uid = user_data['user_id']
            try:
                user = await self.bot.fetch_user(int(uid))
                
                # Verificar se já está no servidor
                member = interaction.guild.get_member(int(uid))
                if member:
                    logger.info(f"⏭️ {user.name} já está no servidor, pulando...")
                    continue
                
                # ✅ VERIFICAR E RENOVAR TOKEN SE EXPIRADO
                access_token = await self.ensure_valid_token(uid, user_data)
                
                if not access_token:
                    logger.error(f"❌ Token inválido para {user.name}, não foi possível renovar")
                    total_falhados += 1
                    continue
                
                # Tentar puxar com token válido
                headers = {
                    'Authorization': f'Bot {self.bot.http.token}',
                    'Content-Type': 'application/json'
                }
                
                data = {'access_token': access_token}
                
                async with aiohttp.ClientSession() as session:
                    async with session.put(
                        f'{self.api_endpoint}/guilds/{interaction.guild.id}/members/{uid}',
                        headers=headers,
                        json=data
                    ) as resp:
                        if resp.status in [200, 201, 204]:
                            self.bot.db.update_last_pulled(uid)
                            self.bot.db.increment_stat('successful_pulls')
                            total_puxados += 1
                            logger.info(f"✅ {user.name} puxado com sucesso!")
                        else:
                            error_text = await resp.text()
                            logger.error(f"❌ Erro ao puxar {user.name}: {resp.status} - {error_text}")
                            total_falhados += 1
            
            except Exception as e:
                total_falhados += 1
                logger.error(f"Erro ao puxar usuário {uid}: {e}")
        
        embed = EmbedBuilder.success(
            "Puxar Usuários",
            f"✅ **{total_puxados}** usuário(s) puxado(s) com sucesso.\n❌ **{total_falhados}** falharam.",
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def ensure_valid_token(self, user_id, user_data):
        """
        Garantir que o token é válido, renovando se necessário.
        Retorna o access_token válido ou None se falhar.
        """
        current_time = int(datetime.utcnow().timestamp())
        expires_at = user_data['expires_at']
        
        # Se o token ainda é válido por pelo menos 1 hora, usar ele
        if expires_at > (current_time + 3600):
            logger.info(f"✅ Token de {user_id} ainda é válido")
            return user_data['access_token']
        
        # Token expirado ou expirando em breve - renovar!
        logger.info(f"🔄 Token de {user_id} expirado/expirando, renovando...")
        new_token = await self.refresh_token(user_id)
        
        if new_token:
            logger.info(f"✅ Token de {user_id} renovado com sucesso!")
            return new_token
        else:
            logger.error(f"❌ Falha ao renovar token de {user_id}")
            return None
    
    async def refresh_token(self, user_id):
        """Renovar access token - Retorna o novo access_token ou None"""
        user_data = self.bot.db.get_oauth_user(user_id)
        
        if not user_data or not user_data.get('refresh_token'):
            logger.error(f"Sem refresh token para {user_id}")
            return None
        
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'refresh_token',
            'refresh_token': user_data['refresh_token']
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f'{self.api_endpoint}/oauth2/token',
                    data=data,
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                ) as resp:
                    if resp.status == 200:
                        token_data = await resp.json()
                        
                        access_token = token_data['access_token']
                        refresh_token = token_data['refresh_token']
                        expires_in = token_data['expires_in']
                        expires_at = int((datetime.utcnow() + timedelta(seconds=expires_in)).timestamp())
                        
                        self.bot.db.add_oauth_user(user_id, access_token, refresh_token, expires_at)
                        logger.info(f"✅ Token renovado para {user_id}")
                        return access_token
                    else:
                        error_text = await resp.text()
                        logger.error(f"❌ Erro ao renovar token para {user_id}: {resp.status} - {error_text}")
                        return None
        except Exception as e:
            logger.error(f"❌ Exceção ao renovar token para {user_id}: {e}")
            return None

class OAuthAuthView(discord.ui.View):
    def __init__(self, auth_url):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(
            label="Autorizar OAuth2",
            emoji="🔐",
            style=discord.ButtonStyle.link,
            url=auth_url
        ))

class OAuthActiveView(discord.ui.View):
    def __init__(self, oauth_cog):
        super().__init__(timeout=300)
        self.oauth_cog = oauth_cog
    
    @discord.ui.button(label="Ver Detalhes", style=discord.ButtonStyle.primary, emoji="📊")
    async def details_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_data = self.oauth_cog.bot.db.get_oauth_user(str(interaction.user.id))
        
        embed = EmbedBuilder.info(
            "Detalhes do OAuth2",
            f"Estatísticas completas de **{interaction.user.name}**",
            thumbnail=interaction.user.display_avatar.url,
            fields=[
                {
                    "name": "📅 Informações Temporais",
                    "value": f"```\nAutorizado: {datetime.fromtimestamp(user_data['added_at']).strftime('%d/%m/%Y %H:%M')}\nExpira: {datetime.fromtimestamp(user_data['expires_at']).strftime('%d/%m/%Y %H:%M')}\n```"
                },
                {
                    "name": "🔒 Segurança",
                    "value": "```\nStatus: Ativo ✅\nRenovação: Automática ✅\nBlacklist: Não 🟢\n```"
                }
            ],
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Revogar", style=discord.ButtonStyle.danger, emoji="🚫")
    async def revoke_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        confirm_view = ConfirmRevokeView(self.oauth_cog)
        
        embed = EmbedBuilder.warning(
            "Confirmar Revogação",
            "Tem certeza que deseja revogar sua autorização OAuth2?\n\n**Consequências:**\n• O bot não poderá mais te adicionar automaticamente\n• Você precisará autorizar novamente",
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)

class ConfirmRevokeView(discord.ui.View):
    def __init__(self, oauth_cog):
        super().__init__(timeout=30)
        self.oauth_cog = oauth_cog
    
    @discord.ui.button(label="Sim, Revogar", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.oauth_cog.bot.db.remove_oauth_user(str(interaction.user.id))
        
        embed = EmbedBuilder.success(
            "Autorização Revogada",
            "Sua autorização OAuth2 foi removida com sucesso.\n\nUse `/oauth` novamente para autorizar.",
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()
    
    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = EmbedBuilder.info(
            "Revogação Cancelada",
            "Sua autorização OAuth2 permanece ativa.",
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

async def setup(bot):
    await bot.add_cog(OAuth(bot))
