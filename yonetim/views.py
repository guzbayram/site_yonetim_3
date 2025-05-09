from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from .models import Site, Kullanici, Blok, Daire, Aidat, Gider
from django.contrib import messages
from django.http import JsonResponse
import re
from decimal import Decimal, InvalidOperation
from django.contrib.auth.decorators import login_required
from django.db import transaction, IntegrityError
from django.db.models import Sum
from django.utils import timezone
from datetime import date 
import logging
import uuid 

logger = logging.getLogger(__name__)

# --- HELPER FONKSİYONLAR ---
def daire_natural_sort_key(daire_obj):
    return (daire_obj.blok.ad.lower(), daire_obj.get_sortable_daire_no())

def get_user_daire(user, site_kodu_user):
    if user.is_authenticated:
        try:
            return Daire.objects.filter(kullanici=user, blok__site__kod=site_kodu_user).select_related('blok', 'blok__site').first()
        except Daire.DoesNotExist:
            return None
    return None

def generate_unique_username(first_name, last_name, site_kodu):
    char_map = {
        'ı': 'i', 'İ': 'I', 'ö': 'o', 'Ö': 'O', 'ü': 'u', 'Ü': 'U',
        'ş': 's', 'Ş': 'S', 'ç': 'c', 'Ç': 'C', 'ğ': 'g', 'Ğ': 'G'
    }
    clean_first_name = first_name.lower()
    clean_last_name = last_name.lower()
    for tr_char, en_char in char_map.items():
        clean_first_name = clean_first_name.replace(tr_char, en_char)
        clean_last_name = clean_last_name.replace(tr_char, en_char)
    
    clean_first_name = re.sub(r'\W+', '', clean_first_name)
    clean_last_name = re.sub(r'\W+', '', clean_last_name)

    base_username = f"{clean_first_name}{clean_last_name}_{site_kodu.lower()}"
    max_len_for_base = 150 - (6 + 1) 
    username_candidate = base_username[:max_len_for_base]
    
    final_username_try = f"{username_candidate}_{uuid.uuid4().hex[:6]}"
    counter = 1
    original_final_username_base = username_candidate
    while Kullanici.objects.filter(username=final_username_try).exists():
        new_uuid_part = uuid.uuid4().hex[:6]
        final_username_try = f"{original_final_username_base[:150-(len(new_uuid_part)+1)]}_{new_uuid_part}"
        counter += 1
        if counter > 100:
            raise Exception("Benzersiz kullanıcı adı üretilemedi (çok fazla çakışma).")
            
    return final_username_try[:150]

# --- VIEW FONKSİYONLARI ---

