"""Coverage for the NBOK-backed administrative category flow."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Book, NBOKEntry


class NBOKAdminCategoryTests(TestCase):
    def setUp(self):
        self.password = "A-secure-pass-123"
        self.staff = User.objects.create_user(
            username="nbok-manager",
            password=self.password,
            is_staff=True,
        )
        self.client.login(username=self.staff.username, password=self.password)

    def test_admin_nbok_tree_reads_imported_table(self):
        response = self.client.get(reverse("api_admin_nbok"))
        self.assertEqual(response.status_code, 200, response.content)
        roots = response.json()["data"]
        names = {node["name"] for node in roots}
        self.assertIn("روش توسعه", names)
        self.assertIn("محتوای توسعه", names)

    def test_admin_can_add_child_to_same_nbok_table(self):
        parent = NBOKEntry.objects.filter(l1="روش توسعه").order_by("id").first()
        self.assertIsNotNone(parent)
        before = NBOKEntry.objects.count()
        response = self.client.post(
            reverse("api_admin_nbok_create"),
            data=(
                '{"name":"دسته آزمایشی جدید","parent_row_id":%d,"parent_level":"L1"}'
                % parent.id
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(NBOKEntry.objects.count(), before + 1)
        created = NBOKEntry.objects.get(id=response.json()["row_id"])
        self.assertEqual(created.l1, "روش توسعه")
        self.assertEqual(created.l2, "دسته آزمایشی جدید")

    def test_book_can_store_nbok_category_selection(self):
        row = NBOKEntry.objects.exclude(l3__isnull=True).exclude(l3="").order_by("id").first()
        self.assertIsNotNone(row)
        response = self.client.post(
            reverse("api_admin_book_add"),
            {
                "title": "کتاب دسته‌بندی NBOK",
                "author": "نویسنده تست",
                "translator": "",
                "publisher": "",
                "library": "",
                "nbok_category_id": str(row.id),
                "nbok_category_level": "L3",
                "summary": "",
                "cover_url": "",
                "physical_count": "1",
                "physical_location": "",
                "tags": "[]",
                "book_type": "physical",
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        book = Book.objects.get(id=response.json()["book_id"])
        self.assertEqual(book.nbok_category_id, row.id)
        self.assertEqual(book.nbok_category_level, "L3")

        listing = self.client.get(reverse("api_admin_books"))
        self.assertEqual(listing.status_code, 200, listing.content)
        item = next(item for item in listing.json()["data"] if item["id"] == book.id)
        self.assertEqual(item["nbok_category"], " ".join((row.l3 or "").split()))
        self.assertTrue(item["nbok_category_path"])
