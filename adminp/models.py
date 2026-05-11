import os
from django.db import models
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex
from django.db.models.signals import post_migrate
from django.dispatch import receiver

class UniversityGroups(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="Название группы")
    is_active = models.BooleanField(default=True, verbose_name="Активна")

    class Meta:
        verbose_name = "Учебные группы"
        verbose_name_plural = "Учебные группы"

    def __str__(self):
        return self.name

class KnowledgeBase(models.Model):
    question = models.CharField(max_length=255, verbose_name="Вопрос")
    answer = models.TextField(verbose_name="Ответ")
    file = models.FileField(upload_to='bot_files/', null=True, blank=True, verbose_name="Прикреплённый файл")
    target_groups = models.ManyToManyField(UniversityGroups, blank=True, verbose_name="Кому доступен вопрос", help_text="Выберите группы (в т.ч. 'Абитуриенты'). Если пусто — доступно всем.")
    search_vector = SearchVectorField(null=True, blank=True, editable=False)
    is_faq = models.BooleanField(default=False, verbose_name="Показывать в частых вопросах")
    
    class Meta:
        verbose_name = "Список вопросов"
        verbose_name_plural = "Список вопросов"
        indexes = [GinIndex(fields=['search_vector'])]
    def __str__(self):
        return self.question
    
class BotUser(models.Model):
    ROLE_CHOICES = [
        ('student', 'Студент'),
        ('applicant', 'Абитуриент'),
    ]

    max_user_id = models.CharField(max_length=100, unique=True, verbose_name="ID в MAX")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name="Роль")
    group_number = models.CharField(max_length=50, null=True, blank=True, verbose_name="Номер группы")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата регистрации")

    class Meta:
        verbose_name = "Пользователь MAX"
        verbose_name_plural = "Пользователи MAX"

    def __str__(self):
        return f"MAX ID: {self.max_user_id} ({self.get_role_display()})"
    
class Feedback(models.Model):
    user = models.ForeignKey('BotUser', on_delete=models.CASCADE, verbose_name="Пользователь")
    message = models.TextField(verbose_name="Сообщение от пользователя")
    admin_reply = models.TextField(null=True, blank=True, verbose_name="Ответ администратора")
    is_replied = models.BooleanField(default=False, verbose_name="Отвечено")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата отправки")
    replied_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата ответа")

    class Meta:
        verbose_name = "Обратная связь"
        verbose_name_plural = "Обратная связь"
    def __str__(self):
        return f"Отзыв от {self.user.max_user_id} ({self.created_at.strftime('%d.%m %H:%M')})"

@receiver(post_migrate)
def create_default_groups(sender, **kwargs):
    if sender.name == 'adminp':
        UniversityGroups.objects.get_or_create(name="Абитуриенты")