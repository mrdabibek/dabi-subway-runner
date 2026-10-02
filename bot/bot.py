"""Telegram bot: referral system, lives economy, and tournament tracking (aiogram 3.x).

O'zbek tilidagi interfeys.

Buyruqlar:
  /start [ref_<id>]  Xush kelibsiz xabari, do'st taklifiga +1 jon
  /play              O'yinni boshlash (Telegram WebApp)
  /leaderboard       Top 10 rekordchilar ro'yxati (metrlarda)
  /invite            Shaxsiy referal havola va statistika
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional, Tuple
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from api.database import SessionLocal, init_db
from api.models import User, DAILY_LIVES, check_and_apply_user_milestone, get_tournament

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("runner-bot")

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
BOT_USERNAME: str = os.getenv("BOT_USERNAME", "mrxplay_bot").lstrip("@")
WEBAPP_URL: str = os.getenv("WEBAPP_URL", "")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi. .env fayliga bot tokeningizni kiriting.")

router = Router()


# ---------------- Database Helpers ----------------

def get_or_create_user(
    db: Session,
    uid: int,
    username: Optional[str],
    first_name: Optional[str],
) -> Tuple[User, bool]:
    """Get existing user or register new one. Returns (User, is_new)."""
    user = db.get(User, uid)
    if user is not None:
        user.ensure_daily_reset()
        if username and user.username != username:
            user.username = username
        if first_name and user.first_name != first_name:
            user.first_name = first_name
        db.commit()
        return user, False

    user = User(id=uid, username=username, first_name=first_name)
    user.ensure_daily_reset()  # Sets 3 lives and initial reset timestamp
    db.add(user)
    db.commit()
    db.refresh(user)
    try:
        milestone = check_and_apply_user_milestone(db)
        if milestone > 0:
            log.info("🎉 1,000 foydalanuvchi marrasi zabt etildi (%s)! Barchaga +3 jon berildi.", milestone)
    except Exception as ex:
        log.warning("Milestone check xatolik: %s", ex)
    return user, True



# ---------------- UI & Keyboard Builders ----------------

def is_valid_webapp_url(url: str) -> bool:
    """Verify that the WebApp URL is a valid public HTTPS endpoint with a real domain."""
    if not url or not url.startswith("https://"):
        return False
    parsed = urlparse(url)
    return bool(parsed.netloc and "." in parsed.netloc and "your-domain" not in parsed.netloc)


def referral_link(inviter_id: int) -> str:
    """Generate personal deep-link referral URL."""
    return f"https://t.me/{BOT_USERNAME}?start=ref_{inviter_id}"


def play_keyboard() -> InlineKeyboardMarkup:
    """Keyboard with WebApp Play button."""
    rows = []
    if is_valid_webapp_url(WEBAPP_URL):
        rows.append([InlineKeyboardButton(text="▶️ O'ynash", web_app=WebAppInfo(url=WEBAPP_URL))])
    else:
        rows.append([InlineKeyboardButton(text="ℹ️ WebApp sozlash (HTTPS kerak)", callback_data="need_https")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def gift_link(inviter_id: int) -> str:
    """Generate personal gift heart deep-link URL."""
    return f"https://t.me/{BOT_USERNAME}?start=gift_{inviter_id}"


def gift_keyboard(link: str) -> InlineKeyboardMarkup:
    """Keyboard for gifting heart to a friend."""
    share_text = "Salom! Men senga Subway Runnerda bepul 1 ta ❤️ Yurakcha sovg'a qildim! Kirib o'yna va 100-700 Stars yut!"
    share_url = f"https://t.me/share/url?url={link}&text={share_text.replace(' ', '+')}"
    rows = []
    if is_valid_webapp_url(WEBAPP_URL):
        rows.append([InlineKeyboardButton(text="▶️ O'ynash", web_app=WebAppInfo(url=WEBAPP_URL))])
    rows.append([InlineKeyboardButton(text="💝 Telegram orqali sovg'a qilish", url=share_url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def invite_keyboard(link: str, user_id: int = 0) -> InlineKeyboardMarkup:
    """Keyboard with WebApp Play, Share link, and Gift Heart button."""
    share_url = f"https://t.me/share/url?url={link}&text=Men+bilan+Subway+Runner+o'yna!+Sovrin+100-700+Stars+⭐"
    rows = []
    if is_valid_webapp_url(WEBAPP_URL):
        rows.append([InlineKeyboardButton(text="▶️ O'ynash", web_app=WebAppInfo(url=WEBAPP_URL))])
    rows.append([InlineKeyboardButton(text="📩 Do'st taklif qilish (Do'st o'ynasa +1 ❤️)", url=share_url)])
    if user_id > 0:
        g_url = gift_link(user_id)
        g_share = f"https://t.me/share/url?url={g_url}&text=Salom!+Men+senga+Subway+Runnerda+bepul+1+ta+❤️+yurakcha+sovg'a+qildim!+Kirib+o'yna+va+Stars+yut!"
        rows.append([InlineKeyboardButton(text="💝 Do'stga yurakcha sovg'a qilish", url=g_share)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def lives_line(user: User) -> str:
    """Format user's current lives and best distance."""
    return f"❤️ <b>Jonlar:</b> {user.lives}/{DAILY_LIVES} | 🏆 <b>Rekord:</b> {user.best_score} m"


