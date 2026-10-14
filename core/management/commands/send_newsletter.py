"""ارسال خبرنامه به مشترکان فعال.

تا پیش از این دستور، ایمیل‌های خبرنامه فقط جمع می‌شدند و هیچ مسیری برای
ارسال وجود نداشت. ارسال از همان EMAIL_BACKEND تنظیمات انجام می‌شود
(کنسول در توسعه، SMTP در تولید) و هر ایمیل جداگانه فرستاده می‌شود تا
آدرس گیرندگان برای همدیگر فاش نشود.

مثال:
    python manage.py send_newsletter --subject "فایل‌های جدید" --text-file news.txt
    python manage.py send_newsletter --subject "تخفیف" --text "متن خبرنامه" --dry-run
"""
from pathlib import Path

from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand, CommandError

from core.models import NewsletterSubscriber


class Command(BaseCommand):
    help = 'ارسال یک خبرنامه به همهٔ مشترکان فعال خبرنامه'

    def add_arguments(self, parser):
        parser.add_argument('--subject', required=True, help='عنوان ایمیل')
        parser.add_argument('--text', default='', help='متن خبرنامه')
        parser.add_argument('--text-file', default='', help='مسیر فایل متن خبرنامه')
        parser.add_argument(
            '--dry-run', action='store_true',
            help='بدون ارسال واقعی، فقط تعداد گیرندگان را نشان بده',
        )

    def handle(self, *args, **options):
        body = options['text']
        if options['text_file']:
            path = Path(options['text_file'])
            if not path.is_file():
                raise CommandError(f'فایل متن خبرنامه پیدا نشد: {path}')
            body = path.read_text(encoding='utf-8')
        if not body.strip():
            raise CommandError('متن خبرنامه خالی است؛ --text یا --text-file بدهید.')

        recipients = list(
            NewsletterSubscriber.objects.filter(is_active=True)
            .values_list('email', flat=True)
        )
        if not recipients:
            self.stdout.write('هیچ مشترک فعالی وجود ندارد؛ چیزی ارسال نشد.')
            return

        if options['dry_run']:
            self.stdout.write(f'[dry-run] {len(recipients)} مشترک فعال؛ چیزی ارسال نشد.')
            return

        sent = 0
        failed = 0
        for email in recipients:
            message = EmailMessage(subject=options['subject'], body=body, to=[email])
            try:
                message.send(fail_silently=False)
                sent += 1
            except Exception:  # یک آدرس بد نباید ارسال به بقیه را متوقف کند
                failed += 1
                self.stderr.write(f'ارسال به {email} ناموفق بود.')
        self.stdout.write(f'خبرنامه ارسال شد: {sent} موفق، {failed} ناموفق.')
