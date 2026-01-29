"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path
from api.api import api

from core import views as core_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    path("", core_views.index, name="index"),
    path("login/", core_views.user_login, name="login"),
    path("logout/", core_views.user_logout, name="logout"),
    path("dashboard/", core_views.dashboard, name="dashboard"),
    path("dashboard/builder/", core_views.builder, name="builder"),
    path("dashboard/reports/", core_views.reports, name="reports"),
    path("dashboard/compare/", core_views.comparison, name="compare"),
    path("dashboard/scenarios/", core_views.scenarios, name="scenarios"),
    path("dashboard/database/", core_views.database, name="database"),
]
