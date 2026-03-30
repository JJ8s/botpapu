"""
Bot de Alertas de Inversión para Telegram
------------------------------------------
Requisitos:
  pip install python-telegram-bot anthropic schedule requests

Variables de entorno necesarias:
  TELEGRAM_TOKEN   → Token de tu bot (de @BotFather)
  ANTHROPIC_KEY    → Tu API key de Anthropic
  CHAT_ID          → Tu chat ID de Telegram (el bot te lo dice al escribirle /start)

Uso:
  python bot_alertas.py
"""

import os
import asyncio
import schedule
import time
import threading
import requests
from anthropic import Anthropic
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# ─── Configuración ────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "TU_TOKEN_AQUI")
ANTHROPIC_KEY  = os.getenv("ANTHROPIC_KEY",  "TU_API_KEY_AQUI")
CHAT_ID        = os.getenv("CHAT_ID",         "TU_CHAT_ID_AQUI")

# Tus umbrales personales del dólar
DOLAR_BARATO = 900   # Bajo este precio conviene comprar USD
DOLAR_CARO   = 970   # Sobre este precio conviene esperar
CAPITAL_CLP  = 25000 # Tu capital en pesos chilenos

client = Anthropic(api_key=ANTHROPIC_KEY)

# ─── Prompt del asistente ─────────────────────────────────────────────────────
SYSTEM_PROMPT = f"""Eres un asistente financiero especializado en inversiones en el S&P 500 desde Chile.
El usuario tiene estas preferencias:
- Capital disponible: ${CAPITAL_CLP:,} pesos chilenos
- Considera el dólar "barato" (bueno para comprar) cuando está bajo ${DOLAR_BARATO} CLP
- Considera el dólar "caro" (malo para comprar) cuando está sobre ${DOLAR_CARO} CLP

Tu rol:
1. Buscar el tipo de cambio USD/CLP actual
2. Buscar el rendimiento reciente del S&P 500
3. Dar una recomendación clara: COMPRAR, ESPERAR o SACAR
4. Explicar el razonamiento en 3-4 oraciones simples en español chileno
5. Calcular cuántos dólares obtendría con su capital al tipo de cambio actual
6. Usar emojis para hacer el mensaje más legible en Telegram
7. Al final escribe exactamente una de estas líneas:
   🟢 RECOMENDACIÓN: INVERTIR AHORA
   🟡 RECOMENDACIÓN: ESPERAR
   🔴 RECOMENDACIÓN: SACAR DINERO

Sé directo y usa datos reales y actualizados. Responde siempre en español."""

# ─── Obtener análisis de Claude ───────────────────────────────────────────────
def obtener_analisis(pregunta: str) -> str:
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            system=SYSTEM_PROMPT,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": pregunta}]
        )
        texto = " ".join(
            bloque.text for bloque in response.content
            if hasattr(bloque, "text")
        )
        return texto.strip()
    except Exception as e:
        return f"⚠️ Error al consultar el mercado: {str(e)}"

# ─── Enviar alerta automática ─────────────────────────────────────────────────
async def enviar_alerta_diaria(app):
    print("📤 Enviando alerta diaria...")
    analisis = obtener_analisis(
        "Dame el análisis diario completo del dólar y el S&P 500. "
        "¿Conviene invertir hoy mis pesos chilenos?"
    )
    try:
        await app.bot.send_message(
            chat_id=CHAT_ID,
            text=f"🌅 *Alerta diaria de inversión*\n\n{analisis}",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Error enviando alerta: {e}")

# ─── Scheduler en hilo separado ───────────────────────────────────────────────
def iniciar_scheduler(app):
    loop = asyncio.new_event_loop()

    def job():
        loop.run_until_complete(enviar_alerta_diaria(app))

    # Alerta automática cada mañana a las 9:00 AM
    schedule.every().day.at("09:00").do(job)

    print("⏰ Scheduler iniciado — alerta diaria a las 09:00")
    while True:
        schedule.run_pending()
        time.sleep(30)

# ─── Comandos del bot ─────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        f"🤖 *Bot de Alertas de Inversión*\n\n"
        f"Tu Chat ID es: `{chat_id}`\n\n"
        f"Comandos disponibles:\n"
        f"/analisis — Análisis completo ahora\n"
        f"/dolar — Tipo de cambio actual\n"
        f"/sp500 — Estado del S\\&P 500\n"
        f"/config — Ver tu configuración\n\n"
        f"O simplemente escríbeme lo que quieras saber 💬",
        parse_mode="Markdown"
    )

async def cmd_analisis(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Consultando mercado en tiempo real...")
    respuesta = obtener_analisis(
        "Dame un análisis completo ahora. ¿Conviene invertir mis pesos chilenos en el S&P 500 hoy?"
    )
    await update.message.reply_text(respuesta)

async def cmd_dolar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💵 Buscando tipo de cambio...")
    respuesta = obtener_analisis("¿Cuánto está el dólar en pesos chilenos ahora mismo? ¿Está caro o barato según mis umbrales?")
    await update.message.reply_text(respuesta)

async def cmd_sp500(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📈 Consultando S&P 500...")
    respuesta = obtener_analisis("¿Cómo está el S&P 500 hoy? ¿Subió o bajó? ¿Conviene comprar?")
    await update.message.reply_text(respuesta)

async def cmd_config(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"⚙️ *Tu configuración actual:*\n\n"
        f"💰 Capital: ${CAPITAL_CLP:,} CLP\n"
        f"🟢 Dólar barato: bajo ${DOLAR_BARATO} CLP\n"
        f"🔴 Dólar caro: sobre ${DOLAR_CARO} CLP\n"
        f"⏰ Alerta diaria: 09:00 AM\n\n"
        f"Para cambiar estos valores edita las variables al inicio del script.",
        parse_mode="Markdown"
    )

async def responder_mensaje(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    pregunta = update.message.text
    await update.message.reply_text("🔍 Analizando...")
    respuesta = obtener_analisis(pregunta)
    await update.message.reply_text(respuesta)

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("🚀 Iniciando bot de alertas...")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("analisis", cmd_analisis))
    app.add_handler(CommandHandler("dolar",    cmd_dolar))
    app.add_handler(CommandHandler("sp500",    cmd_sp500))
    app.add_handler(CommandHandler("config",   cmd_config))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder_mensaje))

    # Iniciar scheduler en hilo separado
    hilo = threading.Thread(target=iniciar_scheduler, args=(app,), daemon=True)
    hilo.start()

    print("✅ Bot corriendo. Escríbele /start en Telegram.")
    app.run_polling()

if __name__ == "__main__":
    main()