def prize_banner(db: Session) -> str:
    """Tournament prize banner: Top 1-5 Stars (100, 50, 15, 10, 5), MEGA prize if 15,000 players join, and milestone."""
    t = get_tournament(db)
    milestone_line = f"🎁 <b>Hamjamiyat bonusi:</b> Har 1,000 ta yangi o'yinchida barchaga <b>+3 ❤️ jon</b> beriladi! (Hozir: {t.get('milestone_progress', 0)}/1000)"
    prizes_text = (
        "<b>🏆 TOURNAMENT SOVRINLARI (TOP 1-5):</b>\n"
        "🥇 1-o'rin: <b>100 ⭐ Stars</b>\n"
        "🥈 2-o'rin: <b>50 ⭐ Stars</b>\n"
        "🥉 3-o'rin: <b>15 ⭐ Stars</b>\n"
        "4️⃣ 4-o'rin: <b>10 ⭐ Stars</b>\n"
        "5️⃣ 5-o'rin: <b>5 ⭐ Stars</b>\n"
        "<i>(Kafolatlangan sovrin jamg'armasi: 180 ⭐)</i>"
    )
    if t["mega_unlocked"]:
        return (
            f"🏆 <b>MEGA SOVRIN OCHILDI: {t['mega_prize']} ⭐ STARS!</b> 🎉\n"
            f"{prizes_text}\n"
            f"👥 Jami qatnashuvchilar: <b>{t['participants']}</b> ta\n"
            f"{milestone_line}"
        )
    return (
        f"{prizes_text}\n"
        f"🔥 Agar 1 haftada {t['goal']:,} ta o'yinchi qo'shilsa → <b>{t['mega_prize']} ⭐ MEGA sovrin</b>!\n"
        f"👥 Hozir: <b>{t['participants']}</b> / {t['goal']:,} ta o'yinchi (⏳ {t['days_left']} kun qoldi)\n"
        f"{milestone_line}"
    )


