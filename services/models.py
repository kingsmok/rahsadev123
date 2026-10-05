from django.db import models


class ServicePackage(models.Model):
    """پکیج‌های طراحی وب سایت (تعرفه‌ها)."""
    title = models.CharField(max_length=120, verbose_name='عنوان پکیج')
    subtitle = models.CharField(max_length=200, blank=True, verbose_name='توضیح کوتاه')
    price = models.PositiveBigIntegerField(null=True, blank=True, verbose_name='قیمت (تومان)',
                                           help_text='خالی بگذارید تا «استعلام قیمت» نمایش داده شود')
    delivery_days = models.PositiveIntegerField(default=14, verbose_name='مدت تحویل (روز)')
    revisions = models.PositiveIntegerField(default=2, verbose_name='تعداد بازنگری')
    features = models.TextField(verbose_name='امکانات پکیج', help_text='هر خط یک مورد')
    is_featured = models.BooleanField(default=False, verbose_name='پیشنهاد ویژه')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    order = models.PositiveIntegerField(default=0, verbose_name='ترتیب نمایش')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')

    class Meta:
        verbose_name = 'پکیج طراحی سایت'
        verbose_name_plural = 'پکیج‌های طراحی سایت'
        ordering = ['order', 'id']

    @property
    def features_list(self):
        return [line.strip() for line in self.features.splitlines() if line.strip()]

    def __str__(self):
        return self.title


class PortfolioItem(models.Model):
    """نمونه کارهای طراحی وب سایت."""
    title = models.CharField(max_length=150, verbose_name='عنوان پروژه')
    image = models.ImageField(upload_to='images/portfolio/', verbose_name='تصویر نمونه کار')
    url = models.URLField(blank=True, verbose_name='آدرس سایت')
    category = models.CharField(max_length=100, blank=True, verbose_name='دسته (شرکتی، فروشگاهی، ...)')
    description = models.TextField(blank=True, verbose_name='توضیحات')
    order = models.PositiveIntegerField(default=0, verbose_name='ترتیب نمایش')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')

    class Meta:
        verbose_name = 'نمونه کار'
        verbose_name_plural = 'نمونه کارها'
        ordering = ['order', '-id']

    def __str__(self):
        return self.title


class ServiceRequest(models.Model):
    """درخواست مشاوره / سفارش طراحی سایت."""
    REQUEST_STATUS = (
        ('new', 'جدید'),
        ('contacted', 'تماس گرفته شد'),
        ('in_progress', 'در حال بررسی'),
        ('done', 'پایان یافته'),
        ('cancelled', 'لغو شده'),
    )

    full_name = models.CharField(max_length=120, verbose_name='نام و نام خانوادگی')
    phone = models.CharField(max_length=14, verbose_name='شماره تماس')
    email = models.EmailField(blank=True, verbose_name='ایمیل')
    package = models.ForeignKey(ServicePackage, null=True, blank=True, on_delete=models.SET_NULL,
                                verbose_name='پکیج انتخابی')
    project_type = models.CharField(max_length=150, blank=True, verbose_name='نوع پروژه')
    budget = models.CharField(max_length=100, blank=True, verbose_name='بودجه تقریبی')
    message = models.TextField(verbose_name='توضیحات پروژه')
    status = models.CharField(max_length=20, choices=REQUEST_STATUS, default='new', verbose_name='وضعیت')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ درخواست')

    class Meta:
        verbose_name = 'درخواست طراحی سایت'
        verbose_name_plural = 'درخواست‌های طراحی سایت'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.full_name} - {self.project_type or self.package or "درخواست مشاوره"}'
