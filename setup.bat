@echo off
chcp 65001 >nul
color 0B
title Panda Store Bot - Setup Automático

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║        Panda Store Bot - Gerador de Estrutura          ║
echo ║            Bot Discord Python Completo                  ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

echo [1/4] Criando estrutura de pastas...
mkdir data 2>nul
mkdir backups 2>nul
mkdir logs 2>nul
mkdir cogs 2>nul
mkdir web 2>nul
mkdir web\templates 2>nul
mkdir web\static 2>nul
echo ✓ Pastas criadas!

echo.
echo [2/4] Criando arquivos de configuração...

REM ==================== .ENV ====================
(
echo # Bot Configuration
echo BOT_TOKEN=seu_bot_token_aqui
echo CLIENT_ID=seu_client_id_aqui
echo CLIENT_SECRET=seu_client_secret_aqui
echo REDIRECT_URI=https://seu-dominio.railway.app/oauth/callback
echo.
echo # Server Configuration
echo GUILD_ID=seu_guild_id_aqui
echo OWNER_ID=seu_owner_id_aqui
echo.
echo # Web Server
echo PORT=3000
echo WEB_PASSWORD=admin123
echo.
echo # OAuth2
echo OAUTH_SCOPES=identify guilds.join
echo.
echo # Bot Settings
echo PREFIX=!
echo DEBUG=False
) > .env

