from django.db import models
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex
from django.db.models.signals import post_migrate
from django.dispatch import receiver

class UniversityGroups(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="Название группы")
    is_active = models.BooleanField(default=True, verbose_name="Активна")

    class Meta:
        verbose_name = "Учебную группу"
        verbose_name_plural = "5.Учебные группы"

    def __str__(self):
        return self.name

class KnowledgeBase(models.Model):
    faq_question = models.CharField(max_length=255, verbose_name="Вопрос")
    question = models.TextField(verbose_name="Расширенный вопрос")
    answer = models.TextField(verbose_name="Ответ")
    file = models.FileField(upload_to='bot_files/', null=True, blank=True, verbose_name="Прикреплённый файл")
    target_groups = models.ManyToManyField(UniversityGroups, blank=True, verbose_name="Кому доступен вопрос", help_text="Выберите группы (в т.ч. 'Абитуриенты'). Если пусто — доступно всем.")
    search_vector = SearchVectorField(null=True, blank=True, editable=False)
    is_faq = models.BooleanField(default=False, verbose_name="Показывать в частых вопросах")
    
    class Meta:
        verbose_name = "Вопрос"
        verbose_name_plural = "3.Список вопросов"
        indexes = [GinIndex(fields=['search_vector'])]
    def __str__(self):
        return self.question
    
class BotUser(models.Model):
    max_user_id = models.CharField(max_length=100, unique=True, verbose_name="ID в MAX")
    group = models.ForeignKey('UniversityGroups', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Группа", related_name="users")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата регистрации")

    class Meta:
        verbose_name = "Пользователя MAX"
        verbose_name_plural = "4.Пользователи MAX"

    def __str__(self):
        group_name = self.group.name if self.group else "Без группы"
        return f"MAX ID: {self.max_user_id} ({group_name})"
    
class Feedback(models.Model):
    user = models.ForeignKey('BotUser', on_delete=models.CASCADE, verbose_name="Пользователь")
    message = models.TextField(verbose_name="Сообщение от пользователя")
    admin_reply = models.TextField(null=True, blank=True, verbose_name="Ответ администратора")
    is_replied = models.BooleanField(default=False, editable=False, verbose_name="Отвечено")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата отправки")
    replied_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата ответа")

    class Meta:
        verbose_name = "Заявку"
        verbose_name_plural = "1.Обратная связь"
    def __str__(self):
        return f"Отзыв от {self.user.max_user_id} ({self.created_at.strftime('%d.%m %H:%M')})"

class MassNotification(models.Model):
    title = models.CharField(max_length=255, verbose_name="Тема/Название рассылки")
    text = models.TextField(verbose_name="Текст сообщения")   
    target_groups = models.ManyToManyField('UniversityGroups', verbose_name="Группы для рассылки", help_text="Сообщение получат все пользователи, состоящие в выбранных группах")
    is_sent = models.BooleanField(default=False, editable=False, verbose_name="Отправлено")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Рассылку"
        verbose_name_plural = "2.Массовые рассылки"

    def __str__(self):
        return f"{self.title} ({self.created_at.strftime('%d.%m.%Y %H:%M')})"
    
class UserQueryLog(models.Model):
    user = models.ForeignKey('BotUser', on_delete=models.CASCADE, verbose_name="Пользователь")
    query_text = models.CharField(max_length=255, verbose_name="Текст запроса")
    knowledge_base = models.ForeignKey('KnowledgeBase', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Найденный ответ")
    is_answered = models.BooleanField(default=False, verbose_name="Ответ найден")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата запроса")

    class Meta:
        verbose_name = "Лог запроса"
        verbose_name_plural = "7.Логи запросов"

    def __str__(self):
        status = "Отвечено" if self.is_answered else "Не отвечено"
        return f"{self.user.max_user_id}: {self.query_text[:30]}... ({status})"

class BannedWord(models.Model):
    word = models.CharField("Запрещенное слово", max_length=100, unique=True, help_text="Вносите слова в нижнем регистре и в начальной форме")
    created_at = models.DateTimeField("Дата добавления", auto_now_add=True)

    class Meta:
        verbose_name = "Запрещенное слово"
        verbose_name_plural = "6.Запрещенные слова"
        ordering = ['word']

    def __str__(self):
        return self.word

    def save(self, *args, **kwargs):
        self.word = self.word.strip().lower()
        super().save(*args, **kwargs)

@receiver(post_migrate)
def create_default_groups(sender, **kwargs):
    if sender.name == 'adminp':
        UniversityGroups.objects.get_or_create(name="Абитуриенты")