import json
import tempfile
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import openpyxl
from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.test import override_settings
from django.urls import reverse

from .forms import AdminBookForm
from .models import (
    Book, BookComment, BookRating, BookRequest, Category, Message,
    PhysicalBookBorrow, PhysicalBookRequest, UserNotification,
)
from .storage import delete_library_asset, save_library_asset


class LibraryPageTests(TestCase):
    def setUp(self):
        self.password = 'A-secure-pass-123'
        self.user = User.objects.create_user(username='reader', password=self.password)
        self.staff = User.objects.create_user(username='manager', password=self.password, is_staff=True)

    def test_library_home_uses_new_brand_shell(self):
        self.client.login(username=self.user.username, password=self.password)
        response = self.client.get('/library/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'library-shell')
        self.assertContains(response, 'چه کتابی می‌خواهید؟')
        self.assertContains(response, 'library-request-nav')
        self.assertContains(response, 'library-request-mobile')
        self.assertContains(response, 'data-open-contact')
        self.assertContains(response, 'show_categories=1')
        self.assertContains(response, 'data-notification-toggle')
        self.assertContains(response, 'css/library.css')
        self.assertContains(response, 'library-footer-links')
        self.assertContains(response, '<span>درخواست کتاب</span>', html=True)
        self.assertNotContains(response, 'فضایی ساده برای جستجو، درخواست و امانت کتاب')
        self.assertNotContains(response, 'سامانه جستجو و امانت کتاب')
        self.assertNotContains(response, 'data-persian-current-year')

    def test_dashboard_and_upload_require_staff(self):
        self.client.login(username=self.user.username, password=self.password)
        dashboard_response = self.client.get(reverse('dashboard'))
        self.assertEqual(dashboard_response.status_code, 302)

        self.client.logout()
        self.client.login(username=self.staff.username, password=self.password)
        dashboard_response = self.client.get(reverse('dashboard'))
        upload_response = self.client.get(reverse('upload'))

        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, 'dashboard-page')
        self.assertContains(dashboard_response, 'books/js/admin-dashboard.js')
        self.assertContains(dashboard_response, 'data-section="books"')
        self.assertContains(dashboard_response, 'admin-shell')
        self.assertContains(dashboard_response, 'id="content"')
        self.assertNotContains(dashboard_response, 'دریافت نسخه پشتیبان')
        self.assertContains(dashboard_response, 'امانت‌ها و درخواست‌های فیزیکی')
        self.assertContains(dashboard_response, 'اعضای کتابخانه')
        self.assertEqual(upload_response.status_code, 200)
        self.assertContains(upload_response, 'upload-shell')


class AdminBookFormTests(TestCase):
    def test_legacy_pdf_url_is_rejected_as_unexpected_input(self):
        form = AdminBookForm({
            "title": "Book",
            "author": "Author",
            "book_type": "physical",
            "physical_count": 1,
            "tags": "[]",
            "pdf_url": "https://example.com/book.pdf",
        })

        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)


