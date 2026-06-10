import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import mercadopago
from aiohttp import web

# ─────────────────────────────────────────────
#  CONFIGURAÇÕES
# ─────────────────────────────────────────────
BOT_TOKEN = "8527797986:AAEYpLqegi7DTfvTvsekGEDoVIcZ8dfRR1I"
MP_ACCESS_TOKEN = "APP_USR-8417097908862425-061015-3456e7037ac72b3c4fe77f477d91825a-3331181571"
GRUPO_VIP_ID = -1003798821382
WEBHOOK_URL = "https://bot-vip-production-7def.up.railway.app"

PLANOS = {
    "mensal": {"nome": "Acesso Mensal", "preco": 29.90, "dias": 30},
    "trimestral": {"nome": "Acesso Trimestral", "preco": 69.90, "dias": 90},
    "anual": {"nome": "Acesso Anual", "preco": 199.90, "dias": 365},
}
# ─────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sdk = mercadopago.SDK(MP_ACCESS_TOKEN)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("🛒 Ver planos", callback_data="ver_planos")],
        [InlineKeyboardButton("❓ Suporte", url="https://t.me/vemnafonte18")],
    ]
    await update.message.reply_text(
        f"Olá, {user.first_name}! 👋\n\n"
        "Bem-vindo ao nosso grupo VIP.\n"
        "Aqui você terá acesso a conteúdo exclusivo.\n\n"
        "Escolha uma opção abaixo:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def ver_planos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = []
    for key, plano in PLANOS.items():
        label = f"{plano['nome']} — R$ {plano['preco']:.2f}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"comprar_{key}")])

    await query.edit_message_text(
        "📦 *Escolha seu plano:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def comprar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chave = query.data.replace("comprar_", "")
    plano = PLANOS.get(chave)
    if not plano:
        return

    user = query.from_user

    preference_data = {
        "items": [
            {
                "title": plano["nome"],
                "quantity": 1,
                "unit_price": plano["preco"],
                "currency_id": "BRL",
            }
        ],
        "payer": {"email": f"{user.id}@telegram.bot"},
        "external_reference": f"{user.id}_{chave}",
        "notification_url": f"{WEBHOOK_URL}/webhook",
        "payment_methods": {
            "excluded_payment_types": [
                {"id": "ticket"}
            ]
        },
        "back_urls": {
            "success": f"{WEBHOOK_URL}/sucesso",
            "failure": f"{WEBHOOK_URL}/falha",
        },
        "auto_return": "approved",
    }

    result = sdk.preference().create(preference_data)
    pref = result.get("response", {})
    link_pagamento = pref.get("init_point", "")

    if not link_pagamento:
        await query.edit_message_text("❌ Erro ao gerar pagamento. Tente novamente.")
        return

    keyboard = [
        [InlineKeyboardButton("💳 Pagar agora (PIX/Cartão)", url=link_pagamento)],
        [InlineKeyboardButton("🔙 Voltar", callback_data="ver_planos")],
    ]

    await query.edit_message_text(
        f"✅ *{plano['nome']}* — R$ {plano['preco']:.2f}\n\n"
        "Clique no botão abaixo para pagar via PIX ou cartão.\n"
        "Após a confirmação, você será adicionado ao grupo automaticamente! 🚀",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def webhook_mp(request):
    try:
        data = await request.json()
        logger.info(f"Webhook recebido: {data}")

        if data.get("type") != "payment":
            return web.Response(status=200)

        payment_id = data["data"]["id"]
        payment_info = sdk.payment().get(payment_id)
        payment = payment_info.get("response", {})

        if payment.get("status") != "approved":
            return web.Response(status=200)

        external_ref = payment.get("external_reference", "")
        if "_" not in external_ref:
            return web.Response(status=200)

        user_id_str, plano_key = external_ref.split("_", 1)
        user_id = int(user_id_str)
        plano = PLANOS.get(plano_key)

        app = request.app["bot_app"]
        bot = app.bot

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
                    "⚠️ Este link é de uso único e exclusivo para você."
                ),
                parse_mode="Markdown",
            )
            logger.info(f"Usuário {user_id} liberado com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao enviar convite: {e}")

    except Exception as e:
        logger.error(f"Erro no webhook: {e}")

    return web.Response(status=200)


async def run_web(bot_app):
    web_app = web.Application()
    web_app["bot_app"] = bot_app
    web_app.router.add_post("/webhook", webhook_mp)
    web_app.router.add_get("/sucesso", lambda r: web.Response(text="Pagamento aprovado! Volte ao Telegram."))
    web_app.router.add_get("/falha", lambda r: web.Response(text="Pagamento não concluído. Tente novamente."))

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    logger.info("Servidor webhook rodando na porta 8080")


async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(ver_planos, pattern="^ver_planos$"))
    app.add_handler(CallbackQueryHandler(comprar, pattern="^comprar_"))

    await app.initialize()
    await app.start()
    await run_web(app)
    await app.updater.start_polling()

    logger.info("Bot rodando...")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
