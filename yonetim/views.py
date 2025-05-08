from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from .models import Site, Kullanici, Blok, Daire, Aidat, Gider
from django.contrib.auth.hashers import make_password
from django.contrib import messages
import datetime
from django.http import JsonResponse
import re
from decimal import Decimal
from collections import defaultdict

# Giriş sayfası / Login page
def giris(request):
    if request.user.is_authenticated:
        return redirect('yonetim:panel')
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        site_kodu = request.POST.get('site_kodu')
        blok_adi = request.POST.get('blok_adi')
        daire_no = request.POST.get('daire_no')
        password = request.POST.get('password')
        
        try:
            # Kullanıcıyı ad, soyad ve site kodu ile bulmaya çalış
            user_query = Kullanici.objects.filter(first_name__iexact=first_name, last_name__iexact=last_name, site_kodu=site_kodu)
            
            if not user_query.exists():
                messages.error(request, 'Kullanıcı bulunamadı veya bilgiler hatalı.')
                return render(request, 'yonetim/giris.html')

            # Birden fazla kullanıcı dönerse (aynı ad, soyad, site_kodu), username ile ayrıştırma gerekebilir.
            # Şimdilik ilkini alıyoruz, ancak bu senaryo daha detaylı ele alınmalı.
            potential_user = user_query.first()

            # Daireyi bul
            daire = Daire.objects.filter(blok__site__kod=site_kodu, blok__ad=blok_adi, no=daire_no, kullanici=potential_user).first()
            if not daire:
                messages.error(request, 'Belirtilen blok ve dairede kayıtlı kullanıcı bulunamadı veya bilgiler hatalı.')
                return render(request, 'yonetim/giris.html')

            # Django'nun authenticate fonksiyonu username bekler.
            user = authenticate(request, username=potential_user.username, password=password)
            
            if user is not None:
                login(request, user)
                return redirect('yonetim:panel')
            else:
                messages.error(request, 'Parola hatalı.')
        except Exception as e: # Genel bir hata yakalama, loglama eklenebilir
            messages.error(request, f'Bir hata oluştu: {e}')
            
    return render(request, 'yonetim/giris.html')

# AJAX: Site koduna göre blokları döndür
def ajax_bloklar(request):
    site_kodu = request.GET.get('site_kodu')
    bloklar_data = []
    if site_kodu:
        try:
            site = Site.objects.get(kod=site_kodu)
            bloklar = Blok.objects.filter(site=site).values('id', 'ad') # ID de gönderiyoruz
            bloklar_data = list(bloklar)
        except Site.DoesNotExist:
            pass # Site bulunamazsa boş liste döner
    return JsonResponse({'bloklar': bloklar_data})

# AJAX: Blok adına göre daireleri döndür
def ajax_daireler(request):
    blok_id = request.GET.get('blok_id') # Artık blok_id kullanıyoruz
    daireler_data = []
    if blok_id:
        try:
            # Sadece kullanıcı atanmamış (boş) daireleri listele
            daireler = Daire.objects.filter(blok_id=blok_id, kullanici__isnull=True).values('id', 'no')
            daireler_data = list(daireler)
        except Blok.DoesNotExist: # Aslında blok_id olduğu için bu hata pek oluşmaz ama yine de
            pass
    return JsonResponse({'daireler': daireler_data})


