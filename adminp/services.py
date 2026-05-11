from django.db.models import Q
from django.contrib.postgres.search import SearchQuery, SearchRank
from asgiref.sync import sync_to_async
from .models import Feedback
from .models import BotUser
from .models import KnowledgeBase

def find_answer_for_user(user_query, user_role, user_group=None):
    query = SearchQuery(user_query, config='russian')
    results = KnowledgeBase.objects.annotate(
        rank=SearchRank('search_vector', query)
    ).filter(
        Q(visibility='all') | Q(visibility=user_role)
    ).filter(rank__gte=0.01).order_by('-rank')

    final_result = None
    for item in results.order_by('-rank'):
        if item.visibility != 'student' or not item.target_groups:
            final_result = item
            break
            
        if user_group:
            allowed_groups = [g.strip() for g in item.target_groups.split(',')]
            if user_group.strip() in allowed_groups:
                final_result = item
                break

    if final_result:
        return {
            "answer": final_result.answer,
            "file": final_result.file if final_result.file else None
        }
    return {"answer":"К сожалению, я не нашёл ответ на ваш вопрос.", "file": None}

@sync_to_async
def register_max_user(user_id, role, group=None):
    """
    Создаём или обновляем профиль пользователя мессенджера MAX
    """
    user, created = BotUser.objects.update_or_create(
        max_user_id=user_id,
        defaults={
            'role': role,
            'group_number': group if role == 'student' else None
        }
    )
    return user

@sync_to_async
def save_feedback(user_max_id, text):
    try:
        user = BotUser.objects.get(max_user_id=user_max_id)
        return Feedback.objects.create(user=user, message=text)
    except BotUser.DoesNotExist:
        return None

@sync_to_async
def get_faq_list(user_role):
    
    faqs = KnowledgeBase.objects.filter(
        Q(visibility='all') | Q(visibility=user_role),
        is_faq=True
    ).order_by('question')[:5]
    
    if not faqs.exists():
        return "Список часто задаваемых вопросов пока пуст."
    
    role_name = "студентов" if user_role == 'student' else "абитуриентов"
    text = f"**Список частых вопросов для {role_name}:**\n\n"

    for idx, item in enumerate(faqs, 1):
        text += f"{idx}. {item.question}\n"
    
    text += "\nЧтобы получить ответ, нажмите 'Задать вопрос' и напишите его в чат."
    return text