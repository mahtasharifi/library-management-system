"""Input schemas for public and administrative book operations."""

from __future__ import annotations

from django import forms

from common.i18n import translate as t


class StrictForm(forms.Form):
    """Reject unexpected request fields before business logic runs."""

    def __init__(self, data=None, files=None, *args, **kwargs):
        super().__init__(data, files, *args, **kwargs)
        self._unexpected_fields = sorted(
            set(data or {}) - set(self.fields)
        )

    def clean(self):
        cleaned = super().clean()

        if self._unexpected_fields:
            raise forms.ValidationError(
                t("books.validation.unexpected_fields"),
                code="unexpected_fields",
                params={
                    "fields": ", ".join(self._unexpected_fields),
                },
            )

        return cleaned


class DigitalBookRequestForm(StrictForm):
    book_id = forms.IntegerField(min_value=1)
    email = forms.EmailField(required=False)


class PhysicalBookRequestForm(StrictForm):
    book_id = forms.IntegerField(min_value=1)
    name = forms.CharField(max_length=200, required=False)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=20)
    message = forms.CharField(max_length=2000, required=False)


class ContactForm(StrictForm):
    type = forms.ChoiceField(choices=[("contact", "contact"), ("book_request", "book_request")], required=False)
    name = forms.CharField(max_length=200, required=False)
    email = forms.EmailField(required=False)
    topic = forms.CharField(max_length=100, required=False)
    subject = forms.CharField(max_length=200, required=False)
    message = forms.CharField(max_length=3000)
    reason = forms.CharField(max_length=2000, required=False)


class CommentForm(StrictForm):
    book_id = forms.IntegerField(min_value=1)
    name = forms.CharField(max_length=200, required=False)
    email = forms.EmailField(required=False)
    text = forms.CharField(max_length=3000, required=False)
    comment = forms.CharField(max_length=3000, required=False)

    def clean(self):
        cleaned = super().clean()
        text = (cleaned.get("text") or cleaned.get("comment") or "").strip()
        if not text:
            self.add_error("text", t("books.validation.comment_required"))
        cleaned["normalized_text"] = text
        return cleaned


class CommentReplyForm(StrictForm):
    parent_id = forms.IntegerField(min_value=1, required=False)
    comment_id = forms.IntegerField(min_value=1, required=False)
    name = forms.CharField(max_length=200, required=False)
    email = forms.EmailField(required=False)
    text = forms.CharField(max_length=3000)

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("parent_id") and not cleaned.get("comment_id"):
            self.add_error("parent_id", t("books.validation.parent_comment_required"))
        return cleaned


class RatingForm(StrictForm):
    book_id = forms.IntegerField(min_value=1)
    rating = forms.IntegerField(min_value=1, max_value=5)


class AdminBookForm(StrictForm):
    title = forms.CharField(max_length=255)
    author = forms.CharField(max_length=255)
    translator = forms.CharField(max_length=255, required=False)
    publisher = forms.CharField(max_length=255, required=False)
    library = forms.CharField(max_length=255, required=False)
    category_id = forms.IntegerField(min_value=1, required=False)
    nbok_category_id = forms.IntegerField(min_value=1, required=False)
    nbok_category_level = forms.ChoiceField(
        choices=[(f"L{i}", f"L{i}") for i in range(1, 7)], required=False,
    )
    summary = forms.CharField(max_length=20000, required=False)
    cover_url = forms.URLField(max_length=1000, required=False)
    physical_count = forms.IntegerField(min_value=0, max_value=10000, required=False, initial=0)
    physical_location = forms.CharField(max_length=200, required=False)
    tags = forms.CharField(max_length=5000, required=False, initial="[]")
    book_type = forms.ChoiceField(choices=[("physical", "physical"), ("pdf", "pdf"), ("both", "both")])
    cover = forms.FileField(required=False)
    book_pdf = forms.FileField(required=False)

    def clean_tags(self):
        import json
        raw = self.cleaned_data.get("tags") or "[]"
        try:
            value = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise forms.ValidationError(t("books.validation.tags_invalid")) from exc
        if not isinstance(value, list) or len(value) > 50:
            raise forms.ValidationError(t("books.validation.tags_too_many"))
        result = []
        for item in value:
            text = str(item).strip()
            if text:
                if len(text) > 100:
                    raise forms.ValidationError(t("books.validation.tag_too_long"))
                result.append(text)
        return result

    def clean(self):
        cleaned = super().clean()
        book_type = cleaned.get("book_type")
        count = cleaned.get("physical_count") or 0
        if book_type in {"physical", "both"} and count < 1:
            self.add_error("physical_count", t("books.validation.physical_count_required"))
        return cleaned


class CategoryMutationForm(StrictForm):
    name = forms.CharField(max_length=100)
    parent_id = forms.IntegerField(min_value=1, required=False)


class NBOKCategoryCreateForm(StrictForm):
    name = forms.CharField(max_length=255)
    parent_row_id = forms.IntegerField(min_value=1, required=False)
    parent_level = forms.ChoiceField(
        choices=[(f"L{i}", f"L{i}") for i in range(1, 7)], required=False,
    )


class SendBookLinkForm(StrictForm):
    book_id = forms.IntegerField(min_value=1)
    email = forms.EmailField(max_length=254)


class AdminAnswerForm(StrictForm):
    answer = forms.CharField(max_length=5000)


class AdminCommentReplyForm(StrictForm):
    response = forms.CharField(max_length=5000, required=False)
    reply = forms.CharField(max_length=5000, required=False)

    def clean(self):
        cleaned = super().clean()
        value = (cleaned.get("response") or cleaned.get("reply") or "").strip()
        if not value:
            self.add_error("response", t("books.validation.response_required"))
        cleaned["text"] = value
        return cleaned


class AdminResponseForm(StrictForm):
    response = forms.CharField(max_length=5000, required=False)


class PhysicalApprovalForm(StrictForm):
    request_id = forms.IntegerField(min_value=1)
    borrow_date = forms.DateField(input_formats=["%Y-%m-%d"])
    return_date = forms.DateField(input_formats=["%Y-%m-%d"])
    notes = forms.CharField(max_length=2000, required=False)

    def clean(self):
        cleaned = super().clean()
        borrow_date = cleaned.get("borrow_date")
        return_date = cleaned.get("return_date")
        if borrow_date and return_date and return_date < borrow_date:
            self.add_error("return_date", t("books.validation.return_before_borrow"))
        return cleaned


class OptionalBooleanField(forms.Field):
    def to_python(self, value):
        if value in (None, ""):
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "on"}:
                return True
            if normalized in {"false", "0", "no", "off"}:
                return False
        raise forms.ValidationError(t("books.validation.boolean_invalid"))


class AdminUserUpdateForm(StrictForm):
    username = forms.CharField(max_length=150)
    email = forms.EmailField(max_length=254)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    phone = forms.CharField(max_length=20, required=False)
    is_active = OptionalBooleanField(required=False)
    is_staff = OptionalBooleanField(required=False)


class AdminPasswordForm(StrictForm):
    password = forms.CharField(min_length=8, max_length=128)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_password(self):
        from django.contrib.auth.password_validation import validate_password

        password = self.cleaned_data["password"]
        validate_password(password, self.user)
        return password
