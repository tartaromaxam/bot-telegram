import os
import json
import gspread
import logging
import sys
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials

# Garantir que o terminal aceite emojis no Windows
if sys.stdout.encoding != 'utf-8':
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except:
        pass
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# ESTADOS DA CONVERSA
NOME, WHATSAPP, MENSAGEM = range(3)

# CONFIGURAÇÕES
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN') or "8665918764:AAFQ7YIbl9m1cF0psSAj3KPEhamUHc78DfY"
SPREADSHEET_NAME = "Leads Bot"
JSON_FILE_PATH = os.path.join(os.path.dirname(__file__), "credenciais.json")

# Habilitar logging básico para ver erros no terminal
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def connect_sheets():
    import json
    try:
        scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
                 "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
        
        # Modo 1: Variável com o JSON Inteiro (Mais seguro)
        google_json = os.environ.get('GOOGLE_SHEETS_JSON')
        # Modo 2: Chave Privada + Email divididos
        private_key = os.environ.get('GOOGLE_PRIVATE_KEY')
        email = os.environ.get('GOOGLE_SERVICE_ACCOUNT_EMAIL')
        
        if google_json:
            try:
                creds_dict = json.loads(google_json)
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                print("✅ Conectado ao Google Sheets via GOOGLE_SHEETS_JSON.")
            except Exception as j_err:
                raise Exception(f"Erro ao parsear GOOGLE_SHEETS_JSON: {j_err}")
                
        elif private_key and email:
            # Limpar formatações duplas e aspas que o painel pode injetar
            cleaned_key = private_key.strip('"').strip("'")
            cleaned_key = cleaned_key.replace('\\n', '\n').replace('\\\\n', '\n')
            email = email.strip('"').strip("'")
            
            creds_dict = {
                "type": "service_account",
                "private_key": cleaned_key,
                "client_email": email,
                "token_uri": "https://oauth2.googleapis.com/token",
            }
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            print("✅ Conectado ao Google Sheets via Variáveis Separadas.")
            
        elif os.path.exists(JSON_FILE_PATH):
            creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_FILE_PATH, scope)
            print("✅ Conectado ao Google Sheets via Arquivo Local.")
        else:
            raise Exception("Nenhuma credencial do Google (Arquivo ou Variável)!")

        client = gspread.authorize(creds)
        return client.open("Leads Bot").sheet1, None
    except Exception as e:
        print(f"❌ ERRO GOOGLE SHEETS: {e}")
        return None, str(e)


# --- INÍCIO ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    source_arg = context.args[0] if context.args else "geral"
    context.user_data['origem'] = source_arg
    
    print(f"\n[SISTEMA] /start recebido. Origem: {source_arg}")
    
    greeting = ("Olá! Sou o assistente da Nexara Solar. 👋\nQual seu *Nome Completo*?" if source_arg == "solar" 
                else "Olá! Sou o assistente da Mavinic Digital. 👋\nQual seu *Nome Completo*?")

    await update.message.reply_text(greeting)
    return NOME

# --- CAPTURA NOME ---
async def collect_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    print(f"[SISTEMA] Nome recebido: {name}")
    context.user_data['nome'] = name
    
    await update.message.reply_text(f"Obrigado, {name}! Agora, qual o seu *WhatsApp* com DDD?")
    return WHATSAPP

# --- CAPTURA WHATSAPP ---
async def collect_whatsapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    whatsapp = update.message.text
    print(f"[SISTEMA] WhatsApp recebido: {whatsapp}")
    context.user_data['whatsapp'] = whatsapp
    
    origem = context.user_data.get('origem', 'geral')
    
    if origem == "solar":
        question = "Perfeito! Para agilizar seu diagnóstico, qual o valor médio da sua conta de luz ou qual sua principal dúvida sobre energia solar?"
    elif origem == "portfolio":
        question = "Excelente! Me conte um pouco mais sobre o site ou projeto digital que você tem em mente? (Ex: Loja virtual, Landing Page, Site institucional...)"
    else:
        question = "Perfeito. Como posso te ajudar hoje? Pode descrever sua dúvida abaixo."

    await update.message.reply_text(question)
    return MENSAGEM

# --- SALVA TUDO ---
async def collect_message_and_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_text = update.message.text
    nome = context.user_data.get('nome')
    whatsapp = context.user_data.get('whatsapp')
    origem = context.user_data.get('origem', 'geral').upper()
    
    print(f"[SISTEMA] Finalizando lead: {nome}")

    try:
        data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        sheet, sheet_error = connect_sheets()
        if sheet:
            # Salva: Nome | WhatsApp | Mensagem | Origem | Data/Hora
            sheet.append_row([nome, whatsapp, msg_text, origem, data_hora])
            print(f"✅ REGISTRO SALVO NA PLANILHA: {data_hora}")
            
            await update.message.reply_text(
                f"✅ Recebido, {nome}!\n\nSalvei sua mensagem sobre: '{msg_text}'. \n"
                "Nossa equipe já foi notificada e entraremos em contato com você em breve pelo WhatsApp! 🚀"
            )
        else:
            await update.message.reply_text(f"🛑 Tive um problema ao conectar na planilha Google. Erro Exato: {sheet_error}\n\nMas seu contato foi salvo na tela!")
    except Exception as e:
        print(f"❌ ERRO AO SALVAR: {e}")
        await update.message.reply_text("Desculpe, tive um pequeno erro ao salvar, mas não se preocupe, tentaremos novamente.")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("[SISTEMA] Conversa cancelada.")
    await update.message.reply_text("Atendimento encerrado.")
    return ConversationHandler.END

if __name__ == "__main__":
    print("\n--- CONFIGURANDO ROBÔ ---")
    print(f"Token: {TELEGRAM_TOKEN[:10]}... (protegido)")
    
    try:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        print("✅ Conexão com Telegram estabelecida.")
    except Exception as e:
        print(f"❌ ERRO AO CONECTAR TOKEN: {e}")
        exit()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NOME: [MessageHandler(filters.TEXT & (~filters.COMMAND), collect_name)],
            WHATSAPP: [MessageHandler(filters.TEXT & (~filters.COMMAND), collect_whatsapp)],
            MENSAGEM: [MessageHandler(filters.TEXT & (~filters.COMMAND), collect_message_and_save)],
        },
        fallbacks=[CommandHandler("cancelar", cancel)],
        allow_reentry=True
    )

    app.add_handler(conv_handler)
    print("✅ Robô Online! Pode testar no Telegram.")
    app.run_polling()
