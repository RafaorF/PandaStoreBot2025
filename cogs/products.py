import discord
from discord.ext import commands
from discord import app_commands
import logging
import os
import stripe
from datetime import datetime
from utils import EmbedBuilder, Config, Permissions

logger = logging.getLogger('PandaBot.Products')

# Configurar Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

class Products(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cart_category_id = 1160644873272172627
        self._create_products_table()
    
    def _create_products_table(self):
        """Criar tabela de produtos no banco de dados"""
        try:
            self.bot.db.cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    eur_cents INTEGER NOT NULL,
                    brl_cents INTEGER NOT NULL,
                    description TEXT NOT NULL,
                    image_url TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    created_by TEXT NOT NULL,
                    updated_at INTEGER DEFAULT NULL
                )
            """)
            self.bot.db.conn.commit()
            logger.info("✅ Tabela de produtos verificada/criada")
        except Exception as e:
            logger.error(f"Erro ao criar tabela de produtos: {e}")
    
    @app_commands.command(name="criarproduto", description="Criar produto para venda")
    @app_commands.describe(
        nome="Nome do produto",
        valor_eur="Valor em EUR (exemplo: 10.50)",
        valor_real="Valor em BRL (exemplo: 55.00)",
        descricao="Descrição do produto",
        imagem_url="URL da imagem para a embed",
        canal="Canal onde enviar o produto"
    )
    @app_commands.check(lambda interaction: Permissions.is_staff(interaction.user))
    async def criarproduto_command(
        self,
        interaction: discord.Interaction,
        nome: str,
        valor_eur: str,
        valor_real: str,
        descricao: str,
        imagem_url: str,
        canal: discord.TextChannel
    ):
        """Criar produto com embed e botão de compra"""
        
        try:
            # Validar valores
            try:
                eur_float = float(valor_eur)
                brl_float = float(valor_real)
                
                if eur_float <= 0 or brl_float <= 0:
                    raise ValueError("Valores devem ser maiores que zero")
                
                # Converter para centavos
                eur_cents = int(eur_float * 100)
                brl_cents = int(brl_float * 100)
                
            except ValueError as e:
                embed = EmbedBuilder.error(
                    "Valor Inválido",
                    f"Os valores devem ser números válidos. Exemplo: 10.50\nErro: {str(e)}",
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Validar URL da imagem
            if not imagem_url.startswith(('http://', 'https://')):
                embed = EmbedBuilder.error(
                    "URL Inválida",
                    "A URL da imagem deve começar com http:// ou https://",
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Verificar se produto já existe
            existing = self._get_product_by_name(nome)
            if existing:
                embed = EmbedBuilder.error(
                    "Produto Já Existe",
                    f"Já existe um produto com o nome **{nome}**.\nUse `/produtoeditar` para editá-lo ou escolha outro nome.",
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            
            await interaction.response.defer()
            
            # Criar embed do produto
            embed = EmbedBuilder.create_embed(
                f"🛍️ {nome}",
                descricao,
                color=Config.COLORS['panda'],
                image=imagem_url,
                thumbnail=interaction.guild.icon.url if interaction.guild.icon else None,
                fields=[
                    {
                        "name": "💶 Preço (EUR)",
                        "value": f"**€{eur_float:.2f}**",
                        "inline": True
                    },
                    {
                        "name": "💵 Preço (BRL)",
                        "value": f"**R$ {brl_float:.2f}**",
                        "inline": True
                    },
                    {
                        "name": "📦 Status",
                        "value": "✅ **Disponível**",
                        "inline": True
                    },
                    {
                        "name": "ℹ️ Como Comprar",
                        "value": "Clique no botão **🛒 Comprar** abaixo para iniciar sua compra!",
                        "inline": False
                    }
                ],
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            
            # Criar view com botão de compra
            view = ProductView(
                self.bot,
                nome,
                eur_cents,
                brl_cents,
                descricao,
                imagem_url,
                self.cart_category_id
            )
            
            # Enviar produto no canal
            await canal.send(embed=embed, view=view)
            
            # Salvar produto no banco de dados
            self._save_product(
                nome,
                eur_cents,
                brl_cents,
                descricao,
                imagem_url,
                str(interaction.user.id)
            )
            
            # Confirmar criação
            success_embed = EmbedBuilder.success(
                "Produto Criado",
                f"✅ Produto **{nome}** criado com sucesso em {canal.mention}!",
                fields=[
                    {
                        "name": "💶 EUR",
                        "value": f"€{eur_float:.2f}",
                        "inline": True
                    },
                    {
                        "name": "💵 BRL",
                        "value": f"R$ {brl_float:.2f}",
                        "inline": True
                    }
                ],
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.followup.send(embed=success_embed, ephemeral=True)
            
            # Log
            log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
            if log_channel:
                log_embed = EmbedBuilder.info(
                    "🛍️ Produto Criado",
                    f"**Produto:** {nome}\n**Canal:** {canal.mention}\n**Criado por:** {interaction.user.mention}",
                    fields=[
                        {"name": "EUR", "value": f"€{eur_float:.2f}", "inline": True},
                        {"name": "BRL", "value": f"R$ {brl_float:.2f}", "inline": True}
                    ],
                    thumbnail=imagem_url,
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                await log_channel.send(embed=log_embed)
            
        except Exception as e:
            logger.error(f"Erro ao criar produto: {e}")
            embed = EmbedBuilder.error(
                "Erro",
                f"Não foi possível criar o produto:\n```{str(e)}```",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


    @app_commands.command(name="enviarproduto", description="Enviar produto já criado")
    @app_commands.describe(
        nome="Nome do produto",
        canal="Canal onde enviar"
    )
    @app_commands.check(lambda interaction: Permissions.is_staff(interaction.user))
    async def enviarproduto_command(
        self,
        interaction: discord.Interaction,
        nome: str,
        canal: discord.TextChannel
    ):
        """Enviar produto existente"""
        
        # Buscar produto
        product = self._get_product_by_name(nome)
        
        if not product:
            # Listar produtos disponíveis
            all_products = self._get_all_products()
            
            if not all_products:
                embed = EmbedBuilder.error(
                    "Nenhum Produto",
                    "Não há produtos cadastrados.\nUse `/criarproduto` para criar um.",
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
            else:
                products_list = "\n".join([f"• **{p['name']}**" for p in all_products])
                embed = EmbedBuilder.error(
                    "Produto Não Encontrado",
                    f"Produto **{nome}** não existe.\n\n**Produtos disponíveis:**\n{products_list}",
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
            
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        try:
            await interaction.response.defer()
            
            # Converter centavos para float
            eur_float = product['eur_cents'] / 100
            brl_float = product['brl_cents'] / 100
            
            # Criar embed do produto
            embed = EmbedBuilder.create_embed(
                f"🛍️ {product['name']}",
                product['description'],
                color=Config.COLORS['panda'],
                image=product['image_url'],
                thumbnail=interaction.guild.icon.url if interaction.guild.icon else None,
                fields=[
                    {
                        "name": "💶 Preço (EUR)",
                        "value": f"**€{eur_float:.2f}**",
                        "inline": True
                    },
                    {
                        "name": "💵 Preço (BRL)",
                        "value": f"**R$ {brl_float:.2f}**",
                        "inline": True
                    },
                    {
                        "name": "📦 Status",
                        "value": "✅ **Disponível**",
                        "inline": True
                    },
                    {
                        "name": "ℹ️ Como Comprar",
                        "value": "Clique no botão **🛒 Comprar** abaixo para iniciar sua compra!",
                        "inline": False
                    }
                ],
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            
            # Criar view com botão de compra
            view = ProductView(
                self.bot,
                product['name'],
                product['eur_cents'],
                product['brl_cents'],
                product['description'],
                product['image_url'],
                self.cart_category_id
            )
            
            # Enviar
            await canal.send(embed=embed, view=view)
            
            # Confirmar
            success_embed = EmbedBuilder.success(
                "Produto Enviado",
                f"✅ Produto **{product['name']}** enviado em {canal.mention}!",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.followup.send(embed=success_embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Erro ao enviar produto: {e}")
            embed = EmbedBuilder.error(
                "Erro",
                f"Não foi possível enviar o produto:\n```{str(e)}```",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


    @app_commands.command(name="produtoeditar", description="Editar ou apagar produto")
    @app_commands.describe(nome="Nome do produto")
    @app_commands.check(lambda interaction: Permissions.is_staff(interaction.user))
    async def produtoeditar_command(self, interaction: discord.Interaction, nome: str):
        """Painel de edição de produto"""
        
        # Buscar produto
        product = self._get_product_by_name(nome)
        
        if not product:
            all_products = self._get_all_products()
            
            if not all_products:
                embed = EmbedBuilder.error(
                    "Nenhum Produto",
                    "Não há produtos cadastrados.",
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
            else:
                products_list = "\n".join([f"• **{p['name']}**" for p in all_products])
                embed = EmbedBuilder.error(
                    "Produto Não Encontrado",
                    f"Produto **{nome}** não existe.\n\n**Produtos disponíveis:**\n{products_list}",
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
            
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Criar embed com info do produto
        eur_float = product['eur_cents'] / 100
        brl_float = product['brl_cents'] / 100
        
        embed = EmbedBuilder.create_embed(
            f"✏️ Editar Produto: {product['name']}",
            "Use os botões abaixo para editar ou apagar este produto.",
            color=Config.COLORS['info'],
            thumbnail=product['image_url'],
            fields=[
                {
                    "name": "💶 Preço EUR",
                    "value": f"€{eur_float:.2f}",
                    "inline": True
                },
                {
                    "name": "💵 Preço BRL",
                    "value": f"R$ {brl_float:.2f}",
                    "inline": True
                },
                {
                    "name": "📝 Descrição",
                    "value": product['description'][:100] + "..." if len(product['description']) > 100 else product['description'],
                    "inline": False
                },
                {
                    "name": "🖼️ URL da Imagem",
                    "value": f"[Clique aqui]({product['image_url']})",
                    "inline": False
                }
            ],
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        view = ProductEditView(self.bot, product)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


    def _save_product(self, name, eur_cents, brl_cents, description, image_url, created_by):
        """Salvar produto no banco"""
        try:
            self.bot.db.cursor.execute("""
                INSERT INTO products (name, eur_cents, brl_cents, description, image_url, created_at, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (name, eur_cents, brl_cents, description, image_url, int(datetime.utcnow().timestamp()), created_by))
            self.bot.db.conn.commit()
            logger.info(f"✅ Produto '{name}' salvo no banco")
        except Exception as e:
            logger.error(f"Erro ao salvar produto: {e}")
            self.bot.db.conn.rollback()
    
    def _get_product_by_name(self, name):
        """Buscar produto por nome"""
        try:
            self.bot.db.cursor.execute("SELECT * FROM products WHERE name = ?", (name,))
            row = self.bot.db.cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Erro ao buscar produto: {e}")
            return None
    
    def _get_all_products(self):
        """Buscar todos os produtos"""
        try:
            self.bot.db.cursor.execute("SELECT * FROM products ORDER BY name")
            return [dict(row) for row in self.bot.db.cursor.fetchall()]
        except Exception as e:
            logger.error(f"Erro ao buscar produtos: {e}")
            return []
    
    def _update_product(self, product_id, **kwargs):
        """Atualizar produto"""
        try:
            fields = []
            values = []
            
            for key, value in kwargs.items():
                fields.append(f"{key} = ?")
                values.append(value)
            
            fields.append("updated_at = ?")
            values.append(int(datetime.utcnow().timestamp()))
            
            values.append(product_id)
            
            query = f"UPDATE products SET {', '.join(fields)} WHERE product_id = ?"
            self.bot.db.cursor.execute(query, values)
            self.bot.db.conn.commit()
            logger.info(f"✅ Produto ID {product_id} atualizado")
            return True
        except Exception as e:
            logger.error(f"Erro ao atualizar produto: {e}")
            self.bot.db.conn.rollback()
            return False
    
    def _delete_product(self, product_id):
        """Deletar produto"""
        try:
            self.bot.db.cursor.execute("DELETE FROM products WHERE product_id = ?", (product_id,))
            self.bot.db.conn.commit()
            logger.info(f"✅ Produto ID {product_id} deletado")
            return True
        except Exception as e:
            logger.error(f"Erro ao deletar produto: {e}")
            self.bot.db.conn.rollback()
            return False


