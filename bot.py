import os
import django
import asyncio

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from maxapi import Bot, Dispatcher, F
from maxapi.types import MessageCreated, MessageCallback, InputMedia
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from maxapi.types.attachments.buttons import CallbackButton

from asgiref.sync import sync_to_async
from adminp.services import find_answer_for_user, register_max_user, save_feedback, get_faq_list
from adminp.models import BotUser, UniversityGroups

TOKEN = "f9LHodD0cOLzBrjTEdNthgfvCzKPHzp6suQuO14eCJWqnwpOCERXyNan2vxoViX4FPOcxVcjAtga1lW14zVE"
bot = Bot(token=TOKEN)
dp = Dispatcher()

user_states = {}
BANNED_WORDS = ["спам", "реклама", "мат"]

async def show_main_menu(event: MessageCreated, text="Выберите действие:"):
    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text="Задать вопрос", payload="ask_question"))
    builder.row(CallbackButton(text="Обратная связь", payload="feedback"))
    
    await event.message.answer(text, attachments=[builder.as_markup()])

# Обработчики событий

@dp.message_created()
async def handle_message(event: MessageCreated):
    msg = event.message
    user_id = msg.sender.user_id
    
    text = msg.body.text.strip() if msg.body and msg.body.text else ""
    state = user_states.get(user_id)

    user = await sync_to_async(lambda: BotUser.objects.filter(max_user_id=user_id).first())()

    # 1 Регистрация пользователя
    if not user:
        if state == "waiting_group":
            entered_group = text.upper()
            group_exists = await sync_to_async(
                lambda: UniversityGroups.objects.filter(name=entered_group, is_active=True).exists()
            )()

            if group_exists:
                await register_max_user(user_id, 'student', group=entered_group)
                user_states[user_id] = "registered"
                faq = await get_faq_list('student')
                await event.message.answer(f"Группа {entered_group} найдена. Регистрация завершена!\n\n{faq}")
                await show_main_menu(event)
            else:
                await event.message.answer("Группа не найдена или неактивна. Попробуйте еще раз:")
            return

        builder = InlineKeyboardBuilder()
        builder.row(CallbackButton(text="Студент", payload="set_student"))
        builder.row(CallbackButton(text="Абитуриент", payload="set_applicant"))
        await event.message.answer("Здравствуй! Выбери, кто ты?:", attachments=[builder.as_markup()])
        return

    # 2 Обратная связь
    if state == "waiting_feedback":
        if len(text) < 10:
            await event.message.answer("Опишите проблему подробнее (минимум 10 символов).")
            return
        
        if any(bad_word in text.lower() for bad_word in BANNED_WORDS):
            await event.message.answer("Ваше сообщение содержит недопустимые слова. Попробуйте еще раз.")
            return

        await save_feedback(user_id, text)
        await event.message.answer("Спасибо! Отзыв отправлен администратору.")
        user_states[user_id] = "registered"
        await show_main_menu(event)
        return

    # 3 Поиск ответов
    if state == "waiting_question":
        response_data = await sync_to_async(find_answer_for_user)(text, user.role, user.group_number)
        await event.message.answer(response_data['answer'])
        
        if response_data.get('file'):
            await event.message.answer(attachments=[InputMedia(path=response_data['file'].path)])
            
        user_states[user_id] = "registered"
        await show_main_menu(event)
        return

    await show_main_menu(event)

@dp.message_callback()
async def handle_callbacks(event: MessageCallback):
    user_id = event.from_user.user_id
    data = event.callback.payload

    if data == "set_student":
        user_states[user_id] = "waiting_group"
        await event.message.answer("Введите номер вашей группы (напр. ИСТД-21):")
        
    elif data == "set_applicant":
        await register_max_user(user_id, 'applicant')
        user_states[user_id] = "registered"
        faq = await get_faq_list('applicant')
        await event.message.answer(f"Вы зарегистрированы как абитуриент!\n\n{faq}")
        await show_main_menu(event)
        
    elif data == "ask_question":
        user_states[user_id] = "waiting_question"
        await event.message.answer("Напишите ваш вопрос:")
        
    elif data == "feedback":
        user_states[user_id] = "waiting_feedback"
        await event.message.answer("Напишите ваше сообщение администратору:")

async def main():
    print("Бот MAX успешно запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")