@login_required
def panel(request):
    try:
        site = Site.objects.get(kod=request.user.site_kodu)
    except Site.DoesNotExist:
        messages.error(request, "Site bulunamadı. Lütfen site kodunuzu kontrol edin veya bir yönetici ile iletişime geçin.")
        logout(request)
        return redirect('yonetim:giris')

    kullanici_kendi_dairesi = get_user_daire(request.user, request.user.site_kodu)
    aidat_ekleme_goster = bool(kullanici_kendi_dairesi)

    if request.method == 'POST':
        if 'aidat_ekle' in request.POST:
            if not kullanici_kendi_dairesi:
                messages.error(request, "Aidat eklenecek bir daireniz bulunmamaktadır.")
                return redirect('yonetim:panel')
            
            tutar_str = request.POST.get('tutar', str(site.aidat_miktari if site.aidat_miktari is not None else '0.00'))
            aciklama = request.POST.get('aciklama', '')
            makbuz = request.FILES.get('makbuz_aidat')

            try:
                daire_nesnesi = kullanici_kendi_dairesi
                tutar = Decimal(tutar_str.replace(',', '.'))
                Aidat.objects.create(
                    daire=daire_nesnesi, tutar=tutar, tarih=timezone.now().date(),
                    aciklama=aciklama, makbuz=makbuz
                )
                messages.success(request, f"{daire_nesnesi.daire_tam_adi} için aidat başarıyla eklendi.")
            except (ValueError, InvalidOperation):
                messages.error(request, "Geçersiz tutar formatı.")
            except Exception as e:
                logger.error(f"Panel - Aidat ekleme hatası: {e}", exc_info=True)
                messages.error(request, f"Aidat eklenirken bir hata oluştu: {e}")
            return redirect('yonetim:panel')

        elif 'gider_ekle' in request.POST:
            if not request.user.is_yonetici:
                messages.error(request, "Gider ekleme yetkiniz yok.")
                return redirect('yonetim:panel')

            tur = request.POST.get('tur')
            tutar_str = request.POST.get('tutar')
            aciklama = request.POST.get('aciklama', '')
            makbuz = request.FILES.get('makbuz_gider')

            if not all([tur, tutar_str]):
                messages.error(request, "Gider türü ve tutar alanları zorunludur.")
            else:
                try:
                    tutar = Decimal(tutar_str.replace(',', '.'))
                    Gider.objects.create(
                        site=site, tur=tur, tutar=tutar, tarih=timezone.now().date(),
                        aciklama=aciklama, makbuz=makbuz
                    )
                    messages.success(request, "Gider başarıyla eklendi.")
                except (ValueError, InvalidOperation):
                    messages.error(request, "Geçersiz tutar formatı.")
                except Exception as e:
                    logger.error(f"Panel - Gider ekleme hatası: {e}", exc_info=True)
                    messages.error(request, f"Gider eklenirken bir hata oluştu: {e}")
            return redirect('yonetim:panel')

    # Panel Üstü Genel Toplamlar
    toplam_gelir_aidatlar = Aidat.objects.filter(daire__blok__site=site).aggregate(toplam=Sum('tutar'))['toplam'] or Decimal('0.00')
    toplam_giderler = Gider.objects.filter(site=site).aggregate(toplam=Sum('tutar'))['toplam'] or Decimal('0.00')
    kasa_bakiyesi = toplam_gelir_aidatlar - toplam_giderler

    # "Daire Aidat Özetleri" Sekmesi için Veri Hazırlama
    daire_aidat_ozetleri = []
    tum_daireler_qs = Daire.objects.filter(blok__site=site).select_related('blok', 'kullanici')
    daireler_listesi_sirali = sorted(list(tum_daireler_qs), key=daire_natural_sort_key)

    current_year = timezone.now().year
    yillik_aidat_borcu_bir_daire_icin = (site.aidat_miktari * 12) if site.aidat_miktari else Decimal('0.00')

    for daire_obj in daireler_listesi_sirali:
        start_of_year = date(current_year, 1, 1)
        end_of_year = date(current_year, 12, 31)

        bu_yil_odenen_tutar = Aidat.objects.filter(
            daire=daire_obj,
            tarih__gte=start_of_year,
            tarih__lte=end_of_year
        ).aggregate(toplam_odenen=Sum('tutar'))['toplam_odenen'] or Decimal('0.00')
        
        bakiye = yillik_aidat_borcu_bir_daire_icin - bu_yil_odenen_tutar

        daire_aidat_ozetleri.append({
            'daire': daire_obj,
            'blok_daire': f"{daire_obj.blok.ad.upper()} - {daire_obj.daire_no}",
            'sakin': daire_obj.kullanici.get_full_name() if daire_obj.kullanici else "Boş",
            'yillik_borc': yillik_aidat_borcu_bir_daire_icin,
            'odenen': bu_yil_odenen_tutar,
            'bakiye': bakiye,
            'is_current_user_flat': kullanici_kendi_dairesi and daire_obj.id == kullanici_kendi_dairesi.id
        })
    
    if not request.user.is_yonetici and kullanici_kendi_dairesi:
        kendi_daire_ozeti = next((item for item in daire_aidat_ozetleri if item['daire'].id == kullanici_kendi_dairesi.id), None)
        if kendi_daire_ozeti:
            daire_aidat_ozetleri.remove(kendi_daire_ozeti)
            daire_aidat_ozetleri.insert(0, kendi_daire_ozeti)

    context = {
        'site': site,
        'kullanici_kendi_dairesi': kullanici_kendi_dairesi,
        'aidat_ekleme_goster': aidat_ekleme_goster,
        'current_year': current_year,
        
        'toplam_gelir_aidatlar': toplam_gelir_aidatlar,
        'toplam_giderler': toplam_giderler,
        'kasa_bakiyesi': kasa_bakiyesi,

        'daire_aidat_ozet_listesi': daire_aidat_ozetleri, # Bu, "Daire Aidat Özetleri" sekmesi için

        # "Tüm Aidat Kayıtları" sekmesi için (q1.jpg'deki gibi)
        'genel_aidat_kayitlari': Aidat.objects.filter(daire__blok__site=site).select_related('daire__blok', 'daire__kullanici').order_by('-tarih', '-id')[:50] if request.user.is_yonetici else [],
        # "Site Gider Listesi" sekmesi için
        'genel_gider_listesi': Gider.objects.filter(site=site).order_by('-tarih', '-id')[:50] if request.user.is_yonetici else [],
    }
    return render(request, 'yonetim/panel.html', context)

