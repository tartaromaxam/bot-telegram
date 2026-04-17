import os
import json
import asyncio
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import requests as http_requests
from telegram import Update
from bot import connect_sheets, create_application

app = FastAPI(title="Mavinic Leads API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Constantes
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN') or "8665918764:AAFQ7YIbl9m1cF0psSAj3KPEhamUHc78DfY"
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID') or "1533451976"
WEBHOOK_URL = os.environ.get('RAILWAY_PUBLIC_DOMAIN')  # Ex: "bot-telegram-production-xxx.up.railway.app"

# Instância global da aplicação PTB
ptb_app = create_application()


def send_telegram_message(text: str):
    """Envia mensagem via API HTTP direta (para notificações do dono)."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        http_requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Erro ao notificar Telegram: {e}")


# --- WEBHOOK DO TELEGRAM ---

@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Recebe updates do Telegram via webhook (substitui o polling)."""
    try:
        data = await request.json()
        update = Update.de_json(data, ptb_app.bot)
        await ptb_app.process_update(update)
    except Exception as e:
        print(f"❌ Erro no webhook: {e}")
    return Response(status_code=200)


# --- APIs DOS FORMULÁRIOS ---

@app.post("/api/contato")
async def api_contato(request: Request):
    try:
        data = await request.json()
        name = data.get("name", "Sem Nome")
        email = data.get("email", "Sem Email")
        message = data.get("message", "Sem Mensagem")
        data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        sheet, sheet_error = connect_sheets()
        if sheet:
            sheet.append_row([name, email, f"PORTFÓLIO: {message} - {data_hora}"])
            print(f"✅ Nova Mensagem Salva: {name}")
        else:
            print(f"⚠️ Não salvou no Sheets. Erro: {sheet_error}")

        msg = (
            f"💼 *NOVO CONTATO NO PORTFÓLIO!*\n\n"
            f"👤 *Nome:* {name}\n"
            f"📧 *E-mail:* {email}\n"
            f"💬 *Mensagem:* {message}\n"
            f"⏰ *Data:* {data_hora}"
        )
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

        sheet, sheet_error = connect_sheets()
        if sheet:
            sheet.append_row([name, whatsapp, f"R$ {billAmount} - {data_hora}"])
            print(f"✅ Novo Lead Salvo: {name}")
        else:
            print(f"⚠️ Não salvou no Sheets. Erro: {sheet_error}")

        msg = (
            f"🚀 *NOVO LEAD DO SITE SOLAR!*\n\n"
            f"👤 *Nome:* {name}\n"
            f"📱 *WhatsApp:* {whatsapp}\n"
            f"💰 *Conta Mensal:* R$ {billAmount}\n"
            f"⏰ *Data:* {data_hora}"
        )
        send_telegram_message(msg)
        return {"success": True}
    except Exception as e:
        print(f"❌ Erro em /api/leads: {e}")
        return {"success": False, "error": str(e)}


# --- STARTUP ---

@app.on_event("startup")
async def startup_event():
    print("🚀 Iniciando Mavinic API + Bot Telegram (Webhook Mode)...")

    # Inicializa a aplicação PTB internamente (sem polling)
    await ptb_app.initialize()
    await ptb_app.start()

    # Configura o webhook no Telegram
    if WEBHOOK_URL:
        webhook_full_url = f"https://{WEBHOOK_URL}/webhook"
        await ptb_app.bot.set_webhook(url=webhook_full_url)
        print(f"✅ Webhook configurado: {webhook_full_url}")
    else:
        print("⚠️ RAILWAY_PUBLIC_DOMAIN não encontrado. Webhook não configurado.")


@app.on_event("shutdown")
async def shutdown_event():
    print("🛑 Encerrando aplicação...")
    await ptb_app.stop()
    await ptb_app.shutdown()


# --- HEALTH CHECK ---

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Mavinic API is running", "mode": "webhook"}
