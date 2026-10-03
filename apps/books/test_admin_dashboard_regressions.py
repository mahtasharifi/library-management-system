"""Regression coverage for the custom staff dashboard CRUD paths."""

from __future__ import annotations

import json
import tempfile
from datetime import date, timedelta
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import (
    Book,
    BookComment,
    BookRequest,
    Category,
    Message,
    PhysicalBookBorrow,
    PhysicalBookRequest,
    Question,
)
from .views.admin import _all_books_data


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    LIBRARY_CDN_STORAGE="filesystem",
    LIBRARY_CDN_BASE_URL="/media/library_cdn/",
)
class AdminDashboardCrudRegressionTests(TestCase):
    def setUp(self):
        self.password = "A-secure-pass-123"
        self.staff = User.objects.create_user(
            username="dashboard-manager",
            password=self.password,
            is_staff=True,
        )
        self.client.login(username=self.staff.username, password=self.password)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        root = Path(self.temp_dir.name)
        self.cdn_root = root / "cdn"
        settings_override = override_settings(
            LIBRARY_CDN_ROOT=self.cdn_root,
        )
        settings_override.enable()
        self.addCleanup(settings_override.disable)

    def _cdn_file(self, url: str) -> Path:
        relative = url.split("/media/library_cdn/", 1)[1]
        return self.cdn_root / relative

    def _book_payload(self, **overrides):
        payload = {
            "title": "کتاب تست داشبورد",
            "author": "نویسنده تست",
            "translator": "",
            "publisher": "ناشر تست",
            "library": "قفسه الف",
            "category_id": "",
            "summary": "خلاصه کتاب",
            "cover_url": "https://example.com/cover.jpg",
            "physical_count": "2",
            "physical_location": "A-12",
            "tags": '["تست", "داشبورد"]',
            "book_type": "physical",
        }
        payload.update(overrides)
        return payload

    def test_physical_book_create_update_and_delete_all_return_200(self):
        created = self.client.post(reverse("api_admin_book_add"), self._book_payload())
        self.assertEqual(created.status_code, 200, created.content)
        book = Book.objects.get(pk=created.json()["book_id"])
        self.assertEqual(book.physical_count, 2)
        self.assertEqual(book.physical_available, 2)
        self.assertEqual(book.tags, ["تست", "داشبورد"])

        category = Category.objects.create(name="دسته تست")
        updated = self.client.post(
            reverse("api_admin_book_update", args=[book.id]),
            self._book_payload(
                title="کتاب ویرایش‌شده",
                physical_count="4",
                category_id=str(category.id),
                tags='["ویرایش"]',
            ),
        )
        self.assertEqual(updated.status_code, 200, updated.content)
        book.refresh_from_db()
        self.assertEqual(book.title, "کتاب ویرایش‌شده")
        self.assertEqual(book.category_id, category.id)
        self.assertEqual(book.physical_available, 4)
        self.assertEqual(book.tags, ["ویرایش"])

        deleted = self.client.post(reverse("api_admin_book_delete", args=[book.id]))
        self.assertEqual(deleted.status_code, 200, deleted.content)
        self.assertFalse(Book.objects.filter(pk=book.id).exists())

    def test_pdf_and_cover_upload_create_without_server_error(self):
        cover = SimpleUploadedFile(
            "cover.jpg",
            b"\xff\xd8\xff\xe0" + b"dashboard-cover",
            content_type="image/jpeg",
        )
        pdf = SimpleUploadedFile(
            "book.pdf",
            b"%PDF-1.4\n% dashboard test\n",
            content_type="application/pdf",
        )
        response = self.client.post(
            reverse("api_admin_book_add"),
            self._book_payload(
                book_type="pdf",
                physical_count="0",
                cover_url="",
                cover=cover,
                book_pdf=pdf,
            ),
        )
        self.assertEqual(response.status_code, 200, response.content)
        book = Book.objects.get(pk=response.json()["book_id"])
        self.assertEqual(book.physical_count, 0)
        self.assertTrue(book.has_pdf)
        self.assertTrue(book.cover_url)
        self.assertTrue(book.pdf_url.startswith("/media/library_cdn/PDF/pdf-"))
        self.assertEqual(len(list((self.cdn_root / "PDF").glob("pdf-*.pdf"))), 1)

    def test_replacing_cdn_assets_deletes_old_files_after_success(self):
        old_cover = SimpleUploadedFile(
            "old.jpg", b"\xff\xd8\xff\xe0old", content_type="image/jpeg",
        )
        old_pdf = SimpleUploadedFile(
            "old.pdf", b"%PDF-1.4\nold", content_type="application/pdf",
        )
        created = self.client.post(
            reverse("api_admin_book_add"),
            self._book_payload(book_type="pdf", physical_count="0", cover_url="", cover=old_cover, book_pdf=old_pdf),
        )
        book = Book.objects.get(pk=created.json()["book_id"])
        old_cover_path = self._cdn_file(book.cover_url)
        old_pdf_path = self._cdn_file(book.pdf_url)
        self.assertTrue(old_cover_path.is_file())
        self.assertTrue(old_pdf_path.is_file())

        new_cover = SimpleUploadedFile(
            "new.jpg", b"\xff\xd8\xff\xe0new", content_type="image/jpeg",
        )
        new_pdf = SimpleUploadedFile(
            "new.pdf", b"%PDF-1.4\nnew", content_type="application/pdf",
        )
        updated = self.client.post(
            reverse("api_admin_book_update", args=[book.id]),
            self._book_payload(book_type="pdf", physical_count="0", cover_url="", cover=new_cover, book_pdf=new_pdf),
        )
        self.assertEqual(updated.status_code, 200, updated.content)
        book.refresh_from_db()
        self.assertFalse(old_cover_path.exists())
        self.assertFalse(old_pdf_path.exists())
        self.assertTrue(self._cdn_file(book.cover_url).is_file())
        self.assertTrue(self._cdn_file(book.pdf_url).is_file())

    def test_book_delete_removes_managed_cdn_assets(self):
        cover = SimpleUploadedFile(
            "delete.jpg", b"\xff\xd8\xff\xe0delete", content_type="image/jpeg",
        )
        pdf = SimpleUploadedFile(
            "delete.pdf", b"%PDF-1.4\ndelete", content_type="application/pdf",
        )
        created = self.client.post(
            reverse("api_admin_book_add"),
            self._book_payload(book_type="pdf", physical_count="0", cover_url="", cover=cover, book_pdf=pdf),
        )
        book = Book.objects.get(pk=created.json()["book_id"])
        cover_path, pdf_path = self._cdn_file(book.cover_url), self._cdn_file(book.pdf_url)

        deleted = self.client.post(reverse("api_admin_book_delete", args=[book.id]))

        self.assertEqual(deleted.status_code, 200, deleted.content)
        self.assertFalse(cover_path.exists())
        self.assertFalse(pdf_path.exists())

    def test_invalid_book_after_upload_cleans_new_cdn_files(self):
        cover = SimpleUploadedFile(
            "invalid.jpg", b"\xff\xd8\xff\xe0invalid", content_type="image/jpeg",
        )
        response = self.client.post(
            reverse("api_admin_book_add"),
            self._book_payload(category_id="999999", cover_url="", cover=cover),
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(list((self.cdn_root / "Cover").glob("*")), [])

    def test_nonexistent_category_is_validation_error_not_silent_data_loss(self):
        response = self.client.post(
            reverse("api_admin_book_add"),
            self._book_payload(category_id="999999"),
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])
        self.assertFalse(Book.objects.exists())

    def test_active_borrow_guards_update_and_delete_without_500(self):
        book = Book.objects.create(
            title="کتاب امانت فعال",
            author="نویسنده",
            physical_count=1,
            physical_available=0,
        )
        PhysicalBookBorrow.objects.create(
            book=book,
            borrower_name="عضو",
            borrower_email="reader@example.com",
            borrow_date=date.today(),
            return_date=date.today() + timedelta(days=7),
        )
        update = self.client.post(
            reverse("api_admin_book_update", args=[book.id]),
            self._book_payload(physical_count="0", book_type="pdf"),
        )
        self.assertEqual(update.status_code, 400)
        delete = self.client.post(reverse("api_admin_book_delete", args=[book.id]))
        self.assertEqual(delete.status_code, 400)
        self.assertTrue(Book.objects.filter(pk=book.id).exists())

    def test_category_list_create_update_and_delete_paths_return_200(self):
        listing = self.client.get(reverse("api_admin_categories"))
        self.assertEqual(listing.status_code, 200)

        created = self.client.post(
            reverse("api_admin_category_create"),
            data='{"name":"دسته جدید","parent_id":null}',
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 200, created.content)
        category_id = created.json()["category_id"]

        updated = self.client.post(
            reverse("api_admin_category_update", args=[category_id]),
            data='{"name":"دسته ویرایش‌شده","parent_id":null}',
            content_type="application/json",
        )
        self.assertEqual(updated.status_code, 200, updated.content)

        deleted = self.client.post(reverse("api_admin_category_delete", args=[category_id]))
        self.assertEqual(deleted.status_code, 200, deleted.content)

    def test_admin_book_listing_query_count_stays_bounded(self):
        category = Category.objects.create(name="کارایی")
        Book.objects.bulk_create([
            Book(title=f"کتاب {index}", author="نویسنده", category=category)
            for index in range(40)
        ])
        with CaptureQueriesContext(connection) as queries:
            data = _all_books_data()
        self.assertEqual(len(data), 40)
        self.assertLessEqual(len(queries), 4)

    def test_dashboard_csrf_token_allows_real_book_post(self):
        csrf_client = Client(enforce_csrf_checks=True)
        self.assertTrue(csrf_client.login(username=self.staff.username, password=self.password))
        page = csrf_client.get(reverse("dashboard"))
        self.assertEqual(page.status_code, 200)
        token = csrf_client.cookies["csrftoken"].value
        response = csrf_client.post(
            reverse("api_admin_book_add"),
            self._book_payload(title="کتاب CSRF"),
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200, response.content)


    def test_invalid_category_parent_returns_400_instead_of_server_error(self):
        create = self.client.post(
            reverse("api_admin_category_create"),
            data=json.dumps({"name": "دسته نامعتبر", "parent_id": 999999}),
            content_type="application/json",
        )
        self.assertEqual(create.status_code, 400, create.content)
        category = Category.objects.create(name="دسته موجود")
        update = self.client.post(
            reverse("api_admin_category_update", args=[category.id]),
            data=json.dumps({"name": "دسته موجود", "parent_id": 999999}),
            content_type="application/json",
        )
        self.assertEqual(update.status_code, 400, update.content)

    def test_valid_dashboard_mutations_do_not_return_400_or_500(self):
        book = Book.objects.create(
            title="کتاب گردش کامل",
            author="نویسنده",
            pdf_url="https://cdn.example.com/library/PDF/test.pdf",
            physical_count=2,
            physical_available=2,
        )
        member = User.objects.create_user(
            username="dashboard-member",
            email="member@example.com",
            password=self.password,
        )

        physical = PhysicalBookRequest.objects.create(
            book=book,
            user=member,
            name="عضو",
            email=member.email,
            phone="09120000000",
        )
        today = date.today()
        approved_physical = self.client.post(
            reverse("api_admin_approve_physical_request"),
            data=json.dumps({
                "request_id": physical.id,
                "borrow_date": today.isoformat(),
                "return_date": (today + timedelta(days=7)).isoformat(),
                "notes": "تست",
            }),
            content_type="application/json",
        )
        self.assertEqual(approved_physical.status_code, 200, approved_physical.content)
        borrow = PhysicalBookBorrow.objects.get(book=book, is_returned=False)
        returned = self.client.post(reverse("api_admin_return_book", args=[borrow.id]))
        self.assertEqual(returned.status_code, 200, returned.content)
        history_deleted = self.client.post(
            reverse("api_admin_borrow_history_delete", args=[borrow.id])
        )
        self.assertEqual(history_deleted.status_code, 200, history_deleted.content)

        rejected_physical = PhysicalBookRequest.objects.create(
            book=book, name="عضو دوم", email="second@example.com", phone="09121111111"
        )
        rejected = self.client.post(
            reverse("api_admin_reject_physical_request", args=[rejected_physical.id]),
            data=json.dumps({"response": "رد شد"}),
            content_type="application/json",
        )
        self.assertEqual(rejected.status_code, 200, rejected.content)

        digital_approve = BookRequest.objects.create(
            book=book, user=member, name="عضو", email=member.email
        )
        approved = self.client.post(
            reverse("api_admin_approve_book_request", args=[digital_approve.id])
        )
        self.assertEqual(approved.status_code, 200, approved.content)

        digital_reject = BookRequest.objects.create(
            book=book, name="عضو", email="reject@example.com"
        )
        rejected_digital = self.client.post(
            reverse("api_admin_reject_book_request", args=[digital_reject.id]),
            data=json.dumps({"response": "درخواست رد شد"}),
            content_type="application/json",
        )
        self.assertEqual(rejected_digital.status_code, 200, rejected_digital.content)

        digital_delete = BookRequest.objects.create(
            book=book, name="عضو", email="delete@example.com"
        )
        deleted_digital = self.client.post(
            reverse("api_admin_book_request_delete", args=[digital_delete.id])
        )
        self.assertEqual(deleted_digital.status_code, 200, deleted_digital.content)

        message = Message.objects.create(
            user=member, name="عضو", email=member.email, message="پیام تست"
        )
        marked = self.client.post(reverse("api_admin_message_read", args=[message.id]))
        self.assertEqual(marked.status_code, 200, marked.content)
        replied = self.client.post(
            reverse("api_admin_message_reply", args=[message.id]),
            data=json.dumps({"response": "پاسخ مدیریت"}),
            content_type="application/json",
        )
        self.assertEqual(replied.status_code, 200, replied.content)
        deleted_message = self.client.post(
            reverse("api_admin_message_delete", args=[message.id])
        )
        self.assertEqual(deleted_message.status_code, 200, deleted_message.content)

        comment = BookComment.objects.create(
            book=book, name="عضو", email=member.email, comment="نظر تست"
        )
        comment_reply = self.client.post(
            reverse("api_admin_comment_reply", args=[comment.id]),
            data=json.dumps({"response": "پاسخ نظر"}),
            content_type="application/json",
        )
        self.assertEqual(comment_reply.status_code, 200, comment_reply.content)
        comment_delete = self.client.post(
            reverse("api_admin_comment_delete", args=[comment.id])
        )
        self.assertEqual(comment_delete.status_code, 200, comment_delete.content)

        question = Question.objects.create(book=book, question="سؤال تست")
        answered = self.client.post(
            reverse("api_admin_question_answer", args=[question.id]),
            data=json.dumps({"answer": "پاسخ تست"}),
            content_type="application/json",
        )
        self.assertEqual(answered.status_code, 200, answered.content)
        question_delete = self.client.post(
            reverse("api_admin_question_delete", args=[question.id])
        )
        self.assertEqual(question_delete.status_code, 200, question_delete.content)

    def test_malformed_admin_json_is_400_not_500(self):
        book = Book.objects.create(
            title="کتاب JSON", author="نویسنده", physical_count=1, physical_available=1
        )
        physical = PhysicalBookRequest.objects.create(
            book=book, name="عضو", email="p@example.com", phone="09120000000"
        )
        digital = BookRequest.objects.create(
            book=book, name="عضو", email="d@example.com"
        )
        message = Message.objects.create(name="عضو", email="m@example.com", message="پیام")
        endpoints = [
            reverse("api_admin_reject_physical_request", args=[physical.id]),
            reverse("api_admin_reject_book_request", args=[digital.id]),
            reverse("api_admin_message_reply", args=[message.id]),
        ]
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.post(
                    endpoint, data="{invalid-json", content_type="application/json"
                )
                self.assertEqual(response.status_code, 400, response.content)

    def test_admin_user_listing_query_count_stays_bounded(self):
        for index in range(40):
            User.objects.create_user(
                username=f"member-{index}",
                email=f"member-{index}@example.com",
                password=self.password,
            )
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("api_admin_users"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(response.json()["data"]), 41)
        self.assertLessEqual(len(queries), 8)

    def test_dashboard_assets_keep_frontend_and_backend_payload_in_sync(self):
        project_root = Path(__file__).resolve().parents[2]
        js = (project_root / "apps/books/static/books/js/admin-dashboard.js").read_text()
        css = (project_root / "apps/books/static/books/css/admin-dashboard.css").read_text()
        self.assertIn("formData.delete('id')", js)
        self.assertIn("formData.delete('tags_text')", js)
        self.assertIn("b.cover_url||BOOK_FALLBACK", js)
        self.assertIn("httpStatus: response.status", js)
        self.assertNotIn("return {...data, status: response.status}", js)
        self.assertIn("mutationRequests", js)
        self.assertIn(".dashboard-page .admin-btn", css)
        self.assertIn("border: 0;", css)
        self.assertIn(".dashboard-page .admin-search:focus-within", css)
