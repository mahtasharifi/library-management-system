"""Public catalog and request views."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from common.i18n import translate as t

from ..forms import (
    CommentForm,
    CommentReplyForm,
    ContactForm,
    DigitalBookRequestForm,
    PhysicalBookRequestForm,
    RatingForm,
)
from ..models import Book, BookComment
from ..repositories import catalog as catalog_repository
from ..services import catalog as catalog_service
from ..services import public as public_service
from ..services.request_data import form_errors, parse_json_object
from ..services.serialization import serialize_book
from ..services.downloads import can_download_book, public_pdf_url


DASHBOARD_ADMIN_GROUP = "Library Dashboard Admin"

def _staff_user(user):
    return (
        user.is_authenticated
        and (
            user.is_superuser
            or user.is_staff
            or user.groups.filter(name=DASHBOARD_ADMIN_GROUP).exists()
        )
    )


def _json_form(request, form_class):
    try:
        data = parse_json_object(request)
    except ValidationError as exc:
        return None, JsonResponse({"success": False, "message": "; ".join(exc.messages)}, status=400)
    form = form_class(data)
    if not form.is_valid():
        return None, JsonResponse({"success": False, "message": form_errors(form)}, status=400)
    return form, None


@login_required
def index(request):
    return render(
        request,
        "books/home.html",
        {"unread_notifications": request.user.library_notifications.filter(is_read=False).count()},
    )


@login_required
def book_catalog(request):
    search = request.GET.get("q", "").strip()[:255]
    category_value = request.GET.get("category", "").strip()
    availability = catalog_service.normalize_availability(request.GET.get("availability", ""))
    # The public taxonomy is NBOK-backed.  Keep the visual shelf server-rendered,
    # while the JSON collection endpoint remains separately bounded.
    category_tree = catalog_service.public_category_tree()
    categories = catalog_service.flatten_public_categories(category_tree)
    selected_category = catalog_service.find_public_category(category_tree, category_value)
    parsed_category = catalog_service.parse_public_category(category_value) if selected_category else None
    books = list(
        catalog_repository.filtered_books(
            search=search,
            nbok_row_id=parsed_category[0] if parsed_category else None,
            nbok_level=parsed_category[1] if parsed_category else None,
            availability=availability,
        )
    )
    for book in books:
        catalog_service.apply_shelf_metadata(book)
    query_without_page = request.GET.copy()
    query_without_page.pop("page", None)
    return render(
        request,
        "books/catalog.html",
        {
            "books": books,
            "categories": categories,
            "selected_category": selected_category,
            "search_query": search,
            "availability": availability,
            "query_without_page": query_without_page.urlencode(),
            "unread_notifications": request.user.library_notifications.filter(is_read=False).count(),
        },
    )


@login_required
def book_detail(request, book_id):
    context = catalog_service.book_detail_context(book_id, request.user)
    context["unread_notifications"] = request.user.library_notifications.filter(is_read=False).count()
    return render(request, "books/detail.html", context)


@login_required
@require_GET
def book_pdf_download(request, book_id):
    book = Book.objects.filter(pk=book_id).only("id", "title", "pdf_url").first()
    if not book or not can_download_book(request.user, book):
        raise Http404
    try:
        target = public_pdf_url(book)
    except ValidationError:
        return JsonResponse({"detail": t("books.api.secure_pdf_not_ready")}, status=503)
    response = redirect(target)
    response["Cache-Control"] = "private, no-store"
    response["Referrer-Policy"] = "no-referrer"
    return response


@user_passes_test(_staff_user, login_url="/accounts/login/")
def dashboard(request):
    return render(request, "books/admin/dashboard.html")


@user_passes_test(_staff_user, login_url="/accounts/login/")
def upload_view(request):
    return render(request, "books/admin/upload.html")


@login_required
@require_GET
def api_books(request):
    search = request.GET.get("search", "").strip()[:255]
    category_value = request.GET.get("category", "").strip()
    parsed_category = catalog_service.parse_public_category(category_value)
    legacy_category_id = catalog_service.parse_category_id(category_value) if parsed_category is None else None
    availability = catalog_service.normalize_availability(request.GET.get("availability", ""))
    try:
        page = max(1, int(request.GET.get("page", 1)))
        page_size = min(catalog_service.API_PAGE_SIZE_MAX, max(1, int(request.GET.get("page_size", catalog_service.API_PAGE_SIZE_DEFAULT))))
    except (TypeError, ValueError):
        page, page_size = 1, catalog_service.API_PAGE_SIZE_DEFAULT
    queryset = catalog_repository.filtered_books(
        search=search,
        category_id=legacy_category_id,
        nbok_row_id=parsed_category[0] if parsed_category else None,
        nbok_level=parsed_category[1] if parsed_category else None,
        availability=availability,
    )
    from django.core.paginator import Paginator

    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(page)
    parent_map = catalog_repository.category_parent_map()
    return JsonResponse(
        {
            "success": True,
            "data": [serialize_book(book, parent_map) for book in page_obj.object_list],
            "total_pages": paginator.num_pages,
            "current_page": page_obj.number,
            "total_count": paginator.count,
            "page_size": page_size,
        }
    )


@login_required
@require_GET
def api_categories(request):
    return JsonResponse({"success": True, "data": catalog_service.public_category_tree()})


@login_required
@require_POST
def api_request_book(request):
    form, error = _json_form(request, DigitalBookRequestForm)
    if error:
        return error
    try:
        record = public_service.request_digital_book(
            request.user,
            book_id=form.cleaned_data["book_id"],
            email=form.cleaned_data.get("email"),
            request=request,
        )
    except Book.DoesNotExist:
        return JsonResponse({"success": False, "message": t("books.api.book_not_found")}, status=404)
    except ValidationError as exc:
        return JsonResponse({"success": False, "message": "; ".join(exc.messages)}, status=400)
    return JsonResponse({"success": True, "message": t("books.api.digital_request_created"), "request_id": record.id})


@login_required
@require_POST
def api_request_physical_book(request):
    form, error = _json_form(request, PhysicalBookRequestForm)
    if error:
        return error
    try:
        record, is_available = public_service.request_physical_book(
            request.user,
            book_id=form.cleaned_data["book_id"],
            name=form.cleaned_data.get("name", ""),
            email=form.cleaned_data.get("email"),
            phone=form.cleaned_data["phone"],
            message=form.cleaned_data.get("message", ""),
        )
    except Book.DoesNotExist:
        return JsonResponse({"success": False, "message": t("books.api.book_not_found")}, status=404)
    except ValidationError as exc:
        return JsonResponse({"success": False, "message": "; ".join(exc.messages)}, status=400)
    message = t("books.api.physical_request_created") if is_available else t("books.api.physical_request_unavailable")
    return JsonResponse({"success": True, "message": message, "request_id": record.id})


@login_required
@require_POST
def api_contact(request):
    form, error = _json_form(request, ContactForm)
    if error:
        return error
    try:
        record = public_service.create_contact_message(request.user, form.cleaned_data)
    except ValidationError as exc:
        return JsonResponse({"success": False, "message": "; ".join(exc.messages)}, status=400)
    return JsonResponse({"success": True, "message": t("books.api.contact_created"), "message_id": record.id})


@login_required
@require_POST
def api_comments(request):
    form, error = _json_form(request, CommentForm)
    if error:
        return error
    try:
        comment = public_service.create_comment(
            request.user,
            book_id=form.cleaned_data["book_id"],
            name=form.cleaned_data.get("name", ""),
            email=form.cleaned_data.get("email"),
            text=form.cleaned_data["normalized_text"],
        )
    except Book.DoesNotExist:
        return JsonResponse({"success": False, "message": t("books.api.book_not_found")}, status=404)
    except ValidationError as exc:
        return JsonResponse({"success": False, "message": "; ".join(exc.messages)}, status=400)
    return JsonResponse({"success": True, "message": t("books.api.comment_created"), "comment_id": comment.id})


@login_required
@require_GET
def api_comments_list(request, book_id):
    book = Book.objects.filter(pk=book_id).first()
    if not book:
        return JsonResponse({"success": False, "message": t("books.api.book_not_found")}, status=404)
    queryset = BookComment.objects.filter(book=book, is_approved=True).select_related("parent").order_by("created_at")[:200]
    data = [
        {
            "id": item.id,
            "name": item.name,
            "comment": item.comment,
            "parent_id": item.parent_id,
            "created_at": item.created_at.isoformat(),
        }
        for item in queryset
    ]
    return JsonResponse({"success": True, "data": data})


@login_required
@require_POST
def api_comments_reply(request):
    form, error = _json_form(request, CommentReplyForm)
    if error:
        return error
    try:
        reply = public_service.create_comment_reply(
            request.user,
            parent_id=form.cleaned_data.get("parent_id") or form.cleaned_data.get("comment_id"),
            name=form.cleaned_data.get("name", ""),
            email=form.cleaned_data.get("email"),
            text=form.cleaned_data["text"],
        )
    except BookComment.DoesNotExist:
        return JsonResponse({"success": False, "message": t("books.api.parent_comment_not_found")}, status=404)
    except ValidationError as exc:
        return JsonResponse({"success": False, "message": "; ".join(exc.messages)}, status=400)
    return JsonResponse({"success": True, "message": t("books.api.reply_created"), "comment_id": reply.id})


@require_POST
def api_rate_book(request):
    if not request.user.is_authenticated:
        return JsonResponse({"success": False, "message": t("books.api.rating_login_required")}, status=401)
    form, error = _json_form(request, RatingForm)
    if error:
        return error
    try:
        result = public_service.rate_book(
            request.user,
            book_id=form.cleaned_data["book_id"],
            rating=form.cleaned_data["rating"],
            request=request,
        )
    except Book.DoesNotExist:
        return JsonResponse({"success": False, "message": t("books.api.book_not_found")}, status=404)
    return JsonResponse({"success": True, "message": t("books.api.rating_created"), **result})
