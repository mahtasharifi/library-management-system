"""Persistent domain models for the Library."""

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from common.i18n import translate as t


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name=t("books.category.field.name"))
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="children", verbose_name=t("books.category.field.parent"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "book_categories"
        verbose_name = t("books.category.model.single")
        verbose_name_plural = t("books.category.model.plural")
        ordering = ["name"]

    def __str__(self):
        full_path = [self.name]
        parent = self.parent
        visited = {self.pk}
        while parent is not None and parent.pk not in visited:
            visited.add(parent.pk)
            full_path.append(parent.name)
            parent = parent.parent
        return " -> ".join(reversed(full_path))


class Book(models.Model):
    title = models.CharField(max_length=255, verbose_name=t("books.book.field.title"))
    author = models.CharField(max_length=255, verbose_name=t("common.labels.author"))
    translator = models.CharField(max_length=255, blank=True, null=True, verbose_name=t("common.labels.translator"))
    publisher = models.CharField(max_length=255, blank=True, null=True, verbose_name=t("common.labels.publisher"))
    library = models.CharField(max_length=255, blank=True, null=True, verbose_name=t("books.book.field.library"))
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=t("books.category.model.single"))
    nbok_category = models.ForeignKey(
        "NBOKEntry", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="books", verbose_name=t("books.category.model.single"),
        db_constraint=False,
    )
    nbok_category_level = models.CharField(max_length=2, blank=True, null=True)
    summary = models.TextField(blank=True, null=True, verbose_name=t("books.book.field.summary"))
    cover_url = models.URLField(max_length=1000, blank=True, null=True, verbose_name=t("books.book.field.cover_url"))
    pdf_url = models.URLField(max_length=1000, blank=True, null=True, verbose_name=t("books.book.field.pdf_url"))
    tags = models.JSONField(default=list, blank=True, verbose_name=t("books.book.field.tags"))
    physical_count = models.PositiveIntegerField(default=0, verbose_name=t("books.book.field.physical_count"))
    physical_available = models.PositiveIntegerField(default=0, verbose_name=t("books.book.field.physical_available"))
    physical_location = models.CharField(max_length=200, blank=True, null=True, verbose_name=t("books.book.field.physical_location"))
    request_count = models.PositiveIntegerField(default=0, verbose_name=t("books.book.field.request_count"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=t("common.labels.created_at"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=t("common.labels.updated_at"))

    class Meta:
        db_table = "books"
        verbose_name = t("books.book.model.single")
        verbose_name_plural = t("books.book.model.plural")
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(physical_available__lte=models.F("physical_count")),
                name="book_available_not_above_total",
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def cover(self):
        return self.cover_url

    @property
    def download_link(self):
        # Never expose a direct storage URL from the domain model.
        return None

    @property
    def display_category_name(self):
        """Return the NBOK category selected for the book, with legacy fallback."""
        level = str(self.nbok_category_level or "").upper()
        if level in {"L1", "L2", "L3", "L4", "L5", "L6"} and self.nbok_category_id:
            try:
                entry = self.nbok_category
            except ObjectDoesNotExist:
                entry = None
            if entry is not None:
                value = getattr(entry, level.lower(), None)
                if value:
                    return str(value).strip()
        try:
            legacy = self.category
        except ObjectDoesNotExist:
            legacy = None
        return legacy.name if legacy else ""

    @property
    def display_category_path(self):
        """Return the selected NBOK hierarchy as human-readable text."""
        level = str(self.nbok_category_level or "").upper()
        levels = ("L1", "L2", "L3", "L4", "L5", "L6")
        if level in levels and self.nbok_category_id:
            try:
                entry = self.nbok_category
            except ObjectDoesNotExist:
                entry = None
            if entry is not None:
                values = []
                for current in levels[: levels.index(level) + 1]:
                    value = getattr(entry, current.lower(), None)
                    if value and str(value).strip():
                        values.append(str(value).strip())
                if values:
                    return " / ".join(values)
        try:
            legacy = self.category
        except ObjectDoesNotExist:
            legacy = None
        return str(legacy) if legacy else ""

    @property
    def has_pdf(self):
        return bool(self.pdf_url)

    @property
    def has_physical(self):
        return self.physical_count > 0

    def get_current_borrower(self):
        current_borrow = self.borrows.filter(is_returned=False).first()
        return current_borrow.borrower_name if current_borrow else None

    def get_borrow_history(self):
        return self.borrows.all().order_by("-borrow_date")


class PhysicalBookBorrow(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="borrows", verbose_name=t("books.book.model.single"))
    borrower_name = models.CharField(max_length=200, verbose_name=t("books.borrow.field.borrower_name"))
    borrower_email = models.EmailField(verbose_name=t("books.borrow.field.borrower_email"))
    borrower_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name=t("common.labels.phone"))
    borrow_date = models.DateField(verbose_name=t("books.borrow.field.borrow_date"))
    return_date = models.DateField(verbose_name=t("books.borrow.field.return_date"))
    actual_return_date = models.DateField(blank=True, null=True, verbose_name=t("books.borrow.field.actual_return_date"))
    notes = models.TextField(blank=True, null=True, verbose_name=t("books.borrow.field.notes"))
    is_returned = models.BooleanField(default=False, verbose_name=t("books.borrow.field.is_returned"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=t("common.labels.created_date"))

    class Meta:
        db_table = "physical_book_borrows"
        verbose_name = t("books.borrow.model.single")
        verbose_name_plural = t("books.borrow.model.plural")
        ordering = ["-borrow_date"]
        constraints = [
            models.CheckConstraint(condition=models.Q(return_date__gte=models.F("borrow_date")), name="borrow_return_not_before_borrow"),
        ]

    def __str__(self):
        return f"{self.book.title} - {self.borrower_name}"

    @property
    def is_overdue(self):
        return not self.is_returned and timezone.now().date() > self.return_date


class PhysicalBookRequest(models.Model):
    STATUS_CHOICES = [("pending", t("books.request.status.pending")), ("approved", t("books.request.status.approved")), ("rejected", t("books.request.status.rejected"))]

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="physical_requests", verbose_name=t("books.book.model.single"))
    name = models.CharField(max_length=200, verbose_name=t("common.labels.name"))
    email = models.EmailField(verbose_name=t("common.labels.email"))
    phone = models.CharField(max_length=20, verbose_name=t("common.labels.phone"))
    message = models.TextField(blank=True, null=True, verbose_name=t("common.labels.message"))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name=t("common.labels.status"))
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="physical_book_requests", verbose_name=t("common.labels.user"))
    admin_read_at = models.DateTimeField(blank=True, null=True, verbose_name=t("books.request.field.admin_read_at"))
    admin_response = models.TextField(blank=True, null=True, verbose_name=t("books.request.field.admin_response"))
    responded_at = models.DateTimeField(blank=True, null=True, verbose_name=t("books.request.field.responded_at"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=t("common.labels.request_date"))

    class Meta:
        db_table = "physical_book_requests"
        verbose_name = t("books.physical_request.model.single")
        verbose_name_plural = t("books.physical_request.model.plural")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "admin_read_at", "-created_at"], name="physical_req_queue_idx")]
        constraints = [models.CheckConstraint(condition=models.Q(status__in=["pending", "approved", "rejected"]), name="physical_request_valid_status")]

    def __str__(self):
        return f"{self.book.title} - {self.name}"