async def send_welcome_screen(
    target_msg: Message,
    uid: int,
    username: Optional[str],
    first_name: Optional[str],
    payload: str = "",
):
    """Deliver full welcome / dashboard screen with lives, tournament status, and play button."""
    db: Session = SessionLocal()
    try:
        user, is_new = get_or_create_user(
            db,
            uid=uid,
            username=username,
            first_name=first_name,
        )

        ref_message_line = ""

        # Handle referral / gift payload
        if payload.startswith("ref_") or payload.startswith("gift_"):
            is_gift = payload.startswith("gift_")
            try:
                inviter_id = int(payload.split("_", 1)[1])
            except (ValueError, IndexError):
                inviter_id = 0

            if inviter_id == uid:
                ref_message_line = "\n⚠️ <i>O'zingizning havolangizdan foydalana olmaysiz.</i>"
            elif inviter_id > 0 and is_new and user.referred_by is None:
                inviter = db.get(User, inviter_id)
                if inviter is None:
                    inviter = User(id=inviter_id)
                    inviter.ensure_daily_reset()
                    db.add(inviter)

                user.referred_by = inviter_id
                user.referral_rewarded = False

                if is_gift:
                    user.lives += 1
                    ref_message_line = (
                        "\n💝 <b>Tabriklaymiz! Do'stingiz sizga 1 ta ❤️ Yurakcha (Jon) sovg'a qildi!</b>\n"
                        "<i>Sizga bepul +1 ❤️ Jon berildi! Birinchi o'yiningizni o'ynashingiz bilanoq do'stingizga ham +1 ❤️ jon taqdim etiladi.</i>"
                    )
                else:
                    ref_message_line = "\n🎁 <b>Do'stingiz taklifi bilan kirdingiz! Birinchi o'yiningizni o'ynashingiz bilanoq do'stingizga +1 ❤️ jon taqdim etiladi.</b>"

                db.commit()

            elif not is_new:
                if is_gift:
                    ref_message_line = "\nℹ️ <i>Siz allaqachon ro'yxatdan o'tgansiz! O'zingiz ham do'stlaringizga /gift buyrug'i orqali yurakcha sovg'a qiling.</i>"
                else:
                    ref_message_line = "\nℹ️ <i>Referal bonusi faqat yangi o'yinchilar birinchi marta o'ynaganida beriladi.</i>"

        personal_ref = referral_link(uid)

        welcome_text = (
            f"🏃‍♂️ <b>Subway Runner 3D o'yiniga xush kelibsiz!</b>{ref_message_line}\n\n"
            f"{prize_banner(db)}\n\n"
            f"{lives_line(user)}\n"
            f"🔄 <i>Jonlar har 24 soatda 3 taga to'ldiriladi yoki do'st taklif qilib oshiriladi.</i>\n\n"
            f"🔗 <b>Sizning taklif havolangiz:</b>\n"
            f"<code>{personal_ref}</code>\n\n"
            f"🎮 <b>Boshqaruv:</b>\n"
            f"⬆️ Sakrash | ⬇️ Sirpanish | ◀️ ▶️ Yo'lakni o'zgartirish | 🛹 Skeytbord\n"
            f"<b>Eng uzoq masofaga yugurgan o'yinchi Stars yutadi!</b>"
        )

        try:
            await target_msg.answer(
                text=welcome_text,
                reply_markup=invite_keyboard(personal_ref, user_id=uid),
            )
        except TelegramBadRequest as ex:
            log.warning("Keyboard send failed (%s), sending without keyboard", ex)
            await target_msg.answer(text=welcome_text)
    finally:
        db.close()


# ---------------- Command Handlers ----------------

@router.message(CommandStart())
async def cmd_start(msg: Message, command: CommandObject):
    """Handle /start and /start ref_<inviter_id> deep links."""
    if msg.from_user is None:
        return

    uid = msg.from_user.id
    payload = (command.args or "").strip()

    await send_welcome_screen(
        target_msg=msg,
        uid=uid,
        username=msg.from_user.username,
        first_name=msg.from_user.first_name,
        payload=payload,
    )


@router.message(Command("play"))
async def cmd_play(msg: Message):
    """Handle /play command and verify lives."""
    if msg.from_user is None:
        return

    uid = msg.from_user.id

    db: Session = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db,
            uid=uid,
            username=msg.from_user.username,
            first_name=msg.from_user.first_name,
        )
        if user.lives <= 0:
            link = referral_link(user.id)
            await msg.answer(
                text=(
                    f"💔 <b>Afsuski, jonlaringiz tugagan!</b>\n"
                    f"{lives_line(user)}\n\n"
                    f"Do'stlaringizni taklif qiling va ular birinchi marta o'ynaganida sizga <b>+1 jon (❤️)</b> beriladi:\n"
                    f"<code>{link}</code>"
                ),
                reply_markup=invite_keyboard(link),
            )
            return

        text = (
            f"⚡ <b>Yugurishga tayyormisiz?</b>\n"
            f"{lives_line(user)}\n\n"
            f"O'yinni boshlash uchun quyidagi tugmani bosing:"
        )
        try:
            await msg.answer(text=text, reply_markup=play_keyboard())
        except TelegramBadRequest as ex:
            log.warning("Play keyboard failed (%s)", ex)
            await msg.answer(text=text)
    finally:
        db.close()


@router.message(Command("leaderboard"))
async def cmd_leaderboard(msg: Message):
    """Handle /leaderboard command: display top 10 runners by distance (meters)."""
    db: Session = SessionLocal()
    try:
        top_runners = db.query(User).order_by(User.best_score.desc()).limit(10).all()
        banner = prize_banner(db)

        if not top_runners or max(u.best_score for u in top_runners) == 0:
            await msg.answer(
                text=f"{banner}\n\n📊 <i>Hali hech kim rekord o'rnatmadi — birinchi bo'ling!</i>\n/play",
            )
            return

        lines = [
            banner,
            "",
            "🏆 <b>TOP-10 REKORDCHILAR (Masofa)</b>",
            "───────────────────",
        ]
        medals = ["🥇", "🥈", "🥉"]

        for idx, runner in enumerate(top_runners, start=1):
            name = f"@{runner.username}" if runner.username else f"Foydalanuvchi {runner.id}"
            prefix = medals[idx - 1] if idx <= 3 else f"{idx}."
            lines.append(f"{prefix} {name} — <b>{runner.best_score} m</b>")

        await msg.answer(text="\n".join(lines))
    finally:
        db.close()


