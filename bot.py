import os
import json
import gspread
import logging
import sys
from datetime import datetime, timedelta, timezone
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# Habilitar logging básico
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ESTADOS DA CONVERSA
NOME, WHATSAPP, MENSAGEM = range(3)

# CONFIGURAÇÕES
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
SPREADSHEET_NAME = "Leads Bot"
JSON_FILE_PATH = os.path.join(os.path.dirname(__file__), "credenciais.json")


def connect_sheets(tab_name="Leads Bot"):
    """Conecta ao Google Sheets e retorna a aba específica, criando-a se necessário."""
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            'https://www.googleapis.com/auth/spreadsheets',
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive"
        ]

        # Modo 1: JSON completo na variável de ambiente (Recomendado para Railway)
        google_json = os.environ.get('GOOGLE_SHEETS_JSON')
        # Modo 2: Chave + Email separados (Fallback)
        private_key = os.environ.get('GOOGLE_PRIVATE_KEY')
        email = os.environ.get('GOOGLE_SERVICE_ACCOUNT_EMAIL')

        creds = None
        if google_json:
            try:
                creds_dict = json.loads(google_json)
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                print(f"✅ Conectado via GOOGLE_SHEETS_JSON (Aba: {tab_name})")
            except Exception as j_err:
                raise Exception(f"Erro ao parsear GOOGLE_SHEETS_JSON: {j_err}")

        elif private_key and email:
            cleaned_key = private_key.strip('"').strip("'")
            cleaned_key = cleaned_key.replace('\\n', '\n').replace('\\\\n', '\n')
            creds_dict = {
                "type": "service_account",
                "private_key": cleaned_key,
                "client_email": email.strip('"').strip("'"),
                "token_uri": "https://oauth2.googleapis.com/token",
            }
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            print(f"✅ Conectado via Variáveis Separadas (Aba: {tab_name})")

        elif os.path.exists(JSON_FILE_PATH):
            creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_FILE_PATH, scope)
            print(f"✅ Conectado via Arquivo Local (Aba: {tab_name})")
        else:
            raise Exception("Nenhuma credencial do Google encontrada!")

        client = gspread.authorize(creds)
        spreadsheet = client.open(SPREADSHEET_NAME)
        
        try:
            return spreadsheet.worksheet(tab_name), None
        except gspread.exceptions.WorksheetNotFound:
            print(f" criando aba: {tab_name}")
            new_sheet = spreadsheet.add_worksheet(title=tab_name, rows=1000, cols=10)
            new_sheet.append_row(["Nome", "WhatsApp", "Mensagem/Interesse", "Origem", "Data/Hora"])
            return new_sheet, None

    except Exception as e:
        print(f"❌ ERRO GOOGLE SHEETS: {e}")
        return None, str(e)


# --- HANDLERS DA CONVERSA ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    source_arg = context.args[0] if context.args else "geral"
    context.user_data['origem'] = source_arg
    print(f"\n[SISTEMA] /start recebido. Origem: {source_arg}")

    greeting = (
        "Olá! Sou o assistente da Nexara Solar. 👋\nQual seu *Nome Completo*?"
        if source_arg == "solar"
        else "Olá! Sou o assistente da Mavinic Digital. 👋\nQual seu *Nome Completo*?"
    )
    await update.message.reply_text(greeting, parse_mode="Markdown")
    return NOME


async def collect_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    print(f"[SISTEMA] Nome recebido: {name}")
    context.user_data['nome'] = name
    await update.message.reply_text(f"Obrigado, {name}! Agora, qual o seu *WhatsApp* com DDD?", parse_mode="Markdown")
    return WHATSAPP


async def collect_whatsapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    whatsapp = update.message.text
    print(f"[SISTEMA] WhatsApp recebido: {whatsapp}")
    context.user_data['whatsapp'] = whatsapp
    origem = context.user_data.get('origem', 'geral')

    if origem == "solar":
        question = "Perfeito! Para agilizar seu diagnóstico, qual o valor médio da sua conta de luz?"
    elif origem == "portfolio":
        question = "Excelente! Me conte sobre o projeto digital que você tem em mente?"
    else:
        question = "Perfeito. Como posso te ajudar hoje?"

    await update.message.reply_text(question)
    return MENSAGEM


async def collect_message_and_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_text = update.message.text
    nome = context.user_data.get('nome')
    whatsapp = context.user_data.get('whatsapp')
    origem = context.user_data.get('origem', 'geral').upper()
    print(f"[SISTEMA] Finalizando lead: {nome}")

    try:
        # Ajusta para o horário de Brasília (UTC-3)
        fuso_horario = timezone(timedelta(hours=-3))
        data_hora = datetime.now(fuso_horario).strftime("%d/%m/%Y %H:%M:%S")
        sheet, sheet_error = connect_sheets("Leads Bot")

        if sheet:
            sheet.append_row([nome, whatsapp, msg_text, origem, data_hora])
            print(f"✅ REGISTRO SALVO NA PLANILHA: {data_hora}")
            await update.message.reply_text(
                f"✅ Recebido, {nome}!\n\nSalvei sua mensagem. "
                "Nossa equipe já foi notificada e entrará em contato pelo WhatsApp! 🚀"
            )
        else:
            await update.message.reply_text(
                f"🛑 Tive um problema ao conectar na planilha Google. Erro: {sheet_error}\n\nMas seu contato foi salvo na tela!"
            )
    except Exception as e:
        print(f"❌ ERRO AO SALVAR: {e}")
        await update.message.reply_text("Desculpe, tive um pequeno erro ao salvar.")

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("[SISTEMA] Conversa cancelada.")
    await update.message.reply_text("Atendimento encerrado.")
    return ConversationHandler.END


def build_conv_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NOME: [MessageHandler(filters.TEXT & (~filters.COMMAND), collect_name)],
            WHATSAPP: [MessageHandler(filters.TEXT & (~filters.COMMAND), collect_whatsapp)],
            MENSAGEM: [MessageHandler(filters.TEXT & (~filters.COMMAND), collect_message_and_save)],
        },
        fallbacks=[CommandHandler("cancelar", cancel)],
        allow_reentry=True
    )


def create_application():
    """Cria e retorna a aplicação PTB configurada (sem iniciar polling)."""
    if not TELEGRAM_TOKEN:
        print("❌ ERRO: TELEGRAM_TOKEN não configurado nas variáveis de ambiente!")
        sys.exit(1)
        
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(build_conv_handler())
    return application
