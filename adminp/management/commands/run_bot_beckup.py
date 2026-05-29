import os
import re
import asyncio
import logging
from django.core.management.base import BaseCommand

from maxapi import Bot, Dispatcher, F
from maxapi.types import MessageCreated, MessageCallback, InputMedia
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from maxapi.types.attachments.buttons import CallbackButton

from asgiref.sync import sync_to_async
from adminp.services import find_answer_for_user, register_max_user, save_feedback, get_faq_list
from adminp.models import BotUser, UniversityGroups, BannedWord

logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("bot_token")
bot = Bot(token=TOKEN)
dp = Dispatcher()

user_states = {}

async def show_main_menu(event: MessageCreated, text="Выберите действие:"):
    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text="Задать вопрос", payload="ask_question"))
    builder.row(CallbackButton(text="Список частых вопросов", payload="get_faq"))
    builder.row(CallbackButton(text="Обратная связь", payload="feedback"))  
    await event.message.answer(text, attachments=[builder.as_markup()])

async def get_db_user(user_id):
    return await sync_to_async(
        lambda: BotUser.objects.select_related('group').filter(max_user_id=user_id).first()
    )()

@dp.message_created()
async def core_message_router(event: MessageCreated):
    user_id = event.message.sender.user_id
    text = event.message.body.text.strip() if event.message.body and event.message.body.text else ""
    
    state = user_states.get(user_id)
    
    if state == "waiting_group":
        entered_group = text.upper()
        group_exists = await sync_to_async(
            lambda: UniversityGroups.objects.filter(name=entered_group, is_active=True).exists()
        )()
        
        if group_exists:
            user_states[user_id] = "registered"
            success = await register_max_user(user_id, entered_group)
            if success:
                faq = await get_faq_list(entered_group)
                await event.message.answer(f"Группа {entered_group} найдена. Регистрация завершена!\n\n{faq}")
                await show_main_menu(event)
            else:
                user_states[user_id] = "waiting_group"
                await event.message.answer("Произошла ошибка при регистрации. Попробуйте позже.")
        else:
            await event.message.answer("Группа не найдена или неактивна. Попробуйте еще раз:")
        return

    elif state == "waiting_feedback":
        if len(text) < 10:
            await event.message.answer("Опишите проблему подробнее (минимум 10 символов).")
            await show_main_menu(event)
            return
            
        banned_words_list = await sync_to_async(
            lambda: list(BannedWord.objects.values_list('word', flat=True))
        )()

        clean_text = re.sub(r'[^\w\s]', '', text.lower())
        user_words = set(clean_text.split())

        intersection = user_words.intersection(banned_words_list)
        if intersection:
            await event.message.answer("Ваше сообщение содержит недопустимые слова. Попробуйте еще раз.")
            await show_main_menu(event)
            return
            
        await save_feedback(user_id, text)
        await event.message.answer("Спасибо! Отзыв отправлен администратору.")
        user_states[user_id] = "registered"
        await show_main_menu(event)
        return

    elif state == "waiting_question":
        user = await get_db_user(user_id)
        user_group = user.group.name if user and user.group else None
        
        response_data = await find_answer_for_user(text, user_id, user_group)
        await event.message.answer(response_data['answer'])
        
        if response_data.get('file'):
            await event.message.answer(attachments=[InputMedia(path=response_data['file'].path)])
            
        user_states[user_id] = "registered"
        await show_main_menu(event)
        return

    else:
        user = await get_db_user(user_id)
        
        if user:
            user_states[user_id] = "registered"
            await show_main_menu(event)
            return
            
        builder = InlineKeyboardBuilder()
        builder.row(CallbackButton(text="Студент", payload="set_student"))
        builder.row(CallbackButton(text="Абитуриент", payload="set_applicant"))
        await event.message.answer("Здравствуй! Выбери, кто ты?:", attachments=[builder.as_markup()])
    pass

@dp.message_callback(F.callback.payload == "set_student")
async def cb_set_student(event: MessageCallback):
    user_id = event.from_user.user_id
    user_states[user_id] = "waiting_group"
    await event.message.answer("Введите номер вашей группы (напр. ИСТД-21):")

@dp.message_callback(F.callback.payload == "set_applicant")
async def cb_set_applicant(event: MessageCallback):
    user_id = event.from_user.user_id
    await register_max_user(user_id, "Абитуриенты")
    user_states[user_id] = "registered"
    faq = await get_faq_list("Абитуриенты")
    await event.message.answer(f"Вы зарегистрированы как абитуриент!\n\n{faq}")
    await show_main_menu(event)

@dp.message_callback(F.callback.payload == "ask_question")
async def cb_ask_question(event: MessageCallback):
    user_id = event.from_user.user_id
    user_states[user_id] = "waiting_question"
    await event.message.answer("Напишите ваш вопрос:")

@dp.message_callback(F.callback.payload == "feedback")
async def cb_feedback(event: MessageCallback):
    user_id = event.from_user.user_id
    user_states[user_id] = "waiting_feedback"
    await event.message.answer("Напишите ваше сообщение администратору:")

@dp.message_callback(F.callback.payload == "get_faq")
async def cb_get_faq(event: MessageCallback):
    user_id = event.from_user.user_id
    user = await get_db_user(user_id)
    user_group = user.group.name if (user and user.group) else None
    faq_text = await get_faq_list(user_group)
    await event.message.answer(faq_text)
    await show_main_menu(event)

async def start_bot():
    try:
        await bot.delete_webhook()
    except Exception as e:
        print(f"Удаление вебхука не удалось: {e}")

    print("Бот MAX успешно запущен...")
    await dp.start_polling(bot)

class Command(BaseCommand):
    help = "Запуск чат-бота MAX"

    def handle(self, *args, **options):
        try:
            asyncio.run(start_bot())
        except KeyboardInterrupt:
            self.stdout.write(self.style.SUCCESS("Бот остановлен."))