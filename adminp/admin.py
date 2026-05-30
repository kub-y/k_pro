import requests
from django.contrib import admin
from django.utils import timezone
from django.conf import settings
from django.contrib import messages
from django.db.models import Count
from .models import KnowledgeBase, BotUser, Feedback, UniversityGroups, MassNotification, UserQueryLog, BannedWord

@admin.register(KnowledgeBase)
class KnowledgeBaseAdmin(admin.ModelAdmin):
    list_display = ('faq_question', 'get_target_groups', 'is_faq', 'has_file')
    list_filter = ('is_faq', 'target_groups')
    search_fields = ('question', 'faq_question', 'answer')
    filter_horizontal = ('target_groups',)
    exclude = ('search_vector',)

    @admin.display(description='Доступно группам')
    def get_target_groups(self, obj):
        groups = obj.target_groups.all()
        if groups.exists():
            return ", ".join([g.name for g in groups])
        return "Все группы"

    @admin.display(boolean=True, description='Файл')
    def has_file(self, obj):
        return bool(obj.file)

    @admin.display(description='Текст ответа')
    def answer_short(self, obj):
        return obj.answer[:100] + "..." if len(obj.answer) > 100 else obj.answer
    
@admin.register(BotUser)
class BotUserAdmin(admin.ModelAdmin):
    list_display = ('max_user_id', 'group', 'created_at')
    list_filter = ('group',)
    search_fields = ('max_user_id', 'group')

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('user', 'message_short', 'is_replied', 'created_at')
    list_filter = ('is_replied', 'created_at')
    readonly_fields = ('user', 'message', 'created_at', 'replied_at')
    fields = ('user', 'message', 'admin_reply', 'created_at', 'replied_at')

    def message_short(self, obj):
        return obj.message[:50] + "..." if len(obj.message) > 50 else obj.message
    message_short.short_description = "Текст сообщения"

    def save_model(self, request, obj, form, change):
        if obj.admin_reply and not obj.is_replied:
            url = f"https://platform-api.max.ru/messages?user_id={obj.user.max_user_id}"
            payload = {
                "text": f"Ответ администратора на ваше сообщение:\n\n{obj.admin_reply}"
            }
            headers = {
                "Authorization": settings.MAX_BOT_TOKEN,
                "Content-Type": "application/json"
            }
            try:
                response = requests.post(url, json=payload, headers=headers)
                response.raise_for_status()
                obj.is_replied = True
                obj.replied_at = timezone.now()
                messages.success(request, f"Ответ успешно отправлен пользователю {obj.user.max_user_id}")
            except Exception as e:
                messages.error(request, f"Ошибка при отправке в MAX: {e}")
                obj.is_replied = False

        super().save_model(request, obj, form, change)

@admin.register(UniversityGroups)
class UniversityGroupsAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    search_fields = ('name',)
    list_filter = ('is_active',)

@admin.register(MassNotification)
class MassNotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_sent', 'created_at')
    filter_horizontal = ('target_groups',)
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        
        if not obj.is_sent:
            selected_groups = form.cleaned_data.get('target_groups')
            
            users = BotUser.objects.filter(group__in=selected_groups).distinct()
            
            if not users.exists():
                messages.warning(request, "Рассылка не отправлена: в выбранных группах нет зарегистрированных пользователей.")
                return

            headers = {
                "Authorization": settings.MAX_BOT_TOKEN,
                "Content-Type": "application/json"
            }
            
            success_count = 0
            failed_count = 0

            for user in users:
                user_url = f"https://platform-api.max.ru/messages?user_id={user.max_user_id}"
                payload = {
                    "text": f"**Важное оповещение:**\n\n{obj.text}"
                }
                
                try:
                    response = requests.post(user_url, json=payload, headers=headers, timeout=5)
                    response.raise_for_status()
                    success_count += 1
                except Exception as e:
                    failed_count += 1
                    print(f"Ошибка отправки пользователю {user.max_user_id}: {e}")

            obj.is_sent = True
            obj.save()

            if success_count > 0:
                messages.success(request, f"Рассылка успешно выполнена! Доставлено: {success_count} сообщений.")
            if failed_count > 0:
                messages.error(request, f"Не удалось доставить сообщения {failed_count} пользователям.")

@admin.register(UserQueryLog)
class UserQueryLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'query_text', 'get_faq_question', 'get_query_count', 'is_answered', 'created_at')
    list_filter = ('is_answered', 'created_at')
    search_fields = ('query_text', 'user__max_user_id', 'knowledge_base__faq_question')
    readonly_fields = ('user', 'query_text', 'knowledge_base', 'is_answered', 'created_at')

    def has_add_permission(self, request):
        return False

    @admin.display(description='Вопрос из списка частых')
    def get_faq_question(self, obj):
        if obj.knowledge_base:
            return obj.knowledge_base.faq_question
        return "— (Ответ не найден)"

    @admin.display(description='Повторений вопроса')
    def get_query_count(self, obj):
        return getattr(obj, 'similar_queries_count', 0)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        
        queryset = queryset.select_related('knowledge_base', 'user').annotate(
            similar_queries_count=Count('knowledge_base__userquerylog')
        )
        return queryset
    
@admin.register(BannedWord)
class BannedWordAdmin(admin.ModelAdmin):
    list_display = ('word',)
    search_fields = ('word',)