from django.contrib import admin

from .models import (
    Book, BookComment, BookRequest, Category, Message,
    PhysicalBookBorrow, PhysicalBookRequest, UserNotification,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'created_at']
    search_fields = ['name']
    list_filter = ['created_at']


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'category', 'physical_count', 'physical_available', 'created_at']
    list_filter = ['category', 'created_at']
    search_fields = ['title', 'author', 'translator', 'publisher']
    readonly_fields = ['created_at', 'updated_at', 'request_count']


@admin.register(BookRequest)
class BookRequestAdmin(admin.ModelAdmin):
    list_display = ['book', 'email', 'status', 'admin_read_at', 'responded_at', 'created_at']
    list_filter = ['status', 'admin_read_at', 'responded_at']
    search_fields = ['book__title', 'email', 'name']
    readonly_fields = ['created_at']


@admin.register(PhysicalBookRequest)
class PhysicalBookRequestAdmin(admin.ModelAdmin):
    list_display = ['book', 'name', 'status', 'admin_read_at', 'responded_at', 'created_at']
    list_filter = ['status', 'admin_read_at', 'responded_at']
    search_fields = ['book__title', 'name', 'email', 'phone']


@admin.register(PhysicalBookBorrow)
class PhysicalBookBorrowAdmin(admin.ModelAdmin):
    list_display = ['book', 'borrower_name', 'borrow_date', 'return_date', 'is_returned']
    list_filter = ['is_returned', 'borrow_date', 'return_date']
    search_fields = ['book__title', 'borrower_name', 'borrower_email']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'is_read', 'responded_at', 'created_at']
    list_filter = ['is_read', 'responded_at', 'created_at']
    search_fields = ['name', 'email', 'message', 'admin_response']
    readonly_fields = ['created_at']


@admin.register(BookComment)
class BookCommentAdmin(admin.ModelAdmin):
    list_display = ['book', 'name', 'parent', 'is_approved', 'created_at']
    list_filter = ['is_approved', 'created_at']
    search_fields = ['book__title', 'name', 'email', 'comment']


@admin.register(UserNotification)
class UserNotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'kind', 'title', 'is_read', 'created_at']
    list_filter = ['kind', 'is_read', 'created_at']
    search_fields = ['user__username', 'user__email', 'title', 'message']
    readonly_fields = ['created_at']
