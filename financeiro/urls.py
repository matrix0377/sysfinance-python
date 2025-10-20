from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('contas/', views.contas, name='contas'),
    path('transacoes/', views.transacoes, name='transacoes'),
    path('metas/', views.metas, name='metas'),
    path('usuarios/', views.usuarios, name='usuarios'),
    path('relatorios/', views.relatorios, name='relatorios'),
    path('logs/', views.logs, name='logs'),
]
