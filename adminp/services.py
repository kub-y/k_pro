from django.db.models import Q
from django.contrib.postgres.search import SearchQuery, SearchRank
from asgiref.sync import sync_to_async
from .models import Feedback, BotUser, KnowledgeBase

@sync_to_async
def find_answer_for_user(user_query, user_group=None):
    query = SearchQuery(user_query, config='russian')
    if user_group == "Абитуриенты":
        group_filter = Q(target_groups__name="Абитуриенты")
    else:
        group_filter = Q(target_groups__isnull=True) | Q(target_groups__name=user_group)
    results = KnowledgeBase.objects.annotate(
        rank=SearchRank('search_vector', query)
    ).filter(
        group_filter
    ).filter(rank__gte=0.01).order_by('-rank').distinct()

    best_match = results.first()
    if best_match:
        return {
            "answer": best_match.answer,
            "file": best_match.file if best_match.file else None
        }
    return {"answer":"К сожалению, я не нашёл ответ на ваш вопрос.", "file": None}

@sync_to_async
def register_max_user(user_id, role, group=None):

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
def get_faq_list(user_group_name):
    
    if user_group_name == "Абитуриенты":
        faqs = KnowledgeBase.objects.filter(
            target_groups__name="Абитуриенты",
            is_faq=True
        ).distinct()
        header = "**Список частых вопросов для абитуриентов:**\n\n"
    else:
        faqs = KnowledgeBase.objects.filter(
            target_groups__isnull=True,
            is_faq=True
        ).distinct()
        header = "**Список частых вопросов для студентов:**\n\n"

    faqs = faqs.order_by('question')[:5]
    
    if not faqs.exists():
        return "Список часто задаваемых вопросов пока пуст."
    
    text = header
    for idx, item in enumerate(faqs, 1):
        text += f"{idx}. {item.question}\n"
    
    text += "\nЧтобы получить ответ, нажмите 'Задать вопрос' и напишите его в чат."
    return text