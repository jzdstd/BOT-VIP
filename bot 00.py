import logging
import asyncio
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from aiohttp import web

# ─────────────────────────────────────────────
#  CONFIGURAÇÕES
# ─────────────────────────────────────────────
BOT_TOKEN = "8527797986:AAEYpLqegi7DTfvTvsekGEDoVIcZ8dfRR1I"
MP_ACCESS_TOKEN = "APP_USR-8417097908862425-061015-3456e7037ac72b3c4fe77f477d91825a-3331181571"
GRUPO_VIP_ID = -1003798821382
WEBHOOK_URL = "https://bot-vip-production-7def.up.railway.app"
VIDEO_FILE_ID = "AAMCAQADGQEAAUwcSGoqLmAyVc3XPxjKdOvyiSn38_m5AAIZBgACq-xYRaeHPfP6l0vUAQAHbQADOwQ"

PLANOS = {

    "mensal":    {"nome": "Acesso Mensal",    "preco": 15.00, "dias": 30},
    "trimestral": {"nome": "Acesso Bimestral", "preco": 25.00, "dias": 60},
    "vitalicio": {"nome": "Acesso Vitalício", "preco": 35.00, "dias": 36500},
}
# ─────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

pagamentos_pendentes = {}

TEXTO_APRESENTACAO = """🔥 *MEGA VIP — O MAIOR GRUPO +18 DO TELEGRAM* 🔥

Juntamos tudo em um só lugar, pagando apenas *1 assinatura* você tem acesso a:

✅ OnlyFans e Privacidades
✅ Cornos e Cuckold
✅ Novinhas
✅ Incesto
✅ Lives Reais +18
✅ Amadores Reais
✅ Sexo Anal
✅ Sexo em Público
✅ Novinhas do TikTok
✅ Filmes Completos
✅ Câmeras Escondidas
✅ Atualizações Diárias
✅ Acesso Imediato

👇 *Veja uma prévia do conteúdo e escolha seu plano!*"""


# ── /start ───────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Envia o vídeo de prévia com a apresentação como legenda
    keyboard = [
        [InlineKeyboardButton("🛒 Ver planos e assinar", callback_data="ver_planos")],
        [InlineKeyboardButton("❓ Suporte", url="https://t.me/vemnafonte18")],
    ]

    await update.message.reply_video(
        video=VIDEO_FILE_ID,
        caption=TEXTO_APRESENTACAO,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ── Ver planos ───────────────────────────────
async def ver_planos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = []
    for key, plano in PLANOS.items():
        label = f"{plano['nome']} — R$ {plano['preco']:.2f}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"comprar_{key}")])

    await query.edit_message_caption(
        caption=(
            "📦 *Escolha seu plano:*\n\n"
            "🗓 Semanal — R$ 10,00 (7 dias)\n"
            "📅 Mensal — R$ 15,00 (30 dias)\n"
            "📆 Bimestral — R$ 25,00 (60 dias)\n"
            "♾️ Vitalício — R$ 45,00\n\n"
            "👆 Selecione um plano abaixo:"
        ),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ── Gera PIX ─────────────────────────────────
async def comprar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chave = query.data.replace("comprar_", "")
    plano = PLANOS.get(chave)
    if not plano:
        return

    user = query.from_user

    await query.edit_message_caption(caption="⏳ Gerando seu PIX, aguarde...")

    payload = {
        "transaction_amount": plano["preco"],
        "description": plano["nome"],
        "payment_method_id": "pix",
        "external_reference": f"{user.id}_{chave}",
        "notification_url": f"{WEBHOOK_URL}/webhook",
        "payer": {
            "email": f"{user.id}@telegram.bot",
            "first_name": user.first_name or "Cliente",
            "last_name": "VIP",
            "identification": {
                "type": "CPF",
                "number": "00000000000"
            }
        }
    }

    headers = {
        "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Idempotency-Key": f"{user.id}-{chave}-{int(asyncio.get_event_loop().time())}",
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.mercadopago.com/v1/payments",
                json=payload,
                headers=headers,
                timeout=15,
            )
        data = response.json()
        logger.info(f"Resposta MP: {data}")

        pix_data = data.get("point_of_interaction", {}).get("transaction_data", {})
        qr_code = pix_data.get("qr_code", "")
        payment_id = str(data.get("id", ""))

        if not qr_code:
            await query.edit_message_caption(
                caption="❌ Erro ao gerar PIX. Tente novamente.\n\n"
                f"Detalhe: {data.get('message', 'Erro desconhecido')}"
            )
            return

        pagamentos_pendentes[payment_id] = user.id

        keyboard = [[InlineKeyboardButton("🔙 Voltar aos planos", callback_data="ver_planos")]]

        await query.edit_message_caption(
            caption=(
                f"✅ *{plano['nome']}* — R$ {plano['preco']:.2f}\n\n"
                f"📋 *PIX Copia e Cola:*\n`{qr_code}`\n\n"
                "👆 Toque no código acima para copiar, depois abra seu banco e cole no campo PIX.\n\n"
                "⏰ Este PIX expira em *30 minutos*.\n"
                "✅ Após o pagamento, você receberá o link do grupo automaticamente!"
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    except Exception as e:
        logger.error(f"Erro ao gerar PIX: {e}")
        await query.edit_message_caption(caption="❌ Erro ao gerar PIX. Tente novamente.")


# ── Webhook Mercado Pago ──────────────────────
async def webhook_mp(request):
    try:
        data = await request.json()
        logger.info(f"Webhook recebido: {data}")

        if data.get("type") != "payment":
            return web.Response(status=200)

        payment_id = str(data["data"]["id"])

        headers = {"Authorization": f"Bearer {MP_ACCESS_TOKEN}"}
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.mercadopago.com/v1/payments/{payment_id}",
                headers=headers,
            )
        payment = response.json()

        if payment.get("status") != "approved":
            return web.Response(status=200)

        external_ref = payment.get("external_reference", "")
        if "_" not in external_ref:
            return web.Response(status=200)

        user_id_str, plano_key = external_ref.split("_", 1)
        user_id = int(user_id_str)
        plano = PLANOS.get(plano_key)

        bot = request.app["bot"]

        try:
            link = await bot.create_chat_invite_link(
                chat_id=GRUPO_VIP_ID,
                member_limit=1,
            )
            await bot.send_message(
                chat_id=user_id,
                text=(
                    f"🎉 *Pagamento confirmado!*\n\n"
                    f"Plano: {plano['nome'] if plano else plano_key}\n\n"
                    f"Use o link abaixo para entrar no grupo VIP:\n{link.invite_link}\n\n"
                    "⚠️ Este link é de uso único e exclusivo para você.\n"
                    "Bem-vindo ao Mega VIP! 🔥"
                ),
                parse_mode="Markdown",
            )
            logger.info(f"Usuário {user_id} liberado com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao enviar convite: {e}")

    except Exception as e:
        logger.error(f"Erro no webhook: {e}")

    return web.Response(status=200)


# ── Servidor web ──────────────────────────────
async def run_web(bot):
    web_app = web.Application()
    web_app["bot"] = bot
    web_app.router.add_post("/webhook", webhook_mp)
    web_app.router.add_get("/", lambda r: web.Response(text="Bot rodando!"))

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    logger.info("Servidor webhook rodando na porta 8080")


# ── Main ──────────────────────────────────────
async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(ver_planos, pattern="^ver_planos$"))
    app.add_handler(CallbackQueryHandler(comprar, pattern="^comprar_"))

    await app.initialize()
    await app.start()
    await run_web(app.bot)
    await app.updater.start_polling()

    logger.info("Bot rodando...")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
