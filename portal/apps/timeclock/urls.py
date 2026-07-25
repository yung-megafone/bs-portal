from django.urls import path

from . import views

app_name = "timeclock"

urlpatterns = [
    path("", views.timeclock_home, name="home"),
    path("punch/", views.punch_action, name="punch"),
    path(
        "punch/<uuid:punch_id>/correct/",
        views.correct_punch_view,
        name="correct",
    ),
]