class ProductEditView(discord.ui.View):
    """View para editar ou apagar produto"""
    
    def __init__(self, bot, product):
        super().__init__(timeout=300)
        self.bot = bot
        self.product = product
    
    @discord.ui.button(label="Editar Preço EUR", style=discord.ButtonStyle.primary, emoji="💶", row=0)
    async def edit_eur(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EditPriceModal(self.bot, self.product, 'eur')
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Editar Preço BRL", style=discord.ButtonStyle.primary, emoji="💵", row=0)
    async def edit_brl(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EditPriceModal(self.bot, self.product, 'brl')
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Editar Descrição", style=discord.ButtonStyle.primary, emoji="📝", row=1)
    async def edit_description(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EditDescriptionModal(self.bot, self.product)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Editar Imagem", style=discord.ButtonStyle.primary, emoji="🖼️", row=1)
    async def edit_image(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EditImageModal(self.bot, self.product)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Apagar Produto", style=discord.ButtonStyle.danger, emoji="🗑️", row=2)
    async def delete_product(self, interaction: discord.Interaction, button: discord.ui.Button):
        confirm_view = ConfirmDeleteView(self.bot, self.product)
        
        embed = EmbedBuilder.warning(
            "Confirmar Exclusão",
            f"Tem certeza que deseja **apagar** o produto **{self.product['name']}**?\n\n⚠️ Esta ação é **irreversível**!",
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)


class EditPriceModal(discord.ui.Modal):
    """Modal para editar preço"""
    
    def __init__(self, bot, product, currency):
        super().__init__(title=f"Editar Preço {currency.upper()}")
        self.bot = bot
        self.product = product
        self.currency = currency
        
        current_price = (product['eur_cents'] if currency == 'eur' else product['brl_cents']) / 100
        
        self.price = discord.ui.TextInput(
            label=f"Novo Preço em {currency.upper()}",
            placeholder=f"Ex: {current_price:.2f}",
            style=discord.TextStyle.short,
            required=True,
            max_length=10
        )
        self.add_item(self.price)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            price_float = float(self.price.value)
            
            if price_float <= 0:
                raise ValueError("Preço deve ser maior que zero")
            
            price_cents = int(price_float * 100)
            
            # Atualizar no banco
            products_cog = self.bot.get_cog('Products')
            key = 'eur_cents' if self.currency == 'eur' else 'brl_cents'
            
            success = products_cog._update_product(
                self.product['product_id'],
                **{key: price_cents}
            )
            
            if success:
                embed = EmbedBuilder.success(
                    "Preço Atualizado",
                    f"Preço em {self.currency.upper()} atualizado para: **{'€' if self.currency == 'eur' else 'R$'} {price_float:.2f}**",
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                
                # Log
                log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
                if log_channel:
                    log_embed = EmbedBuilder.info(
                        "💰 Produto Editado",
                        f"**Produto:** {self.product['name']}\n**Campo:** Preço {self.currency.upper()}\n**Novo Valor:** {'€' if self.currency == 'eur' else 'R$'} {price_float:.2f}\n**Editado por:** {interaction.user.mention}",
                        footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                    )
                    await log_channel.send(embed=log_embed)
            else:
                embed = EmbedBuilder.error(
                    "Erro",
                    "Não foi possível atualizar o preço.",
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError as e:
            embed = EmbedBuilder.error(
                "Valor Inválido",
                f"Digite um número válido. Erro: {str(e)}",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class EditDescriptionModal(discord.ui.Modal, title="Editar Descrição"):
    """Modal para editar descrição"""
    
    description = discord.ui.TextInput(
        label="Nova Descrição",
        placeholder="Digite a nova descrição do produto...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=2000
    )
    
    def __init__(self, bot, product):
        super().__init__()
        self.bot = bot
        self.product = product
        self.description.default = product['description']
    
    async def on_submit(self, interaction: discord.Interaction):
        products_cog = self.bot.get_cog('Products')
        
        success = products_cog._update_product(
            self.product['product_id'],
            description=self.description.value
        )
        
        if success:
            embed = EmbedBuilder.success(
                "Descrição Atualizada",
                f"Descrição do produto **{self.product['name']}** foi atualizada!",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            
            # Log
            log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
            if log_channel:
                log_embed = EmbedBuilder.info(
                    "📝 Produto Editado",
                    f"**Produto:** {self.product['name']}\n**Campo:** Descrição\n**Editado por:** {interaction.user.mention}",
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                await log_channel.send(embed=log_embed)
        else:
            embed = EmbedBuilder.error(
                "Erro",
                "Não foi possível atualizar a descrição.",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class EditImageModal(discord.ui.Modal, title="Editar Imagem"):
    """Modal para editar URL da imagem"""
    
    image_url = discord.ui.TextInput(
        label="Nova URL da Imagem",
        placeholder="https://exemplo.com/imagem.png",
        style=discord.TextStyle.short,
        required=True,
        max_length=500
    )
    
    def __init__(self, bot, product):
        super().__init__()
        self.bot = bot
        self.product = product
        self.image_url.default = product['image_url']
    
    async def on_submit(self, interaction: discord.Interaction):
        # Validar URL
        if not self.image_url.value.startswith(('http://', 'https://')):
            embed = EmbedBuilder.error(
                "URL Inválida",
                "A URL da imagem deve começar com http:// ou https://",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        products_cog = self.bot.get_cog('Products')
        
        success = products_cog._update_product(
            self.product['product_id'],
            image_url=self.image_url.value
        )
        
        if success:
            embed = EmbedBuilder.success(
                "Imagem Atualizada",
                f"URL da imagem do produto **{self.product['name']}** foi atualizada!",
                image=self.image_url.value,
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            
            # Log
            log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
            if log_channel:
                log_embed = EmbedBuilder.info(
                    "🖼️ Produto Editado",
                    f"**Produto:** {self.product['name']}\n**Campo:** Imagem\n**Editado por:** {interaction.user.mention}",
                    thumbnail=self.image_url.value,
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                await log_channel.send(embed=log_embed)
        else:
            embed = EmbedBuilder.error(
                "Erro",
                "Não foi possível atualizar a imagem.",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ConfirmDeleteView(discord.ui.View):
    """View para confirmar exclusão de produto"""
    
    def __init__(self, bot, product):
        super().__init__(timeout=60)
        self.bot = bot
        self.product = product
    
    @discord.ui.button(label="Sim, Apagar", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        products_cog = self.bot.get_cog('Products')
        
        success = products_cog._delete_product(self.product['product_id'])
        
        if success:
            embed = EmbedBuilder.success(
                "Produto Apagado",
                f"O produto **{self.product['name']}** foi apagado com sucesso!",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            
            # Log
            log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
            if log_channel:
                log_embed = EmbedBuilder.warning(
                    "🗑️ Produto Apagado",
                    f"**Produto:** {self.product['name']}\n**Apagado por:** {interaction.user.mention}",
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                await log_channel.send(embed=log_embed)
        else:
            embed = EmbedBuilder.error(
                "Erro",
                "Não foi possível apagar o produto.",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
        
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()
    
    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = EmbedBuilder.info(
            "Cancelado",
            "A exclusão do produto foi cancelada.",
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()


class ProductView(discord.ui.View):
    """View persistente com botão de compra"""
    
    def __init__(self, bot, product_name, eur_cents, brl_cents, description, image_url, cart_category_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.product_name = product_name
        self.eur_cents = eur_cents
        self.brl_cents = brl_cents
        self.description = description
        self.image_url = image_url
        self.cart_category_id = cart_category_id

class QuantityModal(discord.ui.Modal, title="Finalizar Compra"):
    """Modal para escolher quantidade e moeda"""
    
    quantidade = discord.ui.TextInput(
        label="Quantidade",
        placeholder="Digite a quantidade desejada",
        style=discord.TextStyle.short,
        required=True,
        min_length=1,
        max_length=4
    )
    
    moeda = discord.ui.TextInput(
        label="Moeda (EUR ou BRL)",
        placeholder="Digite EUR ou BRL",
        style=discord.TextStyle.short,
        required=True,
        min_length=3,
        max_length=3
    )
    
    def __init__(self, bot, product_name, eur_cents, brl_cents, description, image_url, cart_category_id):
        super().__init__()
        self.bot = bot
        self.product_name = product_name
        self.eur_cents = eur_cents
        self.brl_cents = brl_cents
        self.description = description
        self.image_url = image_url
        self.cart_category_id = cart_category_id
    
    async def on_submit(self, interaction: discord.Interaction):
        """Processar compra"""
        
        try:
            # Validar quantidade
            try:
                qty = int(self.quantidade.value)
                if qty <= 0:
                    raise ValueError("Quantidade deve ser maior que zero")
                if qty > 1000:
                    raise ValueError("Quantidade máxima: 1000")
            except ValueError:
                embed = EmbedBuilder.error(
                    "Quantidade Inválida",
                    "Digite um número válido entre 1 e 1000",
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Validar moeda
            currency = self.moeda.value.upper().strip()
            if currency not in ['EUR', 'BRL']:
                embed = EmbedBuilder.error(
                    "Moeda Inválida",
                    "Digite **EUR** ou **BRL**",
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Calcular valor total
            if currency == 'EUR':
                unit_price = self.eur_cents
                total_cents = unit_price * qty
                currency_lower = 'eur'
                currency_symbol = '€'
            else:  # BRL
                unit_price = self.brl_cents
                total_cents = unit_price * qty
                currency_lower = 'brl'
                currency_symbol = 'R$'
            
            await interaction.response.defer()
            
            # Criar canal de carrinho
            category = interaction.guild.get_channel(self.cart_category_id)
            
            if not category:
                embed = EmbedBuilder.error(
                    "Erro",
                    "Categoria de carrinho não encontrada. Contate um administrador.",
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Criar canal
            channel_name = f"🛒-compra-{interaction.user.name}"
            
            config = self.bot.db.get_config(str(interaction.guild.id))
            staff_role_id = int(config.get('staff_role', Config.STAFF_ROLE_ID)) if config else Config.STAFF_ROLE_ID
            
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            
            staff_role = interaction.guild.get_role(staff_role_id)
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
            cart_channel = await category.create_text_channel(
                name=channel_name,
                overwrites=overwrites
            )
            
            # Criar ticket no banco
            self.bot.db.create_ticket(str(cart_channel.id), str(interaction.user.id), "compra")
            
            # Criar sessão de pagamento Stripe
            base_url = os.getenv('REDIRECT_URI', 'https://seu-dominio.railway.app').split('/oauth')[0]
            success_url = f"{base_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
            cancel_url = f"{base_url}/payment/cancel"
            
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': currency_lower,
                        'unit_amount': unit_price,
                        'product_data': {
                            'name': self.product_name,
                            'description': self.description,
                            'images': [self.image_url] if self.image_url else []
                        },
                    },
                    'quantity': qty,
                }],
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'guild_id': str(interaction.guild.id),
                    'channel_id': str(cart_channel.id),
                    'user_id': str(interaction.user.id),
                    'username': interaction.user.name,
                    'product': self.product_name,
                    'quantity': str(qty),
                    'staff_id': str(interaction.user.id),
                    'timestamp': str(int(datetime.utcnow().timestamp()))
                }
            )
            
            # Formatar valores
            unit_value = unit_price / 100
            total_value = total_cents / 100
            
            # Embed no carrinho
            cart_embed = EmbedBuilder.create_embed(
                "🛒 Carrinho de Compra",
                f"Olá {interaction.user.mention}!\n\nAqui está o resumo da sua compra:",
                color=Config.COLORS['success'],
                thumbnail=self.image_url,
                fields=[
                    {
                        "name": "🛍️ Produto",
                        "value": f"**{self.product_name}**",
                        "inline": False
                    },
                    {
                        "name": "📊 Quantidade",
                        "value": f"**{qty}x**",
                        "inline": True
                    },
                    {
                        "name": "💰 Preço Unitário",
                        "value": f"**{currency_symbol} {unit_value:.2f}**",
                        "inline": True
                    },
                    {
                        "name": "💳 Total",
                        "value": f"**{currency_symbol} {total_value:.2f}**",
                        "inline": True
                    },
                    {
                        "name": "💵 Moeda",
                        "value": f"**{currency}**",
                        "inline": True
                    },
                    {
                        "name": "📝 Descrição",
                        "value": self.description,
                        "inline": False
                    },
                    {
                        "name": "💳 Pagamento",
                        "value": "Clique no botão abaixo para pagar via Stripe",
                        "inline": False
                    }
                ],
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            
            # View com botão de pagamento
            payment_view = discord.ui.View(timeout=None)
            payment_view.add_item(discord.ui.Button(
                label="Pagar com Stripe",
                emoji="💳",
                style=discord.ButtonStyle.link,
                url=checkout_session.url
            ))
            
            await cart_channel.send(
                f"{interaction.user.mention} | {staff_role.mention if staff_role else ''}",
                embed=cart_embed,
                view=payment_view
            )
            
            # Adicionar botões de controle do carrinho
            from cogs.tickets import TicketControlView
            control_view = TicketControlView(self.bot, "compra")
            
            control_embed = EmbedBuilder.info(
                "🔧 Controles do Carrinho",
                "Use os botões abaixo para gerenciar este carrinho",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            
            await cart_channel.send(embed=control_embed, view=control_view)
            
            # Responder ao usuário
            success_embed = EmbedBuilder.success(
                "Carrinho Criado",
                f"✅ Seu carrinho foi criado: {cart_channel.mention}\n\n"
                f"**Produto:** {self.product_name}\n"
                f"**Quantidade:** {qty}x\n"
                f"**Total:** {currency_symbol} {total_value:.2f}",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.followup.send(embed=success_embed, ephemeral=True)
            
            # Log
            log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
            if log_channel:
                log_embed = EmbedBuilder.success(
                    "🛒 Compra Iniciada",
                    f"**Produto:** {self.product_name}\n"
                    f"**Cliente:** {interaction.user.mention}\n"
                    f"**Quantidade:** {qty}x\n"
                    f"**Total:** {currency_symbol} {total_value:.2f}\n"
                    f"**Canal:** {cart_channel.mention}",
                    thumbnail=interaction.user.display_avatar.url,
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                await log_channel.send(embed=log_embed)
            
            # Salvar no banco
            self.bot.db.add_log(
                'payment',
                str(interaction.user.id),
                str(interaction.guild.id),
                'purchase_initiated',
                f"Produto: {self.product_name}, Qtd: {qty}, Total: {currency_symbol} {total_value:.2f}, Session: {checkout_session.id}"
            )
            
        except stripe.error.StripeError as e:
            logger.error(f"Erro do Stripe: {e}")
            embed = EmbedBuilder.error(
                "Erro no Pagamento",
                f"Ocorreu um erro ao criar o pagamento:\n```{str(e)}```",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        except Exception as e:
            logger.error(f"Erro ao processar compra: {e}")
            embed = EmbedBuilder.error(
                "Erro",
                f"Ocorreu um erro ao processar sua compra:\n```{str(e)}```",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Products(bot))