# Kayıt sayfası / Register page
def kayit(request):
    if request.user.is_authenticated and not (request.user.is_yonetici and not Daire.objects.filter(kullanici=request.user).exists()):
         # Eğer kullanıcı zaten giriş yapmışsa ve yönetici değilse ya da yöneticiyse ama zaten bir dairesi varsa panele yönlendir
        return redirect('yonetim:panel')

    # Yönetici site bilgilerini girdikten sonra kendi dairesini seçmek için bu sayfaya yönlendirildiyse:
    if request.user.is_authenticated and request.user.is_yonetici and not Daire.objects.filter(kullanici=request.user).exists():
        site = Site.objects.filter(kod=request.user.site_kodu).first()
        if not site:
            messages.error(request, "Site bulunamadı. Lütfen çıkış yapıp tekrar deneyin.")
            return redirect('yonetim:giris') # veya başka bir uygun hata sayfasına

        context = {
            'yonetici_kaydi_icin_daire_secimi': True, # Template'in bu özel durumu anlaması için flag
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'site_kodu': request.user.site_kodu,
            'site_bloklari': Blok.objects.filter(site=site)
        }
        if request.method == 'POST':
            daire_id = request.POST.get('yonetici_daire_id')
            try:
                daire = Daire.objects.get(id=daire_id, blok__site=site)
                if daire.kullanici and daire.kullanici != request.user:
                    messages.error(request, 'Bu daire başka bir kullanıcıya atanmış.')
                else:
                    daire.kullanici = request.user
                    daire.save()
                    messages.success(request, 'Daire başarıyla size atandı.')
                    return redirect('yonetim:panel')
            except Daire.DoesNotExist:
                messages.error(request, 'Geçersiz daire seçimi.')
            return render(request, 'yonetim/kayit.html', context) # Hata durumunda formu tekrar göster
        return render(request, 'yonetim/kayit.html', context)

    # Normal kayıt işlemi (yeni kullanıcı veya yeni site kuran yönetici)
    if request.method == 'POST':
        site_kodu_form = request.POST.get('site_kodu', '').strip().lower() # Formdan gelen site kodu
        
        if not re.match(r'^[a-z0-9]{3}$', site_kodu_form):
            messages.error(request, 'Site kodu 3 karakter, küçük harf ve rakam içermelidir!')
            return render(request, 'yonetim/kayit.html')

        password = request.POST.get('password') # password1 yerine password
        password_confirm = request.POST.get('password_confirm') # password2 yerine password_confirm
        
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        rol = request.POST.get('rol') # 'yonetici' ya da 'sakin'
        
        is_yonetici = (rol == 'yonetici')
        
        # Benzersiz username oluşturma (örnek: ad_soyad_sitekodu)
        # Kullanıcı adı olarak e-posta da düşünülebilir veya daha karmaşık bir yapı.
        # Şimdilik basit tutuyoruz, ancak production'da daha robust bir yapı gerekebilir.
        base_username = f"{first_name.lower()}_{last_name.lower()}"
        username_candidate = f"{base_username}_{site_kodu_form}"
        counter = 1
        while Kullanici.objects.filter(username=username_candidate).exists():
            username_candidate = f"{base_username}_{site_kodu_form}_{counter}"
            counter += 1
        username = username_candidate

        if password != password_confirm:
            messages.error(request, 'Parolalar eşleşmiyor.')
            return render(request, 'yonetim/kayit.html')

        if Kullanici.objects.filter(site_kodu=site_kodu_form, first_name__iexact=first_name, last_name__iexact=last_name).exists():
             # Bu site kodu, ad ve soyad ile daha önce kayıt yapılmış mı kontrolü
             # Daha spesifik kontrol gerekebilir (örn: aynı daireye mükerrer kayıt engelleme)
            messages.error(request, 'Bu ad, soyad ve site kodu ile daha önce bir kullanıcı kayıt olmuş.')
            return render(request, 'yonetim/kayit.html')

        site_var_mi = Site.objects.filter(kod=site_kodu_form).first()

        user = Kullanici.objects.create_user( # create_user kullanmak daha iyi
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            site_kodu=site_kodu_form,
            is_yonetici=is_yonetici
        )

        if is_yonetici:
            if site_var_mi: # Yönetici var olan bir siteye kaydoluyorsa
                messages.info(request, 'Yönetici olarak var olan bir siteye kayıt olma özelliği henüz aktif değil. Yeni site kurabilirsiniz.')
                user.delete() 
                return render(request, 'yonetim/kayit.html')
            else: # Yönetici yeni bir site kuruyor
                site = Site.objects.create(
                    ad='Yeni Site (Lütfen Güncelleyin)', # Geçici bir ad
                    adres='Belirtilmedi',
                    kod=site_kodu_form,
                    yonetici=user,
                    yonetici_tel='Belirtilmedi'
                )
                login(request, user)
                messages.success(request, f'Hoş geldiniz, {user.first_name}! Siteniz oluşturuldu. Lütfen site bilgilerinizi girin.')
                return redirect('yonetim:site_bilgi') # Yöneticiyi site bilgilerini girmesi için yönlendir
        else: # Sakin kaydı
            if not site_var_mi:
                messages.error(request, 'Bu site kodu ile kayıtlı bir site bulunamadı. Yöneticinizle iletişime geçin.')
                user.delete() # Oluşturulan kullanıcıyı geri al
                return render(request, 'yonetim/kayit.html')
            
            daire_id = request.POST.get('sakin_daire_id') # Template'den daire ID'si gelecek
            if not daire_id:
                messages.error(request, 'Lütfen bir daire seçin.')
                user.delete()
                return render(request, 'yonetim/kayit.html')

            try:
                daire = Daire.objects.get(id=daire_id, blok__site=site_var_mi)
                if daire.kullanici:
                    messages.error(request, 'Bu daire zaten başka bir kullanıcıya atanmış.')
                    user.delete()
                    return render(request, 'yonetim/kayit.html')
                daire.kullanici = user
                daire.save()
                login(request, user)
                messages.success(request, f'Hoş geldiniz, {user.first_name}! Kaydınız tamamlandı.')
                return redirect('yonetim:panel')
            except Daire.DoesNotExist:
                messages.error(request, 'Seçilen daire bulunamadı.')
                user.delete()
                return render(request, 'yonetim/kayit.html')
                
    return render(request, 'yonetim/kayit.html')


