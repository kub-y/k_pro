import openpyxl
from django.core.management.base import BaseCommand
from adminp.models import KnowledgeBase, UniversityGroups

class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str)

    def handle(self, *args, **options):
        file_path = options['file_path']
        
        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            sheet = wb.active
            
            rows = sheet.iter_rows(min_row=2, values_only=True)
            created_count = 0
            
            for row in rows:
                if not row or row[0] is None:
                    continue
                
                faq_question_val = str(row[0]).strip()[:255]
                question_val = str(row[1]).strip() if row[1] is not None else ""
                answer_val = str(row[2]).strip() if row[2] is not None else ""
                groups_string = row[3]
                file_val = row[4]
                
                is_faq_raw = row[5] if len(row) > 5 else False
                is_faq_val = bool(is_faq_raw) if is_faq_raw not in ["Ложь", "false", "False", 0, "0", None] else False

                kb_entry = KnowledgeBase.objects.create(
                    faq_question=faq_question_val,
                    question=question_val,
                    answer=answer_val,
                    file=file_val,
                    is_faq=is_faq_val
                )
                
                if groups_string:
                    group_names = [g.strip() for g in str(groups_string).split(',') if g.strip()]
                    
                    for name in group_names:
                        group, created = UniversityGroups.objects.get_or_create(name=name)
                        kb_entry.target_groups.add(group)
                
                created_count += 1
            
            self.stdout.write(self.style.SUCCESS(f"Импорт успешно завершен! Создано записей: {created_count}"))
            
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"Файл не найден по пути: {file_path}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Произошла непредвиденная ошибка: {e}"))