@router.message(Command("invite"))
async def cmd_invite(msg: Message):
    """Handle /invite command: display referral statistics and share link."""
    if msg.from_user is None:
        return

    db: Session = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db,
            uid=msg.from_user.id,
            username=msg.from_user.username,
            first_name=msg.from_user.first_name,
        )
        link = referral_link(user.id)

        await msg.answer(
            text=(
                f"📩 <b>Do'stlarni taklif qilish tizimi</b>\n\n"
                f"Har bir taklif qilingan do'stingiz uchun sizga <b>+1 jon</b> beriladi!\n\n"
                f"🔗 <b>Sizning havolangiz:</b>\n"
                f"<code>{link}</code>\n\n"
                f"{lives_line(user)}\n"
                f"👥 <b>Jami taklif qilgan do'stlaringiz:</b> {user.referral_count} ta"
            ),
            reply_markup=invite_keyboard(link, user_id=user.id),
        )
    finally:
        db.close()


@router.message(Command("gift"))
async def cmd_gift(msg: Message):
    """Handle /gift command: gift a heart/life to a friend."""
    if msg.from_user is None:
        return

    db: Session = SessionLocal()
    try:
        user, _ = get_or_create_user(
            db,
            uid=msg.from_user.id,
            username=msg.from_user.username,
            first_name=msg.from_user.first_name,
        )
        g_link = gift_link(user.id)
        await msg.answer(
            text=(
                "💝 <b>Yurakcha (Jon) sovg'a qilish bo'limi</b>\n\n"
                "Do'stingizga o'ynash uchun <b>❤️ 1 ta Jon (Yurakcha)</b> sovg'a qiling!\n\n"
                "🎁 <b>Do'stingiz oladi:</b> Havoladan kirishi bilan bepul <b>+1 ❤️ Jon</b>!\n"
                "❤️ <b>Siz olasiz:</b> Do'stingiz 1-o'yinini o'ynashi bilanoq sizga ham <b>+1 ❤️ Jon</b>!\n\n"
                f"🔗 <b>Sizning shaxsiy sovg'a havolangiz:</b>\n"
                f"<code>{g_link}</code>\n\n"
                f"{lives_line(user)}"
            ),
            reply_markup=gift_keyboard(g_link),
        )
    finally:
        db.close()


@router.callback_query(F.data == "need_https")
async def on_need_https(cb: CallbackQuery):
    """Notify user about WebApp URL setup."""
    await cb.answer(
        "Telegram WebApp faqat HTTPS manzillarda ishlaydi.\n"
        "Brauzeringizda o'ynash uchun:\nhttp://127.0.0.1:8000/webapp/",
        show_alert=True,
    )


@router.message(F.web_app_data)
async def on_webapp_data(msg: Message):
    """Receive data sent directly from Telegram.WebApp.sendData."""
    await msg.answer("✅ Natijangiz qabul qilindi!", reply_markup=play_keyboard())


async def update_menu_button(bot: Bot) -> None:
    while True:
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="🎮 O'ynash", web_app=WebAppInfo(url=WEBAPP_URL))
            )
            log.info("Telegram Chat Menu Button yangilandi: %s", WEBAPP_URL)
            return
        except Exception as ex:
            log.warning("Chat Menu Button o'rnatishda xatolik, 10 soniyada qayta uriniladi: %s", ex)
            await asyncio.sleep(10)


async def main() -> None:
    """Initialize DB and start Telegram Bot polling."""
    init_db()
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)

    log.info("Telegram bot @%s ishga tushirildi! WebApp URL: %s", BOT_USERNAME, WEBAPP_URL)
    if is_valid_webapp_url(WEBAPP_URL):
        asyncio.create_task(update_menu_button(bot))
    while True:
        try:
            await dp.start_polling(bot)
        except Exception as e:
            log.warning("Bot pollingda tarmoq xatoligi, 5 soniyada qayta ulanmoqda: %s", e)
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
