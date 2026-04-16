import os
import subprocess
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import requests
import asyncio
from bot import connect_sheets

app = FastAPI(title="Mavinic Leads API")

# Setup CORS para permitir requisições dos sites na Hostinger
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Constantes do Telegram
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN') or "8665918764:AAFQ7YIbl9m1cF0psSAj3KPEhamUHc78DfY"
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID') or "1533451976"

def send_telegram_message(text: str):
    """Envia uma mensagem para o dono no Telegram usando a API HTTP diretamente."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Erro ao notificar Telegram da API: {e}")

@app.post("/api/contato")
async def api_contato(request: Request):
    try:
        data = await request.json()
        name = data.get("name", "Sem Nome")
        email = data.get("email", "Sem Email")
        message = data.get("message", "Sem Mensagem")
        
        data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        # 1. Salvar no Google Sheets
        sheet, sheet_error = connect_sheets()
        if sheet:
            sheet.append_row([name, email, f"PORTFÓLIO: {message} - {data_hora}"])
            print(f"✅ Nova Mensagem Salva: {name}")
        else:
            print(f"⚠️ Aviso: Não salvou no Sheets. Erro: {sheet_error}")

        # 2. Notificar no Telegram
        msg = (f"💼 *NOVO CONTATO NO PORTFÓLIO!*\n\n"
               f"👤 *Nome:* {name}\n"
               f"📧 *E-mail:* {email}\n"
               f"💬 *Mensagem:* {message}\n"
               f"⏰ *Data:* {data_hora}")
        send_telegram_message(msg)

        return {"success": True}
    except Exception as e:
        print(f"❌ Erro em /api/contato: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/leads")
async def api_leads(request: Request):
    try:
        data = await request.json()
        name = data.get("name", "Sem Nome")
        whatsapp = data.get("whatsapp", "Sem WhatsApp")
        billAmount = data.get("billAmount", "0")
        
        data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        # 1. Salvar no Google Sheets (Origem: SOLAR_LP)
        sheet, sheet_error = connect_sheets()
        if sheet:
            sheet.append_row([name, whatsapp, f"R$ {billAmount} - {data_hora}"])
            print(f"✅ Novo Lead Salvo: {name}")
        else:
            print(f"⚠️ Aviso: Não salvou no Sheets. Erro: {sheet_error}")

        # 2. Notificar no Telegram
        msg = (f"🚀 *NOVO LEAD DO SITE SOLAR!*\n\n"
               f"👤 *Nome:* {name}\n"
               f"📱 *WhatsApp:* {whatsapp}\n"
               f"💰 *Conta Mensal:* R$ {billAmount}\n"
               f"⏰ *Data:* {data_hora}")
        send_telegram_message(msg)

        return {"success": True}
    except Exception as e:
        print(f"❌ Erro em /api/leads: {e}")
        return {"success": False, "error": str(e)}

@app.on_event("startup")
def startup_event():
    # Inicializa o bot do telegram em background (em um processo separado mas na mesma máquina Dyno)
    print("🚀 Iniciando servidor FastAPI e lançando o robô do Telegram em Background...")
    # Executamos o bot do telegram no terminal interativo para não travar a API HTTP
    try:
        bot_script_path = os.path.join(os.path.dirname(__file__), "bot.py")
        subprocess.Popen(["python", bot_script_path])
    except Exception as e:
        print(f"❌ Erro ao iniciar subprocesso do bot: {e}")

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Mavinic API is running"}
