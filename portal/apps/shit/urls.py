from django.urls import path

from . import views

app_name = "shit"

urlpatterns = [
    path("", views.ticket_list, name="list"),
    path("new/", views.ticket_create, name="create"),
    path(
        "<str:ticket_number>/board-move/",
        views.ticket_board_move,
        name="board_move",
    ),
    path("<str:ticket_number>/", views.ticket_detail, name="detail"),
    path("<str:ticket_number>/manage/", views.ticket_manage, name="manage"),
    path("<str:ticket_number>/comment/", views.ticket_comment, name="comment"),
    path(
        "<str:ticket_number>/attachment/",
        views.ticket_attachment,
        name="attachment",
    ),
]
