"""
URL routing for Library books app.
"""
from django.urls import path
from django.contrib.auth.decorators import login_required
from . import views
urlpatterns = [
    path('', login_required(views.index), name='index'),                       
    path('books/', views.book_catalog, name='book_catalog'),
    path('books/<int:book_id>/', views.book_detail, name='book_detail'),
    path('books/<int:book_id>/download/', views.book_pdf_download, name='book_pdf_download'),
    path('dashboard/', login_required(views.dashboard), name='dashboard'),  
    path('upload/', login_required(views.upload_view), name='upload'),         
    # Public API
    path('api/books/', views.api_books, name='api_books'),                   
    path('api/categories/', views.api_categories, name='api_categories'),     
    path('api/request-book/', views.api_request_book, name='api_request_book'),
    path('api/request-physical-book/', views.api_request_physical_book, name='api_request_physical_book'), 
    path('api/contact/', views.api_contact, name='api_contact'),            
    # Comments and ratings
    path('api/comments/', views.api_comments, name='api_comments'),          
    path('api/comments/<int:book_id>/', views.api_comments_list, name='api_comments_list'), 
    path('api/comments/reply/', views.api_comments_reply, name='api_comments_reply'),   
    path('api/rate-book/', views.api_rate_book, name='api_rate_book'),        
    # Uploads
    path('api/upload/', views.api_upload, name='api_upload'),                  
    # Admin dashboard
    path('api/admin/dashboard/', views.api_admin_dashboard, name='api_admin_dashboard'),  
    # Book administration
    path('api/admin/books/', views.api_admin_books, name='api_admin_books'),
    path('api/admin/books/<int:book_id>/', views.api_admin_book_detail, name='api_admin_book_detail'), 
    path('api/admin/books/add/', views.api_admin_book_add, name='api_admin_book_add'),               
    path('api/admin/books/<int:book_id>/update/', views.api_admin_book_update, name='api_admin_book_update'), 
    path('api/admin/books/<int:book_id>/delete/', views.api_admin_book_delete, name='api_admin_book_delete'), 
    path('api/admin/books/import/', views.api_admin_books_import, name='api_admin_books_import'),             
    path('api/admin/book-imports/<int:job_id>/', views.api_admin_import_job, name='api_admin_import_job'),
    path('api/admin/books/import-template/', views.api_admin_physical_import_template, name='api_admin_physical_import_template'),
    path('api/admin/send-book-link/', views.api_admin_send_book_link, name='api_admin_send_book_link'),       
    # Physical-book request administration
    path('api/admin/physical-book-requests/', views.api_admin_physical_requests, name='api_admin_physical_requests'),
    path('api/admin/physical-book-requests/mark-read/', views.api_admin_physical_requests_mark_read, name='api_admin_physical_requests_mark_read'),   
    path('api/admin/physical-book-requests/approve/', views.api_admin_approve_physical_request, name='api_admin_approve_physical_request'),
    path('api/admin/physical-book-requests/<int:request_id>/reject/', views.api_admin_reject_physical_request, name='api_admin_reject_physical_request'), 
    path('api/admin/borrowed-books/', views.api_admin_borrowed_books, name='api_admin_borrowed_books'),             
    path('api/admin/books/<int:book_id>/borrow-history/', views.api_admin_borrow_history, name='api_admin_borrow_history'),
    path('api/admin/books/<int:borrow_id>/return/', views.api_admin_return_book, name='api_admin_return_book'),        

    # Digital-book request administration
    path('api/admin/book-requests/', views.api_admin_book_requests, name='api_admin_book_requests'),
    path('api/admin/book-requests/mark-read/', views.api_admin_book_requests_mark_read, name='api_admin_book_requests_mark_read'),                             
    path('api/admin/book-requests/pending-count/', views.api_admin_book_requests_pending_count, name='api_admin_book_requests_pending_count'), 
    path('api/admin/book-requests/<int:request_id>/approve/', views.api_admin_approve_book_request, name='api_admin_approve_book_request'),
    path('api/admin/book-requests/<int:request_id>/reject/', views.api_admin_reject_book_request, name='api_admin_reject_book_request'),  
    path('api/admin/book-requests/<int:request_id>/delete/', views.api_admin_book_request_delete, name='api_admin_book_request_delete'), 
    # Message administration
    path('api/admin/messages/', views.api_admin_messages, name='api_admin_messages'),                           
    path('api/admin/messages/<int:message_id>/mark-read/', views.api_admin_message_read, name='api_admin_message_read'), 
    path('api/admin/messages/<int:message_id>/reply/', views.api_admin_message_reply, name='api_admin_message_reply'),
    path('api/admin/messages/<int:message_id>/delete/', views.api_admin_message_delete, name='api_admin_message_delete'),
    path('api/admin/messages/unread-count/', views.api_admin_messages_unread_count, name='api_admin_messages_unread_count'),
    path('api/admin/unread-counts/', views.api_admin_unread_counts, name='api_admin_unread_counts'),
    # User administration
    path('api/admin/users/', views.api_admin_users, name='api_admin_users'),
    path('api/admin/users/<int:user_id>/update/', views.api_admin_user_update, name='api_admin_user_update'),
    path('api/admin/users/<int:user_id>/password/', views.api_admin_user_password, name='api_admin_user_password'),
    path('api/admin/users/<int:user_id>/delete/', views.api_admin_user_delete, name='api_admin_user_delete'),
    # Question administration
    path('api/admin/questions/', views.api_admin_questions, name='api_admin_questions'), 
    path('api/admin/questions/<int:question_id>/answer/', views.api_admin_question_answer, name='api_admin_question_answer'), 
    path('api/admin/questions/<int:question_id>/delete/', views.api_admin_question_delete, name='api_admin_question_delete'), 
    # Comment administration
    path('api/admin/comments/', views.api_admin_comments, name='api_admin_comments'), 
    path('api/admin/comments/<int:comment_id>/reply/', views.api_admin_comment_reply, name='api_admin_comment_reply'),
    path('api/admin/comments/<int:comment_id>/delete/', views.api_admin_comment_delete, name='api_admin_comment_delete'), 
    # Category administration
    path('api/admin/categories/', views.api_admin_categories, name='api_admin_categories'), 
    path('api/admin/categories/book-counts/', views.api_admin_categories_book_counts, name='api_admin_categories_book_counts'),
    path('api/admin/nbok/', views.api_admin_nbok, name='api_admin_nbok'),
    path('api/admin/nbok/create/', views.api_admin_nbok_create, name='api_admin_nbok_create'),
    path('api/admin/categories/create/', views.api_admin_category_create, name='api_admin_category_create'), 
    path('api/admin/categories/<int:category_id>/update/', views.api_admin_category_update, name='api_admin_category_update'), 
    path('api/admin/categories/<int:category_id>/delete/', views.api_admin_category_delete, name='api_admin_category_delete'), 
    # Borrow-history deletion
    path('api/admin/books/<int:borrow_id>/borrow-history/delete/', views.api_admin_borrow_history_delete, name='api_admin_borrow_history_delete'), 
    # Logout
    path('api/logout/', views.api_logout, name='api_logout'), 
]