# ... (daire_odeme_detay, giris, kayit, site_bilgi, cikis, ajax_bloklar, ajax_daireler fonksiyonları önceki yanıttaki gibi kalır)
# Bu fonksiyonların en son güncel hallerini bir önceki yanıttan alabilirsiniz.
# ÖNEMLİ: Bu fonksiyonların güncel hallerini buraya KOPYALAMANIZ GEREKİR.
# Sadece panel fonksiyonu yukarıda güncellenmiştir.

@login_required
def daire_odeme_detay(request, daire_id):
    # ... (önceki tam yanıttaki gibi) ...
    try:
        daire = get_object_or_404(Daire.objects.select_related('blok__site', 'kullanici'),
                                  id=daire_id, blok__site__kod=request.user.site_kodu)
    except Daire.DoesNotExist:
        messages.error(request, "Belirtilen daire bulunamadı veya erişim yetkiniz yok.")
        return redirect('yonetim:panel')

    if not (request.user.is_yonetici or (daire.kullanici == request.user)):
        messages.error(request, "Bu ödeme detaylarını görüntüleme yetkiniz yok.")
        return redirect('yonetim:panel')

    aidatlar = Aidat.objects.filter(daire=daire).order_by('-tarih', '-id')
    toplam_odenen_aidat = aidatlar.aggregate(toplam=Sum('tutar'))['toplam'] or Decimal('0.00')

    context = {
        'daire_nesnesi': daire,
        'aidatlar': aidatlar,
        'toplam_odenen_aidat': toplam_odenen_aidat,
        'kalan_borc_hesaplanmadi': True, 
        'site': daire.blok.site
    }
    return render(request, 'yonetim/daire_odeme_detay.html', context)

def giris(request):
    # ... (önceki tam yanıttaki gibi) ...
    if request.user.is_authenticated:
        return redirect('yonetim:panel')
    form_data = {} 
    if request.method == 'POST':
        form_data = request.POST.copy()
        first_name = form_data.get('first_name', '').strip()
        last_name = form_data.get('last_name', '').strip()
        site_kodu_giris = form_data.get('site_kodu', '').strip().upper()
        blok_adi_giris = form_data.get('blok_adi', '').strip().upper() 
        daire_no_giris = form_data.get('daire_no', '').strip()
        password_giris = form_data.get('password')
        if not all([first_name, last_name, site_kodu_giris, blok_adi_giris, daire_no_giris, password_giris]):
            messages.error(request, "Tüm alanların doldurulması zorunludur.")
            return render(request, 'yonetim/giris.html', {'form_data': form_data})
        user_to_auth = None
        try:
            daire_qs = Daire.objects.select_related('kullanici', 'blok__site').filter(
                blok__site__kod=site_kodu_giris, blok__ad__iexact=blok_adi_giris, 
                daire_no__iexact=daire_no_giris, kullanici__is_active=True,
                kullanici__first_name__iexact=first_name, kullanici__last_name__iexact=last_name )
            matching_daire = daire_qs.first()
            if matching_daire and matching_daire.kullanici:
                user_to_auth = authenticate(request, username=matching_daire.kullanici.username, password=password_giris)
            if user_to_auth is not None:
                login(request, user_to_auth); return redirect('yonetim:panel')
            else: messages.error(request, "Giriş bilgileri hatalı veya kullanıcı aktif değil/bulunamadı.")
        except Exception as e: messages.error(request, f"Giriş sırasında bir hata oluştu: {e}"); logger.error(f"Giriş hatası: {e}", exc_info=True)
        return render(request, 'yonetim/giris.html', {'form_data': form_data})
    return render(request, 'yonetim/giris.html', {'form_data': form_data})

