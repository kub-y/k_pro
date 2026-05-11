import requests
from django.contrib import admin
from django.utils import timezone
from django.conf import settings
from django.contrib import messages
from .models import KnowledgeBase
from .models import BotUser
from .models import Feedback
from .models import UniversityGroups

@admin.register(KnowledgeBase)
class KnowledgeBaseAdmin(admin.ModelAdmin):
    list_display = ('question', 'visibility', 'target_groups', 'has_file')
    list_filter = ('visibility',)
    search_fields = ('question', 'answer', 'target_groups')
    exclude = ('search_vector',)

    @admin.display(boolean=True, description='Файл')
    def has_file(self, obj):
        return bool(obj.file)

    @admin.display(description='Текст ответа')
    def answer_short(self, obj):
        return obj.answer[:100] + "..." if len(obj.answer) > 100 else obj.answer
@admin.register(BotUser)
class BotUserAdmin(admin.ModelAdmin):
    list_display = ('max_user_id', 'role', 'group_number', 'created_at')
    list_filter = ('role',)
    search_fields = ('max_user_id', 'group_number')

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('user', 'message_short', 'is_replied', 'created_at')
    list_filter = ('is_replied', 'created_at')
    readonly_fields = ('user', 'message', 'created_at', 'replied_at')
    fields = ('user', 'message', 'admin_reply', 'is_replied', 'created_at', 'replied_at')

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