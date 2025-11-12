import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils import EmbedBuilder, Config, Permissions

logger = logging.getLogger('PandaBot.Polls')

class Polls(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="enquete", description="Criar uma enquete")
    @app_commands.describe(
        pergunta="Pergunta da enquete",
        opcao1="Primeira opção",
        opcao2="Segunda opção",
        opcao3="Terceira opção (opcional)",
        opcao4="Quarta opção (opcional)",
        opcao5="Quinta opção (opcional)",
        canal="Canal onde enviar (opcional)"
    )
    @app_commands.check(lambda interaction: Permissions.is_staff(interaction.user))
    async def enquete_command(
        self,
        interaction: discord.Interaction,
        pergunta: str,
        opcao1: str,
        opcao2: str,
        opcao3: str = None,
        opcao4: str = None,
        opcao5: str = None,
        canal: discord.TextChannel = None
    ):
        """Criar enquete com até 5 opções"""
        
        # Canal de destino
        target_channel = canal or interaction.channel
        
        # Preparar opções
        opcoes = [opcao1, opcao2]
        if opcao3:
            opcoes.append(opcao3)
        if opcao4:
            opcoes.append(opcao4)
        if opcao5:
            opcoes.append(opcao5)
        
        # Emojis de números
        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        
        # Criar descrição
        description = ""
        for i, opcao in enumerate(opcoes):
            description += f"\n{number_emojis[i]} **{opcao}**"
        
        embed = EmbedBuilder.create_embed(
            "📊 Enquete",
            f"**{pergunta}**{description}\n\n*Reaja para votar!*",
            color=Config.COLORS['info'],
            thumbnail=interaction.guild.icon.url if interaction.guild.icon else None,
            fields=[
                {
                    "name": "Criado por",
                    "value": interaction.user.mention,
                    "inline": True
                }
            ],
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        try:
            # Enviar enquete
            msg = await target_channel.send(embed=embed)
            
            # Adicionar reações
            for i in range(len(opcoes)):
                await msg.add_reaction(number_emojis[i])
            
            # Resposta
            success_embed = EmbedBuilder.success(
                "Enquete Criada",
                f"Enquete criada em {target_channel.mention}!",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.response.send_message(embed=success_embed, ephemeral=True)
            
            # Log
            log_channel = self.bot.get_channel(Config.LOG_CHANNEL_ID)
            if log_channel:
                log_embed = EmbedBuilder.info(
                    "📊 Enquete Criada",
                    f"**Canal:** {target_channel.mention}\n**Pergunta:** {pergunta}\n**Criado por:** {interaction.user.mention}",
                    footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
                )
                await log_channel.send(embed=log_embed)
            
        except Exception as e:
            logger.error(f"Erro ao criar enquete: {e}")
            error_embed = EmbedBuilder.error(
                "Erro",
                f"Não foi possível criar a enquete: {str(e)}",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
    
    @app_commands.command(name="enquete-simples", description="Criar enquete sim/não")
    @app_commands.describe(
        pergunta="Pergunta da enquete",
        canal="Canal onde enviar (opcional)"
    )
    @app_commands.check(lambda interaction: Permissions.is_staff(interaction.user))
    async def enquete_simples_command(
        self,
        interaction: discord.Interaction,
        pergunta: str,
        canal: discord.TextChannel = None
    ):
        """Criar enquete simples sim/não"""
        
        target_channel = canal or interaction.channel
        
        embed = EmbedBuilder.create_embed(
            "📊 Enquete Sim/Não",
            f"**{pergunta}**\n\n✅ **Sim**\n❌ **Não**\n\n*Reaja para votar!*",
            color=Config.COLORS['info'],
            thumbnail=interaction.guild.icon.url if interaction.guild.icon else None,
            fields=[
                {
                    "name": "Criado por",
                    "value": interaction.user.mention,
                    "inline": True
                }
            ],
            footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        try:
            msg = await target_channel.send(embed=embed)
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")
            
            success_embed = EmbedBuilder.success(
                "Enquete Criada",
                f"Enquete criada em {target_channel.mention}!",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.response.send_message(embed=success_embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Erro ao criar enquete: {e}")
            error_embed = EmbedBuilder.error(
                "Erro",
                f"Não foi possível criar a enquete: {str(e)}",
                footer_icon=interaction.guild.icon.url if interaction.guild.icon else None
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Polls(bot))