@transaction.atomic
def kayit(request):
    # ... (önceki tam yanıttaki gibi - generate_unique_username kullanarak) ...
    if request.user.is_authenticated: return redirect('yonetim:panel')
    form_data = {}
    if request.method == 'POST':
        form_data = request.POST.copy()
        password = form_data.get('password'); password_confirm = form_data.get('password_confirm')
        first_name = form_data.get('first_name', '').strip(); last_name = form_data.get('last_name', '').strip()
        role = form_data.get('rol'); site_kodu_form = form_data.get('site_kodu', '').strip().upper()
        sakin_blok_id = form_data.get('sakin_blok_id'); sakin_daire_id = form_data.get('sakin_daire_id')
        if not all([password, password_confirm, first_name, last_name, role, site_kodu_form]):
            messages.error(request, "Lütfen tüm zorunlu alanları doldurun."); return render(request, 'yonetim/kayit.html', {'form_data': form_data})
        if password != password_confirm:
            messages.error(request, "Parolalar eşleşmiyor."); return render(request, 'yonetim/kayit.html', {'form_data': form_data}) 
        try: generated_username = generate_unique_username(first_name, last_name, site_kodu_form)
        except Exception as e: messages.error(request, str(e)); return render(request, 'yonetim/kayit.html', {'form_data': form_data})
        generated_email = f"{generated_username}@otomatikkayit.placeholder" 
        is_yonetici_flag = (role == 'yonetici'); site_nesnesi = None
        if is_yonetici_flag:
            if Site.objects.filter(kod=site_kodu_form).exists():
                messages.error(request, f"'{site_kodu_form}' kodlu site mevcut."); return render(request, 'yonetim/kayit.html', {'form_data': form_data})
        else: 
            try: site_nesnesi = Site.objects.get(kod=site_kodu_form)
            except Site.DoesNotExist: messages.error(request, f"'{site_kodu_form}' kodlu site bulunamadı."); return render(request, 'yonetim/kayit.html', {'form_data': form_data})
            if not sakin_blok_id or not sakin_daire_id: messages.error(request, "Sakin için blok/daire seçimi zorunlu."); return render(request, 'yonetim/kayit.html', {'form_data': form_data})
        try:
            user = Kullanici.objects.create_user(username=generated_username, email=generated_email, password=password, first_name=first_name, last_name=last_name, site_kodu=site_kodu_form, is_yonetici=is_yonetici_flag)
            if is_yonetici_flag:
                messages.success(request, f"Yönetici olarak kayıt oldunuz. '{site_kodu_form}' için site bilgilerinizi girin.")
                login(request, user); return redirect('yonetim:site_bilgi') 
            else: 
                daire_nesnesi = Daire.objects.get(id=sakin_daire_id, blok_id=sakin_blok_id, blok__site=site_nesnesi)
                if daire_nesnesi.kullanici is not None:
                    user.delete(); messages.error(request, f"{daire_nesnesi.daire_tam_adi} dolu."); return render(request, 'yonetim/kayit.html', {'form_data': form_data})
                daire_nesnesi.kullanici = user; daire_nesnesi.save()
                messages.success(request, f"Sakin olarak kayıt oldunuz: {daire_nesnesi.daire_tam_adi}")
                login(request, user); return redirect('yonetim:panel')
        except Daire.DoesNotExist:
            if 'user' in locals() and hasattr(user, 'pk') and user.pk: user.delete()
            messages.error(request, "Seçilen daire/blok geçersiz."); return render(request, 'yonetim/kayit.html', {'form_data': form_data})
        except IntegrityError as e: logger.error(f"Kayıt IntegrityError: {e}", exc_info=True); messages.error(request, "Kayıt hatası (IE)."); return render(request, 'yonetim/kayit.html', {'form_data': form_data})
        except Exception as e:
            logger.error(f"Kayıt Genel Hata: {e}", exc_info=True)
            if 'user' in locals() and hasattr(user, 'pk') and user.pk: user.delete()
            messages.error(request, f"Hata: {e}"); return render(request, 'yonetim/kayit.html', {'form_data': form_data})
    else: 
        site_kodu_get = request.GET.get('sitekodu', None)
        form_data = {'site_kodu': site_kodu_get} if site_kodu_get else {}
        if site_kodu_get: form_data['rol'] = 'sakin'
    return render(request, 'yonetim/kayit.html', {'form_data': form_data})

