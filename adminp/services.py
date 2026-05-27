from django.db.models import Q
from django.contrib.postgres.search import SearchQuery, SearchRank
from asgiref.sync import sync_to_async
from .models import Feedback, BotUser, KnowledgeBase, UniversityGroups, UserQueryLog

@sync_to_async
def find_answer_for_user(user_query, user_id, user_group_name=None):
    query = SearchQuery(user_query, config='russian', search_type='websearch')
    if user_group_name == "Абитуриенты":
        group_filter = Q(target_groups__name="Абитуриенты")
    else:
        group_filter = Q(target_groups__isnull=True) | Q(target_groups__name=user_group_name)
    results = KnowledgeBase.objects.annotate(
        rank=SearchRank('search_vector', query)
    ).filter(
        group_filter
    ).filter(rank__gte=0.01).order_by('-rank').distinct()

    is_answered = False
    best_match = results.first()
    if best_match:
        is_answered = True
    if not is_answered:
        user_obj = BotUser.objects.get(max_user_id=user_id)
        UserQueryLog.objects.create(user=user_obj, query_text=user_query, is_answered=False)

    if best_match:
        return {
            "answer": best_match.answer,
            "file": best_match.file if (best_match.file and best_match.file.name) else None
        }
    return {"answer":"К сожалению, я не нашёл ответ на ваш вопрос.", "file": None}

@sync_to_async
def register_max_user(user_id, group_name):
    group_obj = UniversityGroups.objects.filter(name=group_name).first()
    user, created = BotUser.objects.update_or_create(
        max_user_id=user_id,
        defaults={'group': group_obj}
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
            Q(target_groups__name=user_group_name) | Q(target_groups__isnull=True),
            is_faq=True
        ).distinct()
        header = "**Список частых вопросов для студентов:**\n\n"

    faqs_list = list(faqs.order_by('question')[:5])
    
    if not faqs_list:
        return "Список часто задаваемых вопросов пока пуст."
    
    text = header
    for idx, item in enumerate(faqs_list, 1):
        text += f"{idx}. {item.question}\n"
    
    text += "\nЧтобы получить ответ, нажмите 'Задать вопрос' и напишите его в чат."
    return text