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
    
    @app_commands.command(name="puxar", description="Puxar usuário de volta ao servidor (Staff)")
    @app_commands.describe(user_id="ID do usuário para puxar")
    @app_commands.check(lambda interaction: Permissions.is_staff(interaction.user))
    async def puxar_command(self, interaction: discord.Interaction, user_id: str):
        """Puxar usuário manualmente"""
        
        await interaction.response.defer(ephemeral=True)
        
        # Verificar se usuário tem OAuth2
        oauth_data = self.bot.db.get_oauth_user(user_id)
        
        if not oauth_data:
            embed = EmbedBuilder.error(
                "Erro",
                f"Usuário `{user_id}` não tem OAuth2 autorizado.",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        try:
            # Obter informações do usuário
            user = await self.bot.fetch_user(int(user_id))
            
            # Verificar se já está no servidor
            member = interaction.guild.get_member(int(user_id))
            if member:
                embed = EmbedBuilder.warning(
                    "Usuário Já no Servidor",
                    f"{user.mention} já está no servidor!",
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Tentar puxar
            access_token = oauth_data['access_token']
            
            # Adicionar ao servidor
            headers = {
                'Authorization': f'Bot {self.bot.http.token}',
                'Content-Type': 'application/json'
            }
            
            data = {'access_token': access_token}
            
            async with aiohttp.ClientSession() as session:
                async with session.put(
                    f'{self.api_endpoint}/guilds/{interaction.guild.id}/members/{user_id}',
                    headers=headers,
                    json=data
                ) as resp:
                    if resp.status in [200, 201, 204]:
                        # Sucesso!
                        self.bot.db.update_last_pulled(user_id)
                        self.bot.db.increment_stat('successful_pulls')
                        
                        embed = EmbedBuilder.success(
                            "Usuário Puxado",
                            f"**{user.name}** foi adicionado ao servidor com sucesso!",
                            thumbnail=user.display_avatar.url,
                            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                        )
                        
                        # Adicionar cargo de verificado
                        config = self.bot.db.get_config(str(interaction.guild.id))
                        if config and config.get('verified_role'):
                            try:
                                member = await interaction.guild.fetch_member(int(user_id))
                                role = interaction.guild.get_role(int(config['verified_role']))
                                if role and member:
                                    await member.add_roles(role)
                                    embed.add_field(name="Cargo Adicionado", value=role.mention, inline=False)
                            except:
                                pass
                        
                        # Log
                        log_channel_id = int(config.get('log_channel', Config.LOG_CHANNEL_ID)) if config else Config.LOG_CHANNEL_ID
                        log_channel = self.bot.get_channel(log_channel_id)
                        if log_channel:
                            log_embed = EmbedBuilder.success(
                                "🔄 Usuário Puxado Manualmente",
                                f"**{user.name}** foi puxado por {interaction.user.mention}",
                                thumbnail=user.display_avatar.url,
                                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                            )
                            await log_channel.send(embed=log_embed)
                        
                        await interaction.followup.send(embed=embed, ephemeral=True)
                    else:
                        # Erro
                        error_msg = await resp.text()
                        logger.error(f"Erro ao puxar {user_id}: {resp.status} - {error_msg}")
                        
                        self.bot.db.increment_stat('failed_pulls')
                        
                        embed = EmbedBuilder.error(
                            "Erro ao Puxar",
                            f"Não foi possível puxar o usuário.\n\n**Status:** {resp.status}\n**Detalhes:** {error_msg[:100]}",
                            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                        )
                        await interaction.followup.send(embed=embed, ephemeral=True)
        
        except Exception as e:
            logger.error(f"Erro ao puxar usuário {user_id}: {e}")
            embed = EmbedBuilder.error(
                "Erro",
                f"Ocorreu um erro ao puxar o usuário:\n```{str(e)}```",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def refresh_token(self, user_id):
        """Renovar access token"""
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
                    logger.error(f"❌ Erro ao renovar token para {user_id}")
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