@login_required
@transaction.atomic
def site_bilgi(request):
    # ... (önceki tam yanıttaki gibi - yönetici daire seçimi ve blok/daire işlemleri) ...
    if not request.user.is_yonetici: messages.error(request, "Yetkiniz yok."); return redirect('yonetim:panel')
    site = None
    try:
        site = Site.objects.select_related('yonetici').get(kod=request.user.site_kodu)
        if not site.yonetici: site.yonetici = request.user; site.save()
    except Site.DoesNotExist: pass
    yoneticinin_mevcut_dairesi = Daire.objects.filter(blok__site=site, kullanici=request.user).first() if site else None
    form_data_get = site.__dict__ if site else {'kod': request.user.site_kodu if request.user.is_authenticated else ''}
    if site: form_data_get['ad'] = site.ad # __dict__ bazen _state gibi şeyler içerir, direkt alanları almak daha iyi

    if request.method == 'POST':
        site_ad = request.POST.get('site_adi','').strip(); site_adres = request.POST.get('site_adresi','').strip()
        yonetici_tel = request.POST.get('yonetici_tel','').strip(); aidat_miktari_s = request.POST.get('aidat_miktari','').strip()
        yonetici_daire_id = request.POST.get('yonetici_daire_secimi')
        blok_adlari = request.POST.getlist('blok_adi[]'); daire_sayilari_s = request.POST.getlist('daire_sayisi[]')
        if not site_ad or not site_adres: messages.error(request, "Site adı ve adres zorunlu."); return redirect('yonetim:site_bilgi')
        aidat_miktari_d = None
        if aidat_miktari_s:
            try: aidat_miktari_d = Decimal(aidat_miktari_s.replace(',','.'))
            except InvalidOperation: messages.error(request, "Geçersiz aidat miktarı."); return redirect('yonetim:site_bilgi')
        if site is None:
            site = Site.objects.create(ad=site_ad, adres=site_adres, kod=request.user.site_kodu, yonetici=request.user, yonetici_tel=yonetici_tel, aidat_miktari=aidat_miktari_d)
            messages.success(request, f"'{site.ad}' sitesi oluşturuldu.")
        else:
            site.ad=site_ad; site.adres=site_adres; site.yonetici_tel=yonetici_tel; site.aidat_miktari=aidat_miktari_d
            if not site.yonetici: site.yonetici = request.user
            site.save(); messages.success(request, "Site bilgileri güncellendi.")
        if yonetici_daire_id and site:
            if yonetici_daire_id == "bos_birak":
                if yoneticinin_mevcut_dairesi: yoneticinin_mevcut_dairesi.kullanici=None; yoneticinin_mevcut_dairesi.save(); messages.info(request, "Yönetici daire ataması kaldırıldı.")
            else:
                try:
                    sec_daire = Daire.objects.get(id=yonetici_daire_id, blok__site=site)
                    if sec_daire.kullanici is None or sec_daire.kullanici == request.user:
                        if yoneticinin_mevcut_dairesi and yoneticinin_mevcut_dairesi.id != sec_daire.id: yoneticinin_mevcut_dairesi.kullanici=None; yoneticinin_mevcut_dairesi.save()
                        sec_daire.kullanici = request.user; sec_daire.save(); messages.success(request, f"Yönetici '{sec_daire.daire_tam_adi}' dairesine atandı.")
                    else: messages.error(request, f"Seçilen daire ({sec_daire.daire_tam_adi}) başkasına ait.")
                except Daire.DoesNotExist: messages.error(request, "Yönetici için seçilen daire bulunamadı.")
        if site:
            mevcut_blok_idler = set(site.bloklar.values_list('id',flat=True)); islenen_blok_idler = set()
            for i, blok_ad_r in enumerate(blok_adlari):
                blok_ad_u = blok_ad_r.strip().upper()
                if not blok_ad_u: continue
                daire_s_s = daire_sayilari_s[i] if i < len(daire_sayilari_s) else None
                if blok_ad_u and daire_s_s:
                    try:
                        daire_s_i = int(daire_s_s)
                        if daire_s_i <= 0: messages.warning(request, f"'{blok_ad_u}' daire sayısı pozitif olmalı."); continue
                        blok_n, cr = Blok.objects.get_or_create(site=site, ad=blok_ad_u)
                        islenen_blok_idler.add(blok_n.id)
                        mevcut_daireler_d = {d.daire_no: d for d in blok_n.daireler.all()}
                        istenen_daireler_s = {str(j) for j in range(1, daire_s_i + 1)}
                        for d_no_yeni in istenen_daireler_s:
                            if d_no_yeni not in mevcut_daireler_d: Daire.objects.create(blok=blok_n, daire_no=d_no_yeni)
                        for d_no_eski, d_obj_eski in mevcut_daireler_d.items():
                            if d_no_eski not in istenen_daireler_s and d_obj_eski.kullanici is None: d_obj_eski.delete()
                            elif d_no_eski not in istenen_daireler_s and d_obj_eski.kullanici is not None: messages.warning(request, f"{blok_n.ad} - Daire {d_obj_eski.daire_no} dolu, silinemedi.")
                    except ValueError: messages.warning(request, f"'{blok_ad_u}' için geçersiz daire sayısı: '{daire_s_s}'.")
                    except Exception as e: logger.error(f"Blok/Daire: {e}", exc_info=True); messages.warning(request, f"'{blok_ad_u}' işlenirken sorun.")
            silinecek_idler = mevcut_blok_idler - islenen_blok_idler
            for blok_id_s in silinecek_idler:
                try:
                    blok_s = Blok.objects.get(id=blok_id_s, site=site)
                    if not blok_s.daireler.filter(kullanici__isnull=False).exists(): blok_s.delete()
                    else: messages.warning(request, f"'{blok_s.ad}' dolu, silinemedi.")
                except Blok.DoesNotExist: pass
        return redirect('yonetim:panel')

    bloklar_ve_daireleri_c = []
    sitedeki_bos_ve_yoneticiye_ait_d = []
    if site:
        for blok_db in site.bloklar.all().order_by('ad'):
            bloklar_ve_daireleri_c.append({'ad': blok_db.ad, 'id': blok_db.id, 'daire_sayisi': blok_db.daireler.count()})
        daire_q = Daire.objects.filter(blok__site=site).select_related('kullanici','blok')
        temp_d_list = sorted(list(daire_q), key=daire_natural_sort_key)
        for d_item_g in temp_d_list:
            if d_item_g.kullanici is None or d_item_g.kullanici == request.user: sitedeki_bos_ve_yoneticiye_ait_d.append(d_item_g)
    context = {
        'site': site, 'bloklar_ve_daireleri': bloklar_ve_daireleri_c, 'is_yeni_site': site is None,
        'form_data': form_data_get,
        'sitedeki_bos_ve_yoneticiye_ait_daireler': sitedeki_bos_ve_yoneticiye_ait_d,
        'yoneticinin_mevcut_dairesi_id': yoneticinin_mevcut_dairesi.id if yoneticinin_mevcut_dairesi else None,
    }
    return render(request, 'yonetim/site_bilgi.html', context)

