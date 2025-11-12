import discord
from discord.ext import commands
from discord import app_commands
import logging
from datetime import datetime
from utils import EmbedBuilder, Config, TranscriptGenerator, Permissions
import os

logger = logging.getLogger('PandaBot.Tickets')

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ticket_category_id = Config.TICKET_CATEGORY_ID
        self.cart_category_id = Config.CART_CATEGORY_ID
    
    @app_commands.command(name="ticket", description="Abrir um ticket de suporte")
    async def ticket_command(self, interaction: discord.Interaction):
        """Abrir ticket de suporte"""
        await self.create_ticket(interaction, "ticket")
    
    @app_commands.command(name="compra", description="Abrir um carrinho de compra")
    async def compra_command(self, interaction: discord.Interaction):
        """Abrir carrinho de compra"""
        await self.create_ticket(interaction, "compra")
    
    async def create_ticket(self, interaction: discord.Interaction, ticket_type: str):
        """Criar ticket ou compra"""
        
        # Verificar se já tem ticket aberto
        existing_tickets = self.bot.db.get_user_tickets(str(interaction.user.id))
        open_tickets = [t for t in existing_tickets if t['status'] == 'open']
        
        if open_tickets:
            embed = EmbedBuilder.warning(
                "Ticket Já Aberto",
                f"Você já tem um ticket aberto: <#{open_tickets[0]['channel_id']}>",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Categoria correta
        category_id = self.ticket_category_id if ticket_type == "ticket" else self.cart_category_id
        category = interaction.guild.get_channel(category_id)
        
        if not category:
            embed = EmbedBuilder.error(
                "Erro",
                "Categoria de tickets não encontrada. Contate um administrador.",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Criar canal
        channel_name = f"{'🎫-ticket' if ticket_type == 'ticket' else '🛒-compra'}-{interaction.user.name}"
        
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # Adicionar staff
        staff_role = interaction.guild.get_role(Config.STAFF_ROLE_ID)
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        try:
            channel = await category.create_text_channel(
                name=channel_name,
                overwrites=overwrites
            )
            
            # Salvar no banco
            ticket_id = self.bot.db.create_ticket(str(channel.id), str(interaction.user.id), ticket_type)
            
            # Embed de boas-vindas
            emoji = "🎫" if ticket_type == "ticket" else "🛒"
            title = "Ticket de Suporte Aberto" if ticket_type == "ticket" else "Carrinho de Compra Aberto"
            
            embed = EmbedBuilder.create_embed(
                f"{emoji} {title}",
                f"Olá {interaction.user.mention}!\n\n" + 
                ("Nossa equipe responderá em breve. Por favor, **descreva seu problema detalhadamente**." if ticket_type == "ticket" else 
                 "Bem-vindo ao seu carrinho de compras! **Descreva o que deseja comprar** e nossa equipe te auxiliará."),
                color=Config.COLORS['panda'],
                thumbnail=interaction.guild.icon.url if interaction.guild.icon else None,
                fields=[
                    {
                        "name": "📝 Próximos Passos",
                        "value": "1️⃣ Descreva seu " + ("problema" if ticket_type == "ticket" else "pedido") + "\n2️⃣ Aguarde a equipe\n3️⃣ Após finalizar, avalie o atendimento"
                    }
                ],
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            
            view = TicketControlView(self.bot, ticket_type)
            await channel.send(f"{interaction.user.mention} | {staff_role.mention if staff_role else ''}", embed=embed, view=view)
            
            # Responder
            success_embed = EmbedBuilder.success(
                "Ticket Criado",
                f"Seu {'ticket' if ticket_type == 'ticket' else 'carrinho'} foi criado: {channel.mention}",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.response.send_message(embed=success_embed, ephemeral=True)
            
            # Log
            log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
            if log_channel:
                log_embed = EmbedBuilder.info(
                    f"{emoji} {'Ticket' if ticket_type == 'ticket' else 'Compra'} Aberto",
                    f"**Usuário:** {interaction.user.mention}\n**Canal:** {channel.mention}\n**Tipo:** {ticket_type.title()}",
                    thumbnail=interaction.user.display_avatar.url,
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                await log_channel.send(embed=log_embed)
            
        except Exception as e:
            logger.error(f"Erro ao criar ticket: {e}")
            embed = EmbedBuilder.error(
                "Erro ao Criar Ticket",
                f"Ocorreu um erro: {str(e)}",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Detectar primeira mensagem no ticket para perguntar motivo"""
        if message.author.bot:
            return
        
        ticket_data = self.bot.db.get_ticket(str(message.channel.id))
        if not ticket_data or ticket_data['status'] != 'open':
            return
        
        # Verificar se é a primeira mensagem do usuário
        async for msg in message.channel.history(limit=10, oldest_first=True):
            if msg.author.id == message.author.id and msg.id != message.id:
                return  # Já enviou mensagens antes
        
        # Confirmar recebimento
        embed = EmbedBuilder.success(
            "Mensagem Recebida",
            "Obrigado por descrever seu " + ("problema" if ticket_data['type'] == 'ticket' else "pedido") + "!\n\nNossa equipe irá responder em breve. 🕐",
            footer_icon=message.guild.icon.url if message.guild.icon else None
        )
        await message.channel.send(embed=embed, delete_after=10)

class TicketControlView(discord.ui.View):
    def __init__(self, bot, ticket_type):
        super().__init__(timeout=None)
        self.bot = bot
        self.ticket_type = ticket_type
    
    @discord.ui.button(label="Fechar Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not Permissions.is_staff(interaction.user):
            return await interaction.response.send_message("❌ Apenas staff pode fechar tickets!", ephemeral=True)
        
        embed = EmbedBuilder.warning(
            "Confirmar Fechamento",
            "Tem certeza que deseja fechar este ticket?\n\nUma transcrição será enviada ao usuário e ao canal de logs.",
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        view = ConfirmCloseView(self.bot, self.ticket_type)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Adicionar Usuário", style=discord.ButtonStyle.primary, emoji="➕", custom_id="add_user")
    async def add_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not Permissions.is_staff(interaction.user):
            return await interaction.response.send_message("❌ Apenas staff pode adicionar usuários!", ephemeral=True)
        
        modal = AddUserModal(self.bot)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Remover Usuário", style=discord.ButtonStyle.secondary, emoji="➖", custom_id="remove_user")
    async def remove_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not Permissions.is_staff(interaction.user):
            return await interaction.response.send_message("❌ Apenas staff pode remover usuários!", ephemeral=True)
        
        modal = RemoveUserModal(self.bot)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Renomear", style=discord.ButtonStyle.secondary, emoji="✏️", custom_id="rename_ticket")
    async def rename_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not Permissions.is_staff(interaction.user):
            return await interaction.response.send_message("❌ Apenas staff pode renomear!", ephemeral=True)
        
        modal = RenameTicketModal(self.bot)
        await interaction.response.send_modal(modal)

class ConfirmCloseView(discord.ui.View):
    def __init__(self, bot, ticket_type):
        super().__init__(timeout=60)
        self.bot = bot
        self.ticket_type = ticket_type
    
    @discord.ui.button(label="Sim, Fechar", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        ticket_data = self.bot.db.get_ticket(str(interaction.channel.id))
        if not ticket_data:
            return await interaction.followup.send("❌ Ticket não encontrado no banco de dados!")
        
        # Gerar transcrição
        embed = EmbedBuilder.info(
            "Gerando Transcrição",
            "Por favor aguarde...",
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        await interaction.followup.send(embed=embed)
        
        try:
            transcript_path = await TranscriptGenerator.generate(interaction.channel)
            
            # Enviar por DM
            user = await self.bot.fetch_user(int(ticket_data['user_id']))
            dm_embed = EmbedBuilder.info(
                "Ticket Fechado",
                f"Seu {'ticket' if self.ticket_type == 'ticket' else 'carrinho'} foi fechado.\n\nAnexo: Transcrição completa.",
                thumbnail=interaction.guild.icon.url if interaction.guild.icon else None,
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            
            try:
                await user.send(embed=dm_embed, file=discord.File(transcript_path))
            except:
                logger.warning(f"Não foi possível enviar DM para {user.id}")
            
            # Enviar para logs
            log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
            if log_channel:
                log_embed = EmbedBuilder.info(
                    f"{'🎫 Ticket' if self.ticket_type == 'ticket' else '🛒 Compra'} Fechado",
                    f"**Usuário:** {user.mention}\n**Fechado por:** {interaction.user.mention}\n**Canal:** {interaction.channel.name}",
                    thumbnail=user.display_avatar.url,
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                await log_channel.send(embed=log_embed, file=discord.File(transcript_path))
            
            # Salvar no banco
            self.bot.db.close_ticket(str(interaction.channel.id), str(interaction.user.id), transcript_path)
            
            # Sistema de avaliação
            rating_view = RatingView(self.bot, ticket_data, self.ticket_type)
            rating_embed = EmbedBuilder.create_embed(
                "⭐ Avalie Nosso Atendimento",
                "Por favor, avalie o atendimento que você recebeu!",
                color=Config.COLORS['warning'],
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            
            try:
                await user.send(embed=rating_embed, view=rating_view)
            except:
                pass
            
            # Deletar canal
            await interaction.channel.send(embed=EmbedBuilder.success(
                "Ticket Fechado",
                "Este canal será deletado em 5 segundos...",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            ))
            
            await interaction.channel.delete(reason=f"Ticket fechado por {interaction.user}")
            
        except Exception as e:
            logger.error(f"Erro ao fechar ticket: {e}")
            await interaction.followup.send(f"❌ Erro: {str(e)}")
    
    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=EmbedBuilder.info("Cancelado", "Fechamento cancelado.", footer_icon=interaction.guild.icon.url if interaction.guild.icon else None),
            view=None
        )
        self.stop()

class RatingView(discord.ui.View):
    def __init__(self, bot, ticket_data, ticket_type):
        super().__init__(timeout=None)
        self.bot = bot
        self.ticket_data = ticket_data
        self.ticket_type = ticket_type
        self.service_rating = None
        self.product_rating = None
    
    @discord.ui.select(
        placeholder="⭐ Avalie o atendimento (1-5 estrelas)",
        options=[
            discord.SelectOption(label="⭐ 1 - Péssimo", value="1"),
            discord.SelectOption(label="⭐⭐ 2 - Ruim", value="2"),
            discord.SelectOption(label="⭐⭐⭐ 3 - Regular", value="3"),
            discord.SelectOption(label="⭐⭐⭐⭐ 4 - Bom", value="4"),
            discord.SelectOption(label="⭐⭐⭐⭐⭐ 5 - Excelente", value="5"),
        ],
        custom_id="service_rating"
    )
    async def service_rating_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.service_rating = int(select.values[0])
        await interaction.response.send_message(f"✅ Avaliação do atendimento: {'⭐' * self.service_rating}", ephemeral=True)
    
    @discord.ui.select(
        placeholder="🛒 Avalie o produto (apenas compras)",
        options=[
            discord.SelectOption(label="⭐ 1 - Péssimo", value="1"),
            discord.SelectOption(label="⭐⭐ 2 - Ruim", value="2"),
            discord.SelectOption(label="⭐⭐⭐ 3 - Regular", value="3"),
            discord.SelectOption(label="⭐⭐⭐⭐ 4 - Bom", value="4"),
            discord.SelectOption(label="⭐⭐⭐⭐⭐ 5 - Excelente", value="5"),
        ],
        custom_id="product_rating"
    )
    async def product_rating_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if self.ticket_type != "compra":
            return await interaction.response.send_message("❌ Avaliação de produto apenas para compras!", ephemeral=True)
        
        self.product_rating = int(select.values[0])
        await interaction.response.send_message(f"✅ Avaliação do produto: {'⭐' * self.product_rating}", ephemeral=True)
    
    @discord.ui.button(label="Enviar Avaliação", style=discord.ButtonStyle.green, emoji="📤")
    async def submit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.service_rating:
            return await interaction.response.send_message("❌ Avalie o atendimento primeiro!", ephemeral=True)
        
        if self.ticket_type == "compra" and not self.product_rating:
            return await interaction.response.send_message("❌ Avalie o produto também!", ephemeral=True)
        
        # Salvar avaliação
        self.bot.db.rate_ticket(
            self.ticket_data['ticket_id'],
            self.service_rating,
            self.service_rating,
            self.product_rating,
            None
        )
        
        # Enviar para canal de avaliações
        rating_channel = self.bot.get_channel(Config.RATING_CHANNEL_ID)
        if rating_channel:
            user = await self.bot.fetch_user(int(self.ticket_data['user_id']))
            
            embed = EmbedBuilder.create_embed(
                "⭐ Nova Avaliação",
                f"**Usuário:** {user.mention}\n**Tipo:** {self.ticket_type.title()}",
                color=Config.COLORS['warning'],
                thumbnail=user.display_avatar.url,
                fields=[
                    {"name": "Atendimento", "value": "⭐" * self.service_rating, "inline": True},
                    {"name": "Produto", "value": "⭐" * self.product_rating if self.product_rating else "N/A", "inline": True}
                ]
            )
            
            await rating_channel.send(embed=embed)
        
        await interaction.response.edit_message(
            embed=EmbedBuilder.success("Avaliação Enviada", "Obrigado pelo seu feedback! 💚"),
            view=None
        )
        self.stop()

class AddUserModal(discord.ui.Modal, title="Adicionar Usuário ao Ticket"):
    user_id = discord.ui.TextInput(label="ID do Usuário", placeholder="123456789", style=discord.TextStyle.short)
    
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user = await self.bot.fetch_user(int(self.user_id.value))
            await interaction.channel.set_permissions(user, read_messages=True, send_messages=True)
            
            embed = EmbedBuilder.success(
                "Usuário Adicionado",
                f"{user.mention} foi adicionado ao ticket!",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.response.send_message(embed=embed)
        except:
            await interaction.response.send_message("❌ Usuário não encontrado!", ephemeral=True)

class RemoveUserModal(discord.ui.Modal, title="Remover Usuário do Ticket"):
    user_id = discord.ui.TextInput(label="ID do Usuário", placeholder="123456789", style=discord.TextStyle.short)
    
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user = await self.bot.fetch_user(int(self.user_id.value))
            await interaction.channel.set_permissions(user, overwrite=None)
            
            embed = EmbedBuilder.success(
                "Usuário Removido",
                f"{user.mention} foi removido do ticket!",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.response.send_message(embed=embed)
        except:
            await interaction.response.send_message("❌ Erro ao remover usuário!", ephemeral=True)

class RenameTicketModal(discord.ui.Modal, title="Renomear Ticket"):
    new_name = discord.ui.TextInput(label="Novo Nome", placeholder="novo-nome", style=discord.TextStyle.short)
    
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.channel.edit(name=self.new_name.value)
            
            embed = EmbedBuilder.success(
                "Canal Renomeado",
                f"Canal renomeado para: **{self.new_name.value}**",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.response.send_message(embed=embed)
        except:
            await interaction.response.send_message("❌ Erro ao renomear canal!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Tickets(bot))