REM ==================== .GITIGNORE ====================
(
echo __pycache__/
echo *.py[cod]
echo *$py.class
echo .env
echo .env.local
echo data/*.db
echo data/*.db-journal
echo *.log
echo logs/
echo backups/*.db
echo backups/*.json
echo .DS_Store
echo venv/
echo .vscode/
) > .gitignore

REM ==================== REQUIREMENTS.TXT ====================
(
echo discord.py==2.3.2
echo aiohttp==3.9.1
echo python-dotenv==1.0.0
echo aiofiles==23.2.1
echo Pillow==10.1.0
echo quart==0.19.4
echo asyncio==3.4.3
) > requirements.txt

REM ==================== RAILWAY.JSON ====================
(
echo {
echo   "build": {
echo     "builder": "NIXPACKS"
echo   },
echo   "deploy": {
echo     "startCommand": "python main.py",
echo     "restartPolicyType": "ON_FAILURE",
echo     "healthcheckPath": "/health"
echo   }
echo }
) > railway.json

REM ==================== NIXPACKS.TOML ====================
(
echo [phases.setup]
echo nixPkgs = ["python310", "gcc"]
echo.
echo [phases.install]
echo cmds = ["pip install -r requirements.txt"]
echo.
echo [start]
echo cmd = "python main.py"
) > nixpacks.toml

echo ✓ Arquivos de configuração criados!

echo.
echo [3/4] Criando arquivos Python base...

REM ==================== UTILS.PY ====================
(
echo # COLE AQUI O CÓDIGO DO utils.py
echo import logging
echo import discord
echo from datetime import datetime
echo import os
) > utils.py

REM ==================== MAIN.PY ====================
echo # COLE AQUI O CÓDIGO DO main.py > main.py

REM ==================== DATABASE.PY ====================
echo # COLE AQUI O CÓDIGO DO database.py > database.py

REM ==================== WEB_SERVER.PY ====================
echo # COLE AQUI O CÓDIGO DO web_server.py > web_server.py

REM ==================== COGS ====================
echo # COLE AQUI O CÓDIGO DO oauth.py > cogs\oauth.py
echo # COLE AQUI O CÓDIGO DO tickets.py > cogs\tickets.py
echo # COLE AQUI O CÓDIGO DO moderation.py > cogs\moderation.py
echo # COLE AQUI O CÓDIGO DO utility.py > cogs\utility.py
echo # COLE AQUI O CÓDIGO DO config.py > cogs\config.py
echo # COLE AQUI O CÓDIGO DO verification.py > cogs\verification.py
echo # COLE AQUI O CÓDIGO DO announcements.py > cogs\announcements.py
echo # COLE AQUI O CÓDIGO DO polls.py > cogs\polls.py
echo # COLE AQUI O CÓDIGO DO events.py > cogs\events.py

echo ✓ Arquivos Python criados!

echo.
echo [4/4] Criando arquivo de instruções...

(
echo ╔══════════════════════════════════════════════════════════╗
echo ║           ARQUIVOS QUE PRECISAM SER PREENCHIDOS         ║
echo ╚══════════════════════════════════════════════════════════╝
echo.
echo IMPORTANTE: Cole o código dos artifacts nos arquivos abaixo:
echo.
echo 📁 RAIZ
echo    1. main.py - Bot principal
echo    2. database.py - Sistema de banco de dados
echo    3. utils.py - Utilitários e configurações
echo    4. web_server.py - Servidor web e OAuth2
echo.
echo 📁 COGS (Comandos e Eventos^)
echo    5. cogs\oauth.py - Sistema OAuth2
echo    6. cogs\tickets.py - Sistema de tickets
echo    7. cogs\moderation.py - Comandos de moderação
echo    8. cogs\utility.py - Comandos utilitários
echo    9. cogs\config.py - Configurações do bot
echo    10. cogs\verification.py - Sistema de verificação
echo    11. cogs\announcements.py - Sistema de avisos
echo    12. cogs\polls.py - Sistema de enquetes
echo    13. cogs\events.py - Eventos (boas-vindas, saídas, etc^)
echo.
echo ════════════════════════════════════════════════════════════
echo.
echo 🔧 PRÓXIMOS PASSOS:
echo.
echo 1. Edite o arquivo .env com suas credenciais do Discord
echo 2. Cole o código fornecido nos 13 arquivos listados acima
echo 3. Instale as dependências: pip install -r requirements.txt
echo 4. Execute o bot: python main.py
echo.
echo 📝 ESTRUTURA DO PROJETO:
echo.
echo panda-bot/
echo ├── main.py              # Bot principal
echo ├── database.py          # Banco de dados SQLite
echo ├── utils.py             # Utilitários
echo ├── web_server.py        # Servidor web + OAuth2
echo ├── requirements.txt     # Dependências
echo ├── .env                 # Configurações (EDITE ESTE^)
echo ├── railway.json         # Config Railway
echo ├── nixpacks.toml        # Config Nixpacks
echo ├── data/                # Banco de dados
echo ├── backups/             # Backups automáticos
echo ├── logs/                # Logs do bot
echo ├── cogs/                # Comandos e eventos
echo │   ├── oauth.py
echo │   ├── tickets.py
echo │   ├── moderation.py
echo │   ├── utility.py
echo │   ├── config.py
echo │   ├── verification.py
echo │   ├── announcements.py
echo │   ├── polls.py
echo │   └── events.py
echo └── web/                 # Arquivos web
echo     ├── templates/
echo     └── static/
echo.
echo ════════════════════════════════════════════════════════════
echo.
echo 🌟 FUNCIONALIDADES:
echo.
echo ✅ Sistema OAuth2 completo com painel web
echo ✅ Tickets e carrinhos de compra
echo ✅ Sistema de avaliações (1-5 estrelas^)
echo ✅ Transcrições enviadas por DM
echo ✅ Verificação com OAuth2
echo ✅ Boas-vindas e despedidas com embeds
echo ✅ Comandos de moderação (kick, ban, mute, etc^)
echo ✅ Sistema de enquetes
echo ✅ Avisos e regras customizáveis
echo ✅ Logs completos
echo ✅ Backup automático
echo ✅ Painel web administrativo
echo.
echo ════════════════════════════════════════════════════════════
echo.
echo ⚙️ COMANDOS PRINCIPAIS:
echo.
echo /config - Configurar o bot (botões interativos^)
echo /oauth - Sistema OAuth2
echo /ticket - Abrir ticket
echo /compra - Abrir carrinho de compra
echo /avisos - Enviar avisos
echo /regras - Enviar regras
echo /enquete - Criar enquete
echo /ping - Ver latência
echo /serverinfo - Informações do servidor
echo /userinfo - Informações de usuário
echo /kick, /ban, /mute - Moderação
echo.
echo ════════════════════════════════════════════════════════════
) > INSTRUCOES.txt

type INSTRUCOES.txt

echo.
echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║              ✓ SETUP CONCLUÍDO COM SUCESSO!             ║
echo ╚══════════════════════════════════════════════════════════╝
echo.
echo ✓ Estrutura de pastas criada
echo ✓ Arquivos de configuração gerados
echo ✓ 13 arquivos Python criados (vazios^)
echo.
echo 📋 Próximo passo: Leia INSTRUCOES.txt
echo.
echo 🎯 Para começar:
echo    1. Edite .env com suas credenciais
echo    2. Cole o código nos arquivos Python
echo    3. pip install -r requirements.txt
echo    4. python main.py
echo.
pause