# Site bilgileri sayfası / Site info page
def site_bilgi(request):
    if not request.user.is_authenticated or not request.user.is_yonetici:
        messages.error(request, "Bu sayfaya erişim yetkiniz yok.")
        return redirect('yonetim:giris')

    site = Site.objects.filter(yonetici=request.user, kod=request.user.site_kodu).first()
    if not site:
        messages.error(request, "Yöneticisi olduğunuz bir site bulunamadı.")
        return redirect('yonetim:giris')

    if request.method == 'POST':
        site.ad = request.POST.get('site_adi', site.ad)
        site.adres = request.POST.get('site_adresi', site.adres)
        site.yonetici_tel = request.POST.get('yonetici_tel', site.yonetici_tel) # Yönetici telefonunu da alalım
        
        aidat_miktari_str = request.POST.get('aidat_miktari')
        if aidat_miktari_str:
            try:
                site.aidat_miktari = Decimal(aidat_miktari_str)
            except:
                messages.error(request, "Aidat miktarı geçerli bir sayı olmalıdır.")
                # Hata durumunda formu mevcut bilgilerle tekrar render et
                bloklar = Blok.objects.filter(site=site)
                context = {'site': site, 'bloklar': bloklar}
                return render(request, 'yonetim/site_bilgi.html', context)
        else:
            site.aidat_miktari = None # Eğer boş bırakılırsa None ata
        
        site.save()

        # Blokları ve daireleri güncelleme/oluşturma
        # Önce mevcut blokları ve onlara bağlı daireleri silmek yerine güncellemeyi veya
        # sadece yeni eklenenleri işlemeyi düşünebilirsiniz.
        # Şimdilik basitlik adına, mevcut blokları silip yeniden oluşturuyoruz.
        # DİKKAT: Bu işlem, dairelere atanmış kullanıcıları veya aidat bilgilerini etkileyebilir.
        # Production'da bu kısım daha dikkatli yönetilmeli.
        
        # Blokları silmeden önce, dairelerde oturan kullanıcı var mı kontrol edilebilir.
        # Veya sadece daire_sayisi değiştiyse daire ekle/sil yapılabilir.
        
        # Mevcut blokları alalım
        current_blok_adlari = [b.ad for b in Blok.objects.filter(site=site)]
        
        # Formdan gelen blok adları ve daire sayıları
        blok_adlari_form = request.POST.getlist('blok_adi[]')
        daire_sayilari_form = request.POST.getlist('daire_sayisi[]')

        # Silinecek bloklar
        bloklar_to_delete = set(current_blok_adlari) - set(b_ad for b_ad in blok_adlari_form if b_ad)
        for blok_ad_del in bloklar_to_delete:
            Blok.objects.filter(site=site, ad=blok_ad_del).delete() # Daireler de CASCADE ile silinir.

        for blok_adi, daire_sayisi_str in zip(blok_adlari_form, daire_sayilari_form):
            if not blok_adi or not daire_sayisi_str: # Boş girişleri atla
                continue
            try:
                daire_sayisi = int(daire_sayisi_str)
                if daire_sayisi <= 0: continue # Geçersiz daire sayısı

                blok, created = Blok.objects.get_or_create(
                    site=site, 
                    ad=blok_adi,
                    defaults={'daire_sayisi': daire_sayisi}
                )
                if not created: # Blok zaten varsa daire sayısını güncelle
                    blok.daire_sayisi = daire_sayisi
                    blok.save()
                
                # Daireleri oluştur/güncelle (var olanları silmeden)
                current_daire_count = Daire.objects.filter(blok=blok).count()
                if daire_sayisi > current_daire_count: # Yeni daireler ekle
                    for i in range(current_daire_count + 1, daire_sayisi + 1):
                        Daire.objects.create(blok=blok, no=str(i))
                elif daire_sayisi < current_daire_count: # Fazla daireleri sil (içinde oturan yoksa)
                    # DİKKAT: İçinde oturan varsa silmemek daha doğru olur. Bu kısım daha detaylı ele alınmalı.
                    # Şimdilik, sondan başlayarak fazla daireleri siliyoruz.
                    daireler_to_delete = Daire.objects.filter(blok=blok, kullanici__isnull=True).order_by('-no')[:current_daire_count - daire_sayisi]
                    for d_del in daireler_to_delete:
                        d_del.delete()
                    # Eğer hala silinmesi gereken daire varsa ve içlerinde oturan varsa, burada bir uyarı verilebilir.
                    if Daire.objects.filter(blok=blok).count() > daire_sayisi:
                        messages.warning(request, f"{blok.ad} bloğunda bazı daireler içinde oturan olduğu için silinemedi.")


            except ValueError:
                messages.error(request, f"'{daire_sayisi_str}' geçerli bir daire sayısı değil.")
                continue
        
        messages.success(request, 'Site ve blok bilgileri güncellendi.')
        
        # Eğer yönetici kendi dairesini henüz seçmediyse, onu kayit sayfasına (özel mod) yönlendir.
        if not Daire.objects.filter(kullanici=request.user).exists():
            return redirect('yonetim:kayit') 
        return redirect('yonetim:panel')

    # GET request
    bloklar = Blok.objects.filter(site=site)
    context = {
        'site': site,
        'bloklar': bloklar,
        'yonetici_adi': request.user.get_full_name() if request.user.is_authenticated else '',
        # site_ad ve site_adres zaten site objesinden geliyor
    }
    return render(request, 'yonetim/site_bilgi.html', context)


