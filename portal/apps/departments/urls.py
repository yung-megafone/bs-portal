from django.urls import path

from .views import department_list

app_name = "departments"

urlpatterns = [
    path("", department_list, name="list"),
]
