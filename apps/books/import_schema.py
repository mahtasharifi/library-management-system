"""Spreadsheet columns accepted by book imports."""

HEADER_MAP = {
    "عنوان": "title",
    "نام کتاب": "title",
    "نویسنده": "author",
    "مؤلف": "author",
    "مترجم": "translator",
    "ناشر": "publisher",
    "کتابخانه": "library",
    "کتابخانه": "library",
    "دسته‌بندی": "category",
    "دسته بندی": "category",
    "خلاصه": "summary",
    "تگ‌ها": "tags",
    "برچسب‌ها": "tags",
    "تعداد نسخه فیزیکی": "physical_count",
    "تعداد": "physical_count",
    "محل نگهداری": "physical_location",
    "لینک عکس جلد": "cover_url",
    "عکس جلد": "cover_url",
}