class BookRequest(models.Model):
    STATUS_CHOICES = [("pending", t("books.request.status.pending")), ("approved", t("books.request.status.approved")), ("rejected", t("books.request.status.rejected"))]

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="requests", null=True, blank=True)
    name = models.CharField(max_length=200, blank=True, null=True, verbose_name=t("common.labels.name"))
    email = models.EmailField()
    message = models.TextField(blank=True, null=True, verbose_name=t("common.labels.message"))
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="digital_book_requests", verbose_name=t("common.labels.user"))
    admin_read_at = models.DateTimeField(blank=True, null=True, verbose_name=t("books.request.field.admin_read_at"))
    admin_response = models.TextField(blank=True, null=True, verbose_name=t("books.request.field.admin_response"))
    responded_at = models.DateTimeField(blank=True, null=True, verbose_name=t("books.request.field.responded_at"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "digital_book_requests"
        verbose_name = t("books.digital_request.model.single")
        verbose_name_plural = t("books.digital_request.model.plural")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "admin_read_at", "-created_at"], name="digital_req_queue_idx")]
        constraints = [models.CheckConstraint(condition=models.Q(status__in=["pending", "approved", "rejected"]), name="digital_request_valid_status")]

    def __str__(self):
        return f"{self.email} - {self.book.title if self.book else t('books.digital_request.new_book')} - {self.status}"