# Panel sayfası / Main panel page
def panel(request):
    if not request.user.is_authenticated:
        return redirect('yonetim:giris')

    user = request.user
    try:
        site = Site.objects.get(kod=user.site_kodu)
    except Site.DoesNotExist:
        messages.error(request, "Site bulunamadı. Lütfen sistem yöneticisi ile iletişime geçin.")
        logout(request)
        return redirect('yonetim:giris')

    kullanici_daireler = Daire.objects.filter(kullanici=user, blok__site=site)
    if not kullanici_daireler.exists() and not user.is_yonetici:
        messages.info(request, "Henüz bir daireye atanmamışsınız. Lütfen yöneticinizle iletişime geçin.")
        # Dairesi olmayan sakin için panelde ne gösterileceğine karar verilmeli.
        # Şimdilik kısıtlı bir panel veya bir mesaj gösterilebilir.
    
    # Yönetici ise ve henüz kendi dairesini seçmediyse site_bilgi'ye veya kayit'a yönlendirilebilir.
    if user.is_yonetici and not Daire.objects.filter(kullanici=user, blok__site=site).exists():
        # Eğer site için blok/daire tanımlanmamışsa önce site_bilgi'ye
        if not Blok.objects.filter(site=site).exists():
            messages.info(request, "Siteniz için henüz blok ve daire tanımlanmamış. Lütfen önce site bilgilerinizi güncelleyin.")
            return redirect('yonetim:site_bilgi')
        else:
            messages.info(request, "Yönetici olarak kendi dairenizi seçmeniz gerekiyor.")
            return redirect('yonetim:kayit')


    if request.method == 'POST':
        if 'odeme_miktari' in request.POST: # Formu ayırt etmek için input name'i kontrol et
            odeme_miktari_str = request.POST.get('odeme_miktari')
            daire_id_form = request.POST.get('daire_id_form') # Hangi daire için ödeme yapıldığı bilgisi

            if not kullanici_daireler.exists() and not user.is_yonetici: # Sakin ve dairesi yoksa ödeme yapamaz
                 messages.error(request, "Aidat ödemesi yapabilmek için bir daireye atanmış olmalısınız.")
                 return redirect('panel')

            # Yönetici ise, forma eklenen bir select'ten hangi daire için aidat girildiğini alabilir.
            # Şimdilik, kullanıcı kendi ilk dairesi için ödeme yapıyor varsayalım veya formda daire seçimi olmalı.
            # Basitlik adına, eğer kullanıcı sakin ise kendi ilk dairesine, yönetici ise formdan gelen daireye atama yapalım.
            
            target_daire = None
            if user.is_yonetici:
                # Yöneticinin tüm daireler için aidat girebilmesi için panel.html'de bir Daire seçimi olmalı.
                # Bu kısım şimdilik atlanmıştır, yönetici kendi dairesi için aidat girer gibi davranır.
                # Ya da aşağıdaki daire_id_form kullanılır.
                if daire_id_form:
                    try:
                        target_daire = Daire.objects.get(id=daire_id_form, blok__site=site)
                    except Daire.DoesNotExist:
                        messages.error(request, "Aidat eklenmek istenen daire bulunamadı.")
                elif kullanici_daireler.exists(): # Yönetici kendi dairesi için giriyorsa
                     target_daire = kullanici_daireler.first()
                else: # Yönetici ama dairesi yok ve formdan daire gelmedi
                    messages.error(request, "Yönetici olarak aidat eklemek için lütfen bir daire seçin veya kendi dairenizi belirleyin.")
            
            elif kullanici_daireler.exists(): # Sakin kullanıcısı
                target_daire = kullanici_daireler.first()

            if target_daire and odeme_miktari_str:
                try:
                    odeme_miktari = Decimal(odeme_miktari_str)
                    if odeme_miktari > 0:
                        Aidat.objects.create(
                            daire=target_daire,
                            tutar=odeme_miktari,
                            tarih=datetime.date.today(),
                            aciklama=request.POST.get('odeme_aciklama', '')
                        )
                        messages.success(request, 'Aidat ödemesi kaydedildi.')
                    else:
                        messages.error(request, "Ödeme miktarı pozitif olmalıdır.")
                except ValueError:
                    messages.error(request, "Geçersiz ödeme miktarı.")
            elif not target_daire :
                 messages.error(request, "Aidat eklenecek daire bulunamadı/seçilmedi.")
            return redirect('yonetim:panel')

        elif 'gider_miktari' in request.POST and user.is_yonetici: # Gider ekleme formu
            gider_turu = request.POST.get('gider_turu')
            gider_miktari_str = request.POST.get('gider_miktari')
            gider_aciklama = request.POST.get('gider_aciklama')

            if gider_turu and gider_miktari_str:
                try:
                    gider_miktari = Decimal(gider_miktari_str)
                    if gider_miktari > 0:
                        Gider.objects.create(
                            site=site,
                            tur=gider_turu,
                            tutar=gider_miktari,
                            tarih=datetime.date.today(),
                            aciklama=gider_aciklama
                        )
                        messages.success(request, 'Gider kaydedildi.')
                    else:
                        messages.error(request, "Gider miktarı pozitif olmalıdır.")
                except ValueError:
                    messages.error(request, "Geçersiz gider miktarı.")
            else:
                messages.error(request, "Gider türü ve miktarı boş bırakılamaz.")
            return redirect('yonetim:panel')

    # GET request için context hazırlığı
    aidatlar = Aidat.objects.filter(daire__blok__site=site).order_by('-tarih', '-id')
    giderler = Gider.objects.filter(site=site).order_by('-tarih', '-id')

    toplam_gelir = sum(a.tutar for a in aidatlar)
    toplam_gider = sum(g.tutar for g in giderler)
    kasa_bakiyesi = toplam_gelir - toplam_gider

    # Kullanıcının borcu/ödediği
    kullanici_odenmis_aidat_toplami = 0
    # Aylık aidat miktarı sitede tanımlıysa, kullanıcının borcunu hesaplayabiliriz.
    # Bu kısım daha detaylı bir borç takip sistemi gerektirir.
    # Şimdilik sadece kullanıcının ödediği toplam aidatı gösteriyoruz.
    if kullanici_daireler.exists():
        kullanici_odenmis_aidat_toplami = sum(a.tutar for a in aidatlar.filter(daire__in=kullanici_daireler))
    
    kullanici_blok_adi = kullanici_daireler.first().blok.ad if kullanici_daireler.exists() else "-"
    kullanici_daire_no_val = kullanici_daireler.first().no if kullanici_daireler.exists() else "-"

    # --- Aidat Takip Tablosu için yıllık özet / Annual summary for dues table ---
    now = datetime.datetime.now()
    yil = now.year
    # Tüm daireleri blok ve no'ya göre sırala / Sort all flats by block and number
    tum_daireler = Daire.objects.filter(blok__site=site).select_related('blok', 'kullanici')
    tum_daireler = sorted(tum_daireler, key=lambda d: (d.blok.ad, int(d.no) if d.no.isdigit() else d.no))
    # Her daire için ödenen toplam / For each flat, total paid for the year
    aidat_ozet = []
    site_yillik_aidat = (site.aidat_miktari or 0) * 12
    for daire in tum_daireler:
        # O daireye ait yıl içindeki ödemeler / Payments for this flat in the current year
        odenen = sum(a.tutar for a in Aidat.objects.filter(daire=daire, tarih__year=yil))
        bakiye = site_yillik_aidat - odenen
        # Borç kırmızı, alacak yeşil / Debt red, credit green
        if bakiye > 0:
            bakiye_renk = 'text-danger' # Borç
        elif bakiye < 0:
            bakiye_renk = 'text-success' # Alacak
        else:
            bakiye_renk = 'text-secondary' # Nötr
        aidat_ozet.append({
            'blok': daire.blok.ad,
            'daire_no': daire.no,
            'sakin': daire.kullanici.get_full_name() if daire.kullanici else '-',
            'yillik_borc': site_yillik_aidat,
            'odenen': odenen,
            'bakiye': bakiye,
            'bakiye_renk': bakiye_renk,
        })

    gider_bos_satir_sayisi = range(max(0, 12 - len(giderler))) # Gider tablosu için boş satır sayısı

    context = {
        'site': site,
        'bloklar': Blok.objects.filter(site=site),
        'daireler': Daire.objects.filter(blok__site=site), # Yöneticinin tüm daireleri görmesi için
        'aidatlar': aidatlar,
        'giderler': giderler,
        'toplam_gelir': toplam_gelir,
        'toplam_gider': toplam_gider,
        'kasa_bakiyesi': kasa_bakiyesi,
        'kullanici_odenmis_aidat_toplami': kullanici_odenmis_aidat_toplami,
        'kullanici_daireler': kullanici_daireler, # Kullanıcının kendi daireleri (birden fazla olabilir)
        'kullanici_blok_adi': kullanici_blok_adi,
        'kullanici_daire_no': kullanici_daire_no_val,
        'site_aylik_aidat': site.aidat_miktari if site.aidat_miktari else 0,
        'aidat_ozet': aidat_ozet, # Yıllık özet tablo / Annual summary table
        'gider_bos_satir_sayisi': gider_bos_satir_sayisi,
    }
    return render(request, 'yonetim/panel.html', context)

# Kullanıcı çıkış işlemi / User logout
def cikis(request):
    logout(request)
    return redirect('yonetim:giris')