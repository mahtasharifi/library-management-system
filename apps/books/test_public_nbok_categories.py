from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Book, Category, NBOKEntry


class PublicNBOKCategoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reader", password="secret-pass-123")
        self.client.force_login(self.user)
        Category.objects.all().delete()
        self.row = NBOKEntry.objects.create(
            l1="ریشه آزمون عمومی",
            l2="شاخه آزمون عمومی",
            l3="برگ آزمون عمومی",
        )
        self.book = Book.objects.create(
            title="کتاب آزمون",
            author="نویسنده",
            nbok_category=self.row,
            nbok_category_level="L3",
        )

    def test_public_categories_only_show_exact_levels_used_by_books(self):
        self.assertFalse(Category.objects.exists())
        response = self.client.get(reverse("api_categories"))
        self.assertEqual(response.status_code, 200)
        categories = response.json()["data"]
        self.assertEqual(len(categories), 1)
        self.assertEqual(categories[0]["id"], f"{self.row.id}-L3")
        self.assertEqual(categories[0]["name"], "برگ آزمون عمومی")
        self.assertEqual(categories[0]["book_count"], 1)
        self.assertEqual(categories[0]["children"], [])

    def test_catalog_sidebar_only_renders_category_that_has_a_book(self):
        response = self.client.get(reverse("book_catalog"))
        self.assertNotContains(response, "ریشه آزمون عمومی")
        self.assertNotContains(response, "شاخه آزمون عمومی")
        self.assertContains(response, "برگ آزمون عمومی")
        self.assertNotContains(response, "سطح 3")
        self.assertNotContains(response, "L3")

    def test_exact_nbok_filter_does_not_include_descendant_selection(self):
        parent_book = Book.objects.create(
            title="کتاب سطح والد",
            author="نویسنده",
            nbok_category=self.row,
            nbok_category_level="L2",
        )
        response = self.client.get(reverse("book_catalog"), {"category": f"{self.row.id}-L2"})
        self.assertContains(response, parent_book.title)
        self.assertNotContains(response, self.book.title)

    def test_unused_nbok_category_is_not_exposed_publicly(self):
        unused = NBOKEntry.objects.create(l1="دسته بدون کتاب")
        response = self.client.get(reverse("api_categories"))
        ids = {item["id"] for item in response.json()["data"]}
        names = {item["name"] for item in response.json()["data"]}
        self.assertNotIn(f"{unused.id}-L1", ids)
        self.assertNotIn("دسته بدون کتاب", names)

    def test_public_book_serializer_uses_selected_nbok_label(self):
        response = self.client.get(reverse("api_books"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        selected = next(item for item in payload if item["id"] == self.book.id)
        self.assertEqual(selected["category"], "برگ آزمون عمومی")