class Message(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True, verbose_name=t("common.labels.name"))
    email = models.EmailField(blank=True, null=True, verbose_name=t("common.labels.email"))
    message = models.TextField(verbose_name=t("common.labels.message"))
    is_read = models.BooleanField(default=False, verbose_name=t("books.message.field.is_read"))
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="library_messages", verbose_name=t("common.labels.user"))
    admin_read_at = models.DateTimeField(blank=True, null=True, verbose_name=t("books.request.field.admin_read_at"))
    admin_response = models.TextField(blank=True, null=True, verbose_name=t("books.request.field.admin_response"))
    responded_at = models.DateTimeField(blank=True, null=True, verbose_name=t("books.request.field.responded_at"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=t("common.labels.sent_date"))

    class Meta:
        db_table = "library_messages"
        verbose_name = t("common.labels.message")
        verbose_name_plural = t("books.message.model.plural")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["is_read", "-created_at"], name="message_unread_idx")]

    def __str__(self):
        return t("books.message.display", name=self.name or t("books.message.unknown_sender"))


class Question(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, verbose_name=t("books.book.model.single"))
    question = models.TextField(verbose_name=t("books.question.field.question"))
    answer = models.TextField(blank=True, null=True, verbose_name=t("books.question.field.answer"))
    is_approved = models.BooleanField(default=False, verbose_name=t("books.question.field.is_approved"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=t("books.question.field.created_at"))
    answered_at = models.DateTimeField(blank=True, null=True, verbose_name=t("books.question.field.answered_at"))

    class Meta:
        db_table = "book_questions"
        verbose_name = t("books.question.field.question")
        verbose_name_plural = t("books.question.model.plural")
        ordering = ["-created_at"]

    def __str__(self):
        return t("books.question.display", book=self.book.title)


class BookComment(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="comments", verbose_name=t("books.book.model.single"))
    name = models.CharField(max_length=200, verbose_name=t("common.labels.name"))
    email = models.EmailField(verbose_name=t("common.labels.email"))
    comment = models.TextField(verbose_name=t("books.comment.field.comment"))
    parent = models.ForeignKey("self", on_delete=models.CASCADE, blank=True, null=True, related_name="replies", verbose_name=t("books.comment.field.parent"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=t("common.labels.created_at"))
    is_approved = models.BooleanField(default=True, verbose_name=t("books.comment.field.is_approved"))

    class Meta:
        db_table = "book_comments"
        verbose_name = t("books.comment.model.single")
        verbose_name_plural = t("books.comment.model.plural")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.book.title} - {self.name}"


class BookRating(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="ratings", verbose_name=t("books.book.model.single"))
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="book_ratings", null=True, blank=True, verbose_name=t("common.labels.user"))
    user_ip = models.GenericIPAddressField(blank=True, null=True, verbose_name=t("books.rating.field.ip"))
    rating = models.PositiveSmallIntegerField(
        choices=[(i, i) for i in range(1, 6)], validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name=t("books.rating.field.rating"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=t("common.labels.created_at"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=t("common.labels.updated_at"))

    class Meta:
        db_table = "book_ratings"
        verbose_name = t("books.rating.model.single")
        verbose_name_plural = t("books.rating.model.plural")
        constraints = [
            models.UniqueConstraint(fields=["book", "user"], name="unique_user_book_rating"),
            models.CheckConstraint(condition=models.Q(rating__gte=1, rating__lte=5), name="book_rating_between_1_and_5"),
        ]

    def __str__(self):
        return t("books.rating.display", book=self.book.title, rating=self.rating)


class UserNotification(models.Model):
    KIND_CHOICES = [
        ("read", t("books.notification.kind.read")), ("answered", t("books.notification.kind.answered")), ("approved", t("books.notification.kind.approved")),
        ("rejected", t("books.notification.kind.rejected")), ("info", t("books.notification.kind.info")),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="library_notifications", verbose_name=t("common.labels.user"))
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="info", verbose_name=t("books.notification.field.kind"))
    title = models.CharField(max_length=200, verbose_name=t("books.book.field.title"))
    message = models.TextField(verbose_name=t("books.notification.field.message"))
    related_type = models.CharField(max_length=40, blank=True, verbose_name=t("books.notification.field.related_type"))
    related_id = models.PositiveBigIntegerField(blank=True, null=True, verbose_name=t("books.notification.field.related_id"))
    is_read = models.BooleanField(default=False, verbose_name=t("books.notification.field.is_read"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=t("common.labels.created_at"))

    class Meta:
        db_table = "user_notifications"
        verbose_name = t("books.notification.model.single")
        verbose_name_plural = t("books.notification.model.plural")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "is_read", "-created_at"], name="user_notification_idx")]

    def __str__(self):
        return f"{self.user} - {self.title}"