@login_required
def cikis(request):
    logout(request)
    messages.info(request, "Başarıyla çıkış yaptınız.")
    return redirect('yonetim:giris')

@login_required
def ajax_bloklar(request):
    # ... (önceki tam yanıttaki gibi) ...
    site_kodu = request.GET.get('site_kodu','').strip().upper()
    if not site_kodu: return JsonResponse({'error':'Site kodu gerekli'}, status=400)
    try:
        site_n_ajax = Site.objects.get(kod=site_kodu)
        bloklar_aj = list(Blok.objects.filter(site=site_n_ajax).order_by('ad').values('id','ad'))
        if not bloklar_aj: return JsonResponse({'bloklar':[], 'message':'Bu sitede blok yok.'})
        return JsonResponse({'bloklar':bloklar_aj})
    except Site.DoesNotExist: return JsonResponse({'error':'Site bulunamadı'}, status=404)
    except Exception as e: logger.error(f"AJAX Bloklar: {e}"); return JsonResponse({'error':'Sunucu hatası'}, status=500)

@login_required
def ajax_daireler(request):
    # ... (önceki tam yanıttaki gibi) ...
    blok_id = request.GET.get('blok_id', None)
    if not blok_id: return JsonResponse({'error':'Blok ID gerekli'}, status=400)
    try:
        blok_n_ajax = Blok.objects.get(id=blok_id)
        daireler_q = Daire.objects.filter(blok=blok_n_ajax, kullanici__isnull=True)
        daireler_l_ajax = [{'id':d.id, 'no':str(d.daire_no), 'sort_key':d.get_sortable_daire_no()} for d in daireler_q]
        daireler_s_d_ajax = sorted(daireler_l_ajax, key=lambda x: x['sort_key'])
        daireler_sonuc_aj = [{'id':d['id'], 'no':d['no']} for d in daireler_s_d_ajax]
        if not daireler_sonuc_aj: return JsonResponse({'daireler':[], 'message':'Bu blokta boş daire yok.'})
        return JsonResponse({'daireler':daireler_sonuc_aj})
    except Blok.DoesNotExist: return JsonResponse({'error':'Blok bulunamadı'}, status=404)
    except Exception as e: logger.error(f"AJAX Daireler: {e}"); return JsonResponse({'error':f'Sunucu hatası: {str(e)}'}, status=500)