class CatalogShelfTests(TestCase):
    def setUp(self):
        self.password = 'A-secure-pass-123'
        self.user = User.objects.create_user(username='catalog-reader', password=self.password)
        self.category = Category.objects.create(name='موضوع تست')
        self.available = Book.objects.create(
            title='کتاب موجود تست', author='نویسنده آبی', category=self.category,
            physical_count=2, physical_available=2,
            cover_url='https://cdn.example.com/available.jpg',
        )
        self.borrowed = Book.objects.create(
            title='کتاب امانت تست', author='نویسنده سبز', category=self.category,
            physical_count=1, physical_available=0,
        )
        PhysicalBookBorrow.objects.create(
            book=self.borrowed, borrower_name='امانت‌گیرنده',
            borrower_email='borrower@example.com', borrow_date=date.today(),
            return_date=date.today() + timedelta(days=7),
        )

    def test_catalog_page_contains_dynamic_shelf_shell(self):
        self.client.login(username=self.user.username, password=self.password)
        response = self.client.get(reverse('book_catalog'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'catalog-bookshelf-grid')
        self.assertContains(response, 'library-bookshelf')
        self.assertContains(response, 'real-library-bookshelf')
        self.assertContains(response, 'real-library-casework')
        self.assertContains(response, 'class="real-library-shelf-board ', count=2)
        self.assertContains(response, 'data-book-pullout', count=2)
        self.assertContains(response, 'class="shelf-slot"', count=2)
        self.assertContains(response, 'catalog-shelf-spine', count=2)
        self.assertContains(response, 'catalog-shelf-title', count=2)
        self.assertContains(response, 'shelf-book-page-block', count=2)
        self.assertContains(response, 'shelf-book-top-edge', count=2)
        self.assertContains(response, 'id="catalogPagination"')
        self.assertContains(response, 'css/library.css')
        self.assertContains(response, 'books/js/library.js')
        self.assertContains(response, 'catalogSearchInput')
        self.assertContains(response, 'catalogAvailabilityFilter')
        self.assertContains(response, self.available.title)
        self.assertContains(response, self.borrowed.title)
        self.assertContains(response, reverse('book_detail', args=[self.available.id]))
        self.assertNotContains(response, self.available.cover_url)

    def test_new_database_book_appears_without_frontend_changes(self):
        self.client.login(username=self.user.username, password=self.password)
        first_response = self.client.get(reverse('book_catalog'))
        self.assertNotContains(first_response, 'کتاب تازه افزوده‌شده')

        created = Book.objects.create(
            title='کتاب تازه افزوده‌شده',
            author='نویسنده تازه',
            category=self.category,
        )
        second_response = self.client.get(reverse('book_catalog'))
        self.assertContains(second_response, created.title)
        self.assertContains(second_response, reverse('book_detail', args=[created.id]))

    def test_catalog_server_does_not_truncate_books_at_fixed_page_size(self):
        self.client.login(username=self.user.username, password=self.password)
        created_ids = [self.available.id, self.borrowed.id]
        for index in range(30):
            created_ids.append(Book.objects.create(
                title=f'کتاب ظرفیت {index}', author='نویسنده ظرفیت', category=self.category,
            ).id)

        response = self.client.get(reverse('book_catalog'), {'page': 2})

        self.assertEqual(response.status_code, 200)
        rendered_ids = [book.id for book in response.context['books']]
        self.assertCountEqual(rendered_ids, created_ids)
        self.assertEqual(len(rendered_ids), len(set(rendered_ids)))
        self.assertNotIn('page_obj', response.context)

    def test_books_api_returns_full_filtered_set_unless_explicitly_paginated(self):
        self.client.login(username=self.user.username, password=self.password)
        for index in range(105):
            Book.objects.create(
                title=f'کتاب API {index}', author='نویسنده API', category=self.category,
            )

        full_response = self.client.get(reverse('api_books'), {'search': 'کتاب API'}).json()
        paged_response = self.client.get(reverse('api_books'), {
            'search': 'کتاب API', 'paginate': '1', 'page_size': '6',
        }).json()

        self.assertEqual(full_response['total_count'], 105)
        self.assertEqual(len(full_response['data']), 24)
        self.assertGreater(full_response['total_pages'], 1)
        self.assertEqual(len({book['id'] for book in full_response['data']}), 24)
        self.assertEqual(full_response['page_size'], 24)
        self.assertEqual(len(paged_response['data']), 6)
        self.assertGreater(paged_response['total_pages'], 1)

    def test_catalog_search_filters_by_title_author_and_category(self):
        self.client.login(username=self.user.username, password=self.password)
        for query, expected, excluded in [
            ('موجود تست', self.available, self.borrowed),
            ('نویسنده سبز', self.borrowed, self.available),
            ('موضوع تست', self.available, None),
        ]:
            response = self.client.get(reverse('book_catalog'), {'q': query})
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, expected.title)
            if excluded:
                self.assertNotContains(response, excluded.title)
            self.assertNotContains(response, self.available.cover_url)

    def test_catalog_single_and_empty_search_results(self):
        self.client.login(username=self.user.username, password=self.password)
        single = self.client.get(reverse('book_catalog'), {'q': self.available.title})
        self.assertEqual(list(single.context['books']), [self.available])
        self.assertContains(single, self.available.title)
        self.assertNotContains(single, self.borrowed.title)

        empty = self.client.get(reverse('book_catalog'), {'q': 'این عنوان وجود ندارد'})
        self.assertEqual(list(empty.context['books']), [])
        self.assertContains(empty, 'کتابی با این مشخصات پیدا نشد.')
        self.assertContains(empty, 'نمایش همه کتاب‌ها')

    def test_books_api_searches_title_author_category_and_status_without_mock_data(self):
        self.client.login(username=self.user.username, password=self.password)
        for query, expected_id in [
            ({'search': 'موجود تست'}, self.available.id),
            ({'search': 'نویسنده سبز'}, self.borrowed.id),
            ({'search': 'موضوع تست'}, self.available.id),
            ({'availability': 'borrowed'}, self.borrowed.id),
            ({'availability': 'available'}, self.available.id),
        ]:
            response = self.client.get(reverse('api_books'), query)
            self.assertEqual(response.status_code, 200)
            ids = [row['id'] for row in response.json()['data']]
            self.assertIn(expected_id, ids)

        one_result = self.client.get(reverse('api_books'), {'search': 'کتاب موجود تست'}).json()
        self.assertEqual(one_result['total_count'], 1)
        no_result = self.client.get(reverse('api_books'), {'search': 'این عنوان وجود ندارد'}).json()
        self.assertEqual(no_result['total_count'], 0)