class NBOKEntry(models.Model):
    """Hierarchical NBOK taxonomy imported from the source workbook."""

    l1 = models.CharField("L1", db_column="L1", max_length=255, blank=True, null=True)
    l2 = models.CharField("L2", db_column="L2", max_length=255, blank=True, null=True)
    l3 = models.CharField("L3", db_column="L3", max_length=255, blank=True, null=True)
    l4 = models.CharField("L4", db_column="L4", max_length=255, blank=True, null=True)
    l5 = models.CharField("L5", db_column="L5", max_length=255, blank=True, null=True)
    l6 = models.CharField("L6", db_column="L6", max_length=255, blank=True, null=True)
    k1 = models.TextField("K1", db_column="K1", blank=True, null=True)

    class Meta:
        db_table = "nbok"
        ordering = ["id"]

    def __str__(self):
        return self.k1 or self.l6 or self.l5 or self.l4 or self.l3 or self.l2 or self.l1 or f"NBOK #{self.pk}"


class BackgroundJob(models.Model):
    """Durable asynchronous work queued inside the transactional application database."""

    TYPE_EMAIL = "email"
    TYPE_PHYSICAL_IMPORT = "physical_import"
    TYPE_CHOICES = [
        (TYPE_EMAIL, t("books.jobs.type.email")),
        (TYPE_PHYSICAL_IMPORT, t("books.jobs.type.physical_import")),
    ]
    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_QUEUED, t("books.jobs.status.queued")),
        (STATUS_RUNNING, t("books.jobs.status.running")),
        (STATUS_COMPLETED, t("books.jobs.status.completed")),
        (STATUS_FAILED, t("books.jobs.status.failed")),
    ]

    job_type = models.CharField(max_length=40, choices=TYPE_CHOICES)
    payload = models.JSONField(default=dict)
    result = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)
    available_at = models.DateTimeField(default=timezone.now)
    locked_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    last_error_code = models.CharField(max_length=100, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="library_background_jobs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "background_jobs"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["status", "available_at", "created_at"], name="background_job_queue_idx"),
            models.Index(fields=["job_type", "status", "-created_at"], name="background_job_type_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["queued", "running", "completed", "failed"]),
                name="background_job_valid_status",
            ),
            models.CheckConstraint(condition=models.Q(max_attempts__gte=1), name="background_job_attempts_positive"),
        ]

    def __str__(self):
        return f"{self.job_type}:{self.pk}:{self.status}"


class TaskWorkerHeartbeat(models.Model):
    """Last-seen timestamps for task workers, used by readiness checks and operators."""

    worker_name = models.CharField(max_length=100, unique=True)
    seen_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "task_worker_heartbeats"
        ordering = ["worker_name"]

    def __str__(self):
        return f"{self.worker_name}@{self.seen_at.isoformat()}"
