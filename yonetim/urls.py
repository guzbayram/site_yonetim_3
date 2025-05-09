from django.urls import path
from . import views

app_name = 'yonetim'

urlpatterns = [
    path('', views.giris, name='giris'),
    path('kayit/', views.kayit, name='kayit'),
    path('site-bilgi/', views.site_bilgi, name='site_bilgi'),
    path('panel/', views.panel, name='panel'),
    path('cikis/', views.cikis, name='cikis'),
    path('ajax/bloklar/', views.ajax_bloklar, name='ajax_bloklar'),
    path('ajax/daireler/', views.ajax_daireler, name='ajax_daireler'),
    # Daire ödeme detay sayfası için URL (Bu zaten vardı ve kullanışlı)
    path('odeme-detay/daire/<int:daire_id>/', views.daire_odeme_detay, name='daire_odeme_detay'),
]