from django.db.models import Q
from django.contrib.postgres.search import SearchQuery, SearchRank
from .models import Feedback, BotUser, KnowledgeBase, UniversityGroups, UserQueryLog

async def find_answer_for_user(user_query, user_id, user_group_name=None):
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

    best_match = await results.afirst()
    is_answered = bool(best_match)

    user_obj = await BotUser.objects.aget(max_user_id=user_id)
    await UserQueryLog.objects.acreate(user=user_obj, query_text=user_query, is_answered=is_answered, knowledge_base=best_match if is_answered else None)

    if best_match:
        return {
            "answer": best_match.answer,
            "file": best_match.file if (best_match.file and best_match.file.name) else None
        }
    return {"answer":"К сожалению, я не нашёл ответ на ваш вопрос.", "file": None}

async def register_max_user(user_id, group_name):
    group_obj = await UniversityGroups.objects.filter(name=group_name).afirst()
    user, created = await BotUser.objects.aget_or_create(
        max_user_id=user_id,
        defaults={'group': group_obj}
    )
    if not created and user.group != group_obj:
        user.group = group_obj
        await user.asave(update_fields=['group'])
    return user

async def save_feedback(user_max_id, text):
    try:
        user = await BotUser.objects.aget(max_user_id=user_max_id)
        return await Feedback.objects.acreate(user=user, message=text)
    except BotUser.DoesNotExist:
        return None

async def get_faq_list(user_group_name):  
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

    faqs_list = [item async for item in faqs.order_by('faq_question')[:5]]
    
    if not faqs_list:
        return "Список часто задаваемых вопросов пока пуст."
    
    text = header
    for idx, item in enumerate(faqs_list, 1):
        text += f"{idx}. {item.faq_question}\n"
    
    text += "\nЧтобы получить ответ, нажмите 'Задать вопрос' и напишите его в чат."
    return text