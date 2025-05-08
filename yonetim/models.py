from django.contrib.auth.models import AbstractUser
from django.db import models

# Kullanıcı modeli / User model
class Kullanici(AbstractUser):
    site_kodu = models.CharField(max_length=8, verbose_name="Site Kodu / Site Code")
    is_yonetici = models.BooleanField(default=False, verbose_name="Yönetici mi? / Is Manager?")

# Site modeli / Site model
class Site(models.Model):
    ad = models.CharField(max_length=100, verbose_name="Site Adı / Site Name")
    adres = models.CharField(max_length=255, verbose_name="Adres / Address")
    kod = models.CharField(max_length=8, unique=True, verbose_name="Site Kodu / Site Code")
    yonetici = models.ForeignKey(Kullanici, on_delete=models.CASCADE, verbose_name="Yönetici / Manager")
    yonetici_tel = models.CharField(max_length=20, blank=True, null=True, verbose_name="Yönetici Telefon / Manager Phone")
    aidat_miktari = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Aylık Aidat Miktarı")

    def __str__(self):
        return self.ad

# Blok modeli / Block model
class Blok(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='bloklar')
    ad = models.CharField(max_length=50, verbose_name="Blok Adı / Block Name")
    daire_sayisi = models.PositiveIntegerField(verbose_name="Daire Sayısı / Flat Count")

    def __str__(self):
        return f"{self.site.ad} - {self.ad}"

# Daire modeli / Flat model
class Daire(models.Model):
    blok = models.ForeignKey(Blok, on_delete=models.CASCADE, related_name='daireler')
    no = models.CharField(max_length=10, verbose_name="Daire No / Flat No")
    kullanici = models.ForeignKey(Kullanici, on_delete=models.SET_NULL, null=True, blank=True, related_name='daireleri')

    def __str__(self):
        return f"{self.blok.ad} - Daire {self.no}"

# Aidat modeli / Dues model
class Aidat(models.Model):
    daire = models.ForeignKey(Daire, on_delete=models.CASCADE, related_name='aidatlar')
    tutar = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Tutar / Amount")
    tarih = models.DateField(verbose_name="Tarih / Date")
    aciklama = models.CharField(max_length=255, blank=True, verbose_name="Açıklama / Description")

    def __str__(self):
        return f"{self.daire} - {self.tutar} TL ({self.tarih})"

# Gider modeli / Expense model
class Gider(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='giderler')
    tur = models.CharField(max_length=50, verbose_name="Gider Türü / Expense Type")
    tutar = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Tutar / Amount")
    tarih = models.DateField(verbose_name="Tarih / Date")
    aciklama = models.CharField(max_length=255, blank=True, verbose_name="Açıklama / Description")

    def __str__(self):
        return f"{self.site.ad} - {self.tur} - {self.tutar} TL"