class BookDetailAndRatingTests(TestCase):
    def setUp(self):
        self.password = 'A-secure-pass-123'
        self.user = User.objects.create_user(username='rating-reader', password=self.password)
        self.other_user = User.objects.create_user(username='other-reader', password=self.password)
        self.category = Category.objects.create(name='داستان')
        self.book = Book.objects.create(
            title='کتاب جزئیات',
            author='نویسنده جزئیات',
            translator='مترجم جزئیات',
            publisher='ناشر جزئیات',
            category=self.category,
            summary='توضیح کامل کتاب برای آزمون صفحه جزئیات.',
            cover_url='https://cdn.example.com/detail-cover.jpg',
            physical_count=2,
            physical_available=1,
        )

    def _rate(self, value, book_id=None):
        return self.client.post(
            reverse('api_rate_book'),
            data=json.dumps({'book_id': book_id or self.book.id, 'rating': value}),
            content_type='application/json',
        )

    def test_detail_page_contains_real_cover_complete_information_and_rating_controls(self):
        self.client.login(username=self.user.username, password=self.password)
        response = self.client.get(reverse('book_detail', args=[self.book.id]))
        self.assertEqual(response.status_code, 200)
        for value in [
            self.book.cover_url, self.book.title, self.book.author,
            self.book.translator, self.book.publisher, self.category.name,
            self.book.summary, 'انتخاب امتیاز از یک تا پنج',
        ]:
            self.assertContains(response, value)
        self.assertContains(response, 'data-rate="1"')
        self.assertContains(response, 'data-rate="5"')
        self.assertNotContains(response, 'هنوز امتیازی ثبت نشده')

    def test_book_8_detail_handles_legacy_null_timestamps(self):
        normal_book = Book.objects.create(
            pk=2,
            title='کتاب دوم',
            author='نویسنده دوم',
            category=self.category,
        )
        legacy_book = Book.objects.create(
            pk=8,
            title='کتاب قدیمی با تاریخ ناقص',
            author='نویسنده قدیمی',
            category=self.category,
        )
        legacy_book.created_at = None
        legacy_book.updated_at = None
        legacy_book.average_rating = None
        legacy_book.rating_total = 0
        legacy_book.active_borrows_cache = []

        self.client.login(username=self.user.username, password=self.password)
        normal_response = self.client.get(reverse('book_detail', args=[normal_book.id]))
        with patch('apps.books.services.catalog.get_object_or_404', return_value=legacy_book):
            legacy_response = self.client.get(reverse('book_detail', args=[legacy_book.id]))

        self.assertEqual(normal_response.status_code, 200)
        self.assertContains(normal_response, normal_book.title)
        self.assertEqual(legacy_response.status_code, 200)
        self.assertIsNone(legacy_response.context['detail_book_data']['created_at'])
        self.assertIsNone(legacy_response.context['detail_book_data']['updated_at'])
        self.assertContains(legacy_response, legacy_book.title)

    def test_each_valid_rating_is_saved_and_rerating_updates_the_same_row(self):
        self.client.login(username=self.user.username, password=self.password)
        for value in range(1, 6):
            response = self._rate(value)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['user_rating'], value)
            self.assertEqual(BookRating.objects.get(book=self.book, user=self.user).rating, value)
            self.assertEqual(BookRating.objects.filter(book=self.book, user=self.user).count(), 1)

    def test_average_count_and_reload_persistence_come_from_database(self):
        BookRating.objects.create(book=self.book, user=self.other_user, rating=2)
        self.client.login(username=self.user.username, password=self.password)
        response = self._rate(4)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['average_rating'], 3.0)
        self.assertEqual(response.json()['rating_count'], 2)

        reloaded = self.client.get(reverse('book_detail', args=[self.book.id]))
        self.assertEqual(reloaded.context['user_rating'], 4)
        self.assertEqual(reloaded.context['average_rating'], 3.0)
        self.assertEqual(reloaded.context['rating_count'], 2)
        self.assertContains(reloaded, 'امتیاز شما: 4 از ۵')

    def test_invalid_ratings_are_rejected_by_backend(self):
        self.client.login(username=self.user.username, password=self.password)
        for value in [0, 6, -1, 100, 'abc', 2.5, None, True]:
            with self.subTest(value=value):
                response = self._rate(value)
                self.assertEqual(response.status_code, 400)
        self.assertFalse(BookRating.objects.filter(book=self.book, user=self.user).exists())

    def test_anonymous_invalid_book_and_csrf_failures_are_clear(self):
        anonymous = self._rate(5)
        self.assertEqual(anonymous.status_code, 401)
        self.assertIn('وارد حساب', anonymous.json()['message'])

        self.client.login(username=self.user.username, password=self.password)
        missing = self._rate(5, book_id=999999)
        self.assertEqual(missing.status_code, 404)
        self.assertFalse(missing.json()['success'])

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.login(username=self.user.username, password=self.password)
        csrf_client.get(reverse('book_detail', args=[self.book.id]))
        without_token = csrf_client.post(
            reverse('api_rate_book'),
            data=json.dumps({'book_id': self.book.id, 'rating': 5}),
            content_type='application/json',
        )
        self.assertEqual(without_token.status_code, 403)
        token = csrf_client.cookies['csrftoken'].value
        with_token = csrf_client.post(
            reverse('api_rate_book'),
            data=json.dumps({'book_id': self.book.id, 'rating': 5}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(with_token.status_code, 200)

    def test_database_enforces_unique_user_book_and_rating_range(self):
        BookRating.objects.create(book=self.book, user=self.user, rating=3)
        with self.assertRaises(IntegrityError), transaction.atomic():
            BookRating.objects.create(book=self.book, user=self.user, rating=4)
        with self.assertRaises(IntegrityError), transaction.atomic():
            BookRating.objects.create(book=self.book, user=self.other_user, rating=6)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='library@example.com',
    SITE_URL='https://library.example.com',
    LIBRARY_CDN_BASE_URL='https://cdn.example.com/library/',
)
class RequestWorkflowTests(TestCase):
    def setUp(self):
        self.password = 'A-secure-pass-123'
        self.reader = User.objects.create_user(
            username='reader-flow', email='reader-flow@example.com', password=self.password,
        )
        self.reader.profile.phone_number = '09121234567'
        self.reader.profile.save(update_fields=['phone_number'])
        self.staff = User.objects.create_user(
            username='manager-flow', password=self.password, is_staff=True,
        )
        self.book = Book.objects.create(
            title='کتاب فیزیکی تست', author='نویسنده تست',
            physical_count=2, physical_available=2,
        )

    def test_physical_request_read_approve_and_notification_flow(self):
        self.client.login(username=self.reader.username, password=self.password)
        create_response = self.client.post(
            reverse('api_request_physical_book'),
            data=json.dumps({
                'book_id': self.book.id, 'name': 'کاربر تست',
                'email': self.reader.email, 'phone': '09121234567',
            }),
            content_type='application/json',
        )
        self.assertEqual(create_response.status_code, 200)
        request_item = PhysicalBookRequest.objects.get()

        self.client.logout()
        self.client.login(username=self.staff.username, password=self.password)
        counts = self.client.get(reverse('api_admin_unread_counts')).json()
        self.assertEqual(counts['physical'], 1)

        list_response = self.client.get(reverse('api_admin_physical_requests'))
        self.assertEqual(list_response.status_code, 200)
        request_item.refresh_from_db()
        self.assertIsNone(request_item.admin_read_at)
        self.assertFalse(UserNotification.objects.filter(
            user=self.reader, related_id=request_item.id, kind='read',
        ).exists())

        mark_response = self.client.post(reverse('api_admin_physical_requests_mark_read'))
        self.assertEqual(mark_response.status_code, 200)
        request_item.refresh_from_db()
        self.assertIsNotNone(request_item.admin_read_at)
        self.assertTrue(UserNotification.objects.filter(
            user=self.reader, related_id=request_item.id, kind='read',
        ).exists())

        today = date.today()
        approve_response = self.client.post(
            reverse('api_admin_approve_physical_request'),
            data=json.dumps({
                'request_id': request_item.id,
                'borrow_date': today.isoformat(),
                'return_date': (today + timedelta(days=14)).isoformat(),
            }),
            content_type='application/json',
        )
        self.assertEqual(approve_response.status_code, 200)
        self.assertTrue(PhysicalBookBorrow.objects.filter(book=self.book, is_returned=False).exists())
        self.assertTrue(UserNotification.objects.filter(user=self.reader, kind='approved').exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('تأیید امانت', mail.outbox[0].subject)
        self.assertIn('library.example.com', mail.outbox[0].alternatives[0][0])
        self.book.refresh_from_db()
        self.assertEqual(self.book.physical_available, 1)

    def test_digital_request_get_is_side_effect_free_and_post_marks_read(self):
        item = BookRequest.objects.create(
            user=self.reader, book=self.book, email=self.reader.email, status='pending',
        )
        self.client.login(username=self.staff.username, password=self.password)

        response = self.client.get(reverse('api_admin_book_requests'))
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertIsNone(item.admin_read_at)

        response = self.client.post(reverse('api_admin_book_requests_mark_read'))
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertIsNotNone(item.admin_read_at)

    def test_message_reply_is_visible_as_user_notification(self):
        message = Message.objects.create(
            user=self.reader, name='کاربر تست', email=self.reader.email,
            message='کتابی درباره روانشناسی می‌خواهم.',
        )
        self.client.login(username=self.staff.username, password=self.password)
        reply = self.client.post(
            reverse('api_admin_message_reply', args=[message.id]),
            data=json.dumps({'response': 'چند عنوان مناسب برای شما پیدا شد.'}),
            content_type='application/json',
        )
        self.assertEqual(reply.status_code, 200)
        message.refresh_from_db()
        self.assertTrue(message.is_read)
        self.assertEqual(message.admin_response, 'چند عنوان مناسب برای شما پیدا شد.')
        self.assertTrue(UserNotification.objects.filter(user=self.reader, kind='answered').exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('چند عنوان مناسب برای شما پیدا شد.', mail.outbox[0].alternatives[0][0])

    def test_contact_form_creates_clear_message_for_admin(self):
        self.client.login(username=self.reader.username, password=self.password)
        response = self.client.post(
            reverse('api_contact'),
            data=json.dumps({
                'type': 'contact',
                'topic': 'مشکل فنی',
                'subject': 'باز نشدن فایل',
                'message': 'لینک دانلود برای من باز نمی‌شود.',
                'email': self.reader.email,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        saved = Message.objects.get()
        self.assertEqual(saved.user, self.reader)
        self.assertIn('نوع پیام: تماس با کتابخانه', saved.message)
        self.assertIn('عنوان: باز نشدن فایل', saved.message)

    def test_account_email_is_default_and_submitted_email_can_override_it(self):
        self.client.login(username=self.reader.username, password=self.password)
        default_response = self.client.post(
            reverse('api_contact'),
            data=json.dumps({
                'type': 'contact', 'topic': 'پرسش عمومی',
                'subject': 'ایمیل پیش‌فرض', 'message': 'بررسی ایمیل حساب',
            }),
            content_type='application/json',
        )
        override_response = self.client.post(
            reverse('api_contact'),
            data=json.dumps({
                'type': 'contact', 'topic': 'پرسش عمومی',
                'subject': 'ایمیل جایگزین', 'message': 'بررسی ایمیل جایگزین',
                'email': 'alternate@example.com',
            }),
            content_type='application/json',
        )

        self.assertEqual(default_response.status_code, 200)
        self.assertEqual(override_response.status_code, 200)
        self.assertEqual(Message.objects.get(message__contains='ایمیل پیش‌فرض').email, self.reader.email)
        self.assertEqual(Message.objects.get(message__contains='ایمیل جایگزین').email, 'alternate@example.com')

    def test_pdf_approval_email_uses_protected_download_url(self):
        self.book.pdf_url = 'https://cdn.example.com/library/PDF/book.pdf'
        self.book.save(update_fields=['pdf_url'])
        item = BookRequest.objects.create(
            book=self.book,
            user=self.reader,
            name='کاربر تست',
            email=self.reader.email,
        )
        self.client.login(username=self.staff.username, password=self.password)

        response = self.client.post(reverse('api_admin_approve_book_request', args=[item.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['email_sent'])
        self.assertEqual(len(mail.outbox), 1)
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn('لینک دانلود کتاب', mail.outbox[0].subject)
        self.assertIn(reverse('book_pdf_download', args=[self.book.id]), html)
        self.assertNotIn('https://dl.example.com/book.pdf', html)

    def test_public_book_api_does_not_expose_private_download_or_borrower_data(self):
        self.book.pdf_url = 'https://cdn.example.com/library/PDF/private.pdf'
        self.book.save(update_fields=['pdf_url'])
        PhysicalBookBorrow.objects.create(
            book=self.book,
            borrower_name='نام امانت گیرنده',
            borrower_email='borrower@example.com',
            borrow_date=date.today(),
            return_date=date.today() + timedelta(days=7),
            is_returned=False,
        )
        self.client.login(username=self.reader.username, password=self.password)

        response = self.client.get(reverse('api_books'))

        self.assertEqual(response.status_code, 200)
        item = next(row for row in response.json()['data'] if row['id'] == self.book.id)
        self.assertTrue(item['has_pdf'])
        self.assertNotIn('pdf_url', item)
        self.assertNotIn('current_borrower', item)

    def test_cdn_pdf_download_requires_approved_request(self):
        self.book.pdf_url = 'https://cdn.example.com/library/PDF/book.pdf'
        self.book.save(update_fields=['pdf_url'])
        url = reverse('book_pdf_download', args=[self.book.id])

        self.client.login(username=self.reader.username, password=self.password)
        denied = self.client.get(url)
        self.assertEqual(denied.status_code, 404)

        BookRequest.objects.create(
            book=self.book,
            user=self.reader,
            name='کاربر تست',
            email=self.reader.email,
            status='approved',
        )
        allowed = self.client.get(url)
        self.assertEqual(allowed.status_code, 302)
        self.assertEqual(allowed['Location'], self.book.pdf_url)
        self.assertEqual(allowed['Cache-Control'], 'private, no-store')
        self.assertEqual(allowed['Referrer-Policy'], 'no-referrer')

    def test_excel_import_skips_header_and_creates_physical_book_only(self):
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(['عنوان', 'نویسنده', 'تعداد نسخه فیزیکی', 'لینک عکس جلد'])
        sheet.append([
            'کتاب واردشده', 'نویسنده اکسل', 3,
            'https://cdn.example.com/library/Cover/imported.jpg',
        ])
        output = BytesIO()
        workbook.save(output)
        upload = SimpleUploadedFile(
            'physical.xlsx', output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.client.login(username=self.staff.username, password=self.password)
        response = self.client.post(reverse('api_admin_books_import'), {'excel': upload})
        self.assertEqual(response.status_code, 200)
        imported = Book.objects.get(title='کتاب واردشده')
        self.assertEqual(imported.physical_count, 3)
        self.assertEqual(imported.physical_available, 3)
        self.assertFalse(imported.has_pdf)

    def test_admin_can_reply_to_comment_from_dashboard_api(self):
        comment = BookComment.objects.create(
            book=self.book,
            name='خواننده',
            email=self.reader.email,
            comment='این کتاب برای شروع مناسب است؟',
        )
        self.client.login(username=self.staff.username, password=self.password)
        response = self.client.post(
            reverse('api_admin_comment_reply', args=[comment.id]),
            data=json.dumps({'response': 'بله، برای شروع انتخاب مناسبی است.'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        reply = comment.replies.get()
        self.assertEqual(reply.name, 'مدیریت کتابخانه')
        self.assertTrue(UserNotification.objects.filter(
            user=self.reader,
            kind='answered',
            related_type='bookcomment',
            related_id=comment.id,
        ).exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('پاسخ به نظر شما', mail.outbox[0].subject)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AdminMemberAndLoanManagementTests(TestCase):
    def setUp(self):
        self.password = 'A-secure-pass-123'
        self.staff = User.objects.create_user(
            username='loan-manager', email='manager@example.com',
            password=self.password, is_staff=True,
        )
        self.member = User.objects.create_user(
            username='library-member', email='member@example.com',
            first_name='عضو', last_name='کتابخانه', password=self.password,
        )

    def test_staff_can_edit_member_reset_password_and_delete(self):
        self.client.login(username=self.staff.username, password=self.password)
        update = self.client.post(
            reverse('api_admin_user_update', args=[self.member.id]),
            data=json.dumps({
                'username': 'member-edited', 'email': 'edited@example.com',
                'first_name': 'نام جدید', 'last_name': 'نام خانوادگی جدید',
                'phone': '09120000000', 'is_active': False, 'is_staff': False,
            }),
            content_type='application/json',
        )
        self.assertEqual(update.status_code, 200)
        self.member.refresh_from_db()
        self.assertEqual(self.member.username, 'member-edited')
        self.assertEqual(self.member.email, 'edited@example.com')
        self.assertFalse(self.member.is_active)
        self.assertEqual(self.member.profile.phone_number, '09120000000')

        reset = self.client.post(
            reverse('api_admin_user_password', args=[self.member.id]),
            data=json.dumps({'password': 'New-member-pass-123'}),
            content_type='application/json',
        )
        self.assertEqual(reset.status_code, 200)
        self.assertTrue(User.objects.get(id=self.member.id).check_password('New-member-pass-123'))

        deleted = self.client.post(reverse('api_admin_user_delete', args=[self.member.id]))
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(User.objects.filter(id=self.member.id).exists())

    def test_active_loan_api_identifies_borrower_and_return_restores_stock(self):
        book = Book.objects.create(
            title='کتاب امانتی تست', author='نویسنده تست',
            physical_count=1, physical_available=0,
        )
        borrow = PhysicalBookBorrow.objects.create(
            book=book, borrower_name='امانت‌گیرنده تست',
            borrower_email='borrower@example.com', borrower_phone='09121111111',
            borrow_date=date.today(), return_date=date.today() + timedelta(days=7),
        )
        self.client.login(username=self.staff.username, password=self.password)
        listing = self.client.get(reverse('api_admin_borrowed_books'))
        self.assertEqual(listing.status_code, 200)
        row = next(item for item in listing.json()['data'] if item['id'] == borrow.id)
        self.assertEqual(row['book_title'], book.title)
        self.assertEqual(row['borrower_email'], 'borrower@example.com')
        self.assertEqual(row['borrower_phone'], '09121111111')

        returned = self.client.post(reverse('api_admin_return_book', args=[borrow.id]))
        self.assertEqual(returned.status_code, 200)
        borrow.refresh_from_db()
        book.refresh_from_db()
        self.assertTrue(borrow.is_returned)
        self.assertEqual(book.physical_available, 1)


class LibraryAssetStorageTests(TestCase):
    @override_settings(
        LIBRARY_CDN_STORAGE='ftp',
        LIBRARY_CDN_BASE_URL='https://cdn.example.com/library/',
        LIBRARY_CDN_FTP_HOST='ftp.example.com',
        LIBRARY_CDN_FTP_PORT=21,
        LIBRARY_CDN_FTP_USER='library-uploader',
        LIBRARY_CDN_FTP_PASSWORD='test-password',
        LIBRARY_CDN_FTP_ROOT='public_html/Library',
        LIBRARY_CDN_FTP_TLS=False,
    )
    @patch('apps.books.services.storage.ftplib.FTP')
    def test_cover_upload_uses_ftp_cover_folder(self, ftp_class):
        ftp = ftp_class.return_value
        upload = SimpleUploadedFile('جلد کتاب.jpg', b'\xff\xd8\xff\xe0' + b'jpeg-test', content_type='image/jpeg')

        url = save_library_asset(upload, 'cover')

        ftp.connect.assert_called_once_with('ftp.example.com', 21, timeout=30)
        ftp.login.assert_called_once_with('library-uploader', 'test-password')
        self.assertEqual(
            [call.args[0] for call in ftp.cwd.call_args_list[:3]],
            ['public_html', 'Library', 'Cover'],
        )
        remote_name = ftp.storbinary.call_args.args[0]
        self.assertTrue(remote_name.startswith('STOR cover-'))
        self.assertTrue(remote_name.endswith('.jpg'))
        self.assertTrue(url.startswith('https://cdn.example.com/library/Cover/cover-'))
        self.assertTrue(url.endswith('.jpg'))

    @override_settings(
        LIBRARY_CDN_STORAGE='ftp',
        LIBRARY_CDN_BASE_URL='https://cdn.example.com/library/',
        LIBRARY_CDN_FTP_HOST='ftp.example.com',
        LIBRARY_CDN_FTP_PORT=21,
        LIBRARY_CDN_FTP_USER='library-uploader',
        LIBRARY_CDN_FTP_PASSWORD='test-password',
        LIBRARY_CDN_FTP_ROOT='public_html/Library',
        LIBRARY_CDN_FTP_TLS=False,
    )
    @patch('apps.books.services.storage.ftplib.FTP')
    def test_pdf_upload_uses_ftp_pdf_folder(self, ftp_class):
        ftp = ftp_class.return_value
        upload = SimpleUploadedFile('book.pdf', b'%PDF-1.4\n% test', content_type='application/pdf')

        url = save_library_asset(upload, 'pdf')

        self.assertEqual(
            [call.args[0] for call in ftp.cwd.call_args_list[:3]],
            ['public_html', 'Library', 'PDF'],
        )
        self.assertTrue(ftp.storbinary.call_args.args[0].startswith('STOR pdf-'))
        self.assertTrue(url.startswith('https://cdn.example.com/library/PDF/pdf-'))

    @override_settings(
        LIBRARY_CDN_STORAGE='ftp',
        LIBRARY_CDN_BASE_URL='https://cdn.example.com/library/',
        LIBRARY_CDN_FTP_HOST='ftp.example.com',
        LIBRARY_CDN_FTP_PORT=21,
        LIBRARY_CDN_FTP_USER='library-uploader',
        LIBRARY_CDN_FTP_PASSWORD='test-password',
        LIBRARY_CDN_FTP_ROOT='public_html/Library',
        LIBRARY_CDN_FTP_TLS=False,
    )
    @patch('apps.books.services.storage.ftplib.FTP')
    def test_managed_pdf_delete_removes_remote_file(self, ftp_class):
        ftp = ftp_class.return_value

        deleted = delete_library_asset(
            'https://cdn.example.com/library/PDF/pdf-abc.pdf',
            'pdf',
        )

        self.assertTrue(deleted)
        self.assertEqual(
            [call.args[0] for call in ftp.cwd.call_args_list[:3]],
            ['public_html', 'Library', 'PDF'],
        )
        ftp.delete.assert_called_once_with('pdf-abc.pdf')



class BackgroundJobTests(TestCase):
    def setUp(self):
        self.password = 'A-secure-pass-123'
        self.staff = User.objects.create_user(
            username='job-manager', email='jobs@example.com',
            password=self.password, is_staff=True,
        )
        self.other_staff = User.objects.create_user(
            username='other-job-manager', email='other-jobs@example.com',
            password=self.password, is_staff=True,
        )

    @override_settings(BACKGROUND_JOBS_EAGER=False)
    def test_email_is_queued_then_delivered_and_payload_is_scrubbed(self):
        from .models import BackgroundJob
        from .services.email import send_library_email
        from .services.jobs import process_next_job

        accepted = send_library_email(
            'reader@example.com', 'موضوع تست', 'عنوان تست', 'متن تست',
        )
        self.assertTrue(accepted)
        job = BackgroundJob.objects.get(job_type=BackgroundJob.TYPE_EMAIL)
        self.assertEqual(job.status, BackgroundJob.STATUS_QUEUED)
        self.assertEqual(job.max_attempts, 1)
        self.assertEqual(len(mail.outbox), 0)

        self.assertTrue(process_next_job())
        job.refresh_from_db()
        self.assertEqual(job.status, BackgroundJob.STATUS_COMPLETED)
        self.assertEqual(job.payload, {})
        self.assertTrue(job.result['delivered'])
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(BACKGROUND_JOBS_EAGER=False)
    def test_json_import_is_queued_and_job_status_is_owner_scoped(self):
        from .models import BackgroundJob
        from .services.jobs import process_next_job

        self.client.login(username=self.staff.username, password=self.password)
        response = self.client.post(
            reverse('api_admin_books_import'),
            data=json.dumps([{
                'عنوان': 'کتاب صف تست',
                'نویسنده': 'نویسنده صف',
                'تعداد نسخه فیزیکی': 2,
            }]),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload['status'], BackgroundJob.STATUS_QUEUED)
        self.assertFalse(Book.objects.filter(title='کتاب صف تست').exists())

        self.client.logout()
        self.client.login(username=self.other_staff.username, password=self.password)
        forbidden = self.client.get(reverse('api_admin_import_job', args=[payload['id']]))
        self.assertEqual(forbidden.status_code, 404)

        self.assertTrue(process_next_job())
        self.assertTrue(Book.objects.filter(title='کتاب صف تست').exists())

        self.client.logout()
        self.client.login(username=self.staff.username, password=self.password)
        completed = self.client.get(reverse('api_admin_import_job', args=[payload['id']]))
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()['status'], BackgroundJob.STATUS_COMPLETED)

    @override_settings(BACKGROUND_JOBS_EAGER=False)
    def test_failed_import_job_is_retried_with_generic_error_code(self):
        from .models import BackgroundJob
        from .services.jobs import enqueue_job, process_job

        job = enqueue_job(
            BackgroundJob.TYPE_PHYSICAL_IMPORT,
            {'rows': []},
            max_attempts=3,
        )
        with patch('apps.books.services.imports.import_physical_rows', side_effect=RuntimeError('sensitive provider detail')):
            process_job(job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, BackgroundJob.STATUS_QUEUED)
        self.assertEqual(job.attempts, 1)
        self.assertEqual(job.last_error_code, 'RuntimeError')
        self.assertIn('rows', job.payload)

    @override_settings(BACKGROUND_JOBS_EAGER=False)
    def test_failed_email_is_not_automatically_retried_and_payload_is_scrubbed(self):
        from .models import BackgroundJob
        from .services.email import send_library_email
        from .services.jobs import process_next_job

        self.assertTrue(send_library_email('reader@example.com', 'subject', 'heading', 'message'))
        with patch('apps.books.services.email.deliver_library_email', side_effect=RuntimeError('provider detail')):
            self.assertTrue(process_next_job())
        job = BackgroundJob.objects.get(job_type=BackgroundJob.TYPE_EMAIL)
        self.assertEqual(job.max_attempts, 1)
        self.assertEqual(job.attempts, 1)
        self.assertEqual(job.status, BackgroundJob.STATUS_FAILED)
        self.assertEqual(job.payload, {})
        self.assertEqual(job.last_error_code, 'RuntimeError')

    @override_settings(BACKGROUND_JOBS_EAGER=False, BACKGROUND_JOB_LOCK_TIMEOUT_SECONDS=60)
    def test_stale_running_job_is_recovered_after_worker_crash(self):
        from django.utils import timezone
        from .models import BackgroundJob
        from .services.jobs import recover_stale_jobs

        job = BackgroundJob.objects.create(
            job_type=BackgroundJob.TYPE_PHYSICAL_IMPORT,
            payload={'rows': []},
            status=BackgroundJob.STATUS_RUNNING,
            attempts=1,
            max_attempts=3,
            locked_at=timezone.now() - timedelta(minutes=5),
        )
        self.assertEqual(recover_stale_jobs(), 1)
        job.refresh_from_db()
        self.assertEqual(job.status, BackgroundJob.STATUS_QUEUED)
        self.assertIsNone(job.locked_at)
        self.assertEqual(job.last_error_code, 'worker_timeout_retry')
