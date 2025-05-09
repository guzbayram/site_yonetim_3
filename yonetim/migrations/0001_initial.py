# Generated by Django 5.2.1 on 2025-05-07 15:22

import django.contrib.auth.models
import django.contrib.auth.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="Blok",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "ad",
                    models.CharField(
                        max_length=50, verbose_name="Blok Adı / Block Name"
                    ),
                ),
                (
                    "daire_sayisi",
                    models.PositiveIntegerField(
                        verbose_name="Daire Sayısı / Flat Count"
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Kullanici",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                (
                    "last_login",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="last login"
                    ),
                ),
                (
                    "is_superuser",
                    models.BooleanField(
                        default=False,
                        help_text="Designates that this user has all permissions without explicitly assigning them.",
                        verbose_name="superuser status",
                    ),
                ),
                (
                    "username",
                    models.CharField(
                        error_messages={
                            "unique": "A user with that username already exists."
                        },
                        help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.",
                        max_length=150,
                        unique=True,
                        validators=[
                            django.contrib.auth.validators.UnicodeUsernameValidator()
                        ],
                        verbose_name="username",
                    ),
                ),
                (
                    "first_name",
                    models.CharField(
                        blank=True, max_length=150, verbose_name="first name"
                    ),
                ),
                (
                    "last_name",
                    models.CharField(
                        blank=True, max_length=150, verbose_name="last name"
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        blank=True, max_length=254, verbose_name="email address"
                    ),
                ),
                (
                    "is_staff",
                    models.BooleanField(
                        default=False,
                        help_text="Designates whether the user can log into this admin site.",
                        verbose_name="staff status",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Designates whether this user should be treated as active. Unselect this instead of deleting accounts.",
                        verbose_name="active",
                    ),
                ),
                (
                    "date_joined",
                    models.DateTimeField(
                        default=django.utils.timezone.now, verbose_name="date joined"
                    ),
                ),
                (
                    "site_kodu",
                    models.CharField(
                        max_length=8, verbose_name="Site Kodu / Site Code"
                    ),
                ),
                (
                    "is_yonetici",
                    models.BooleanField(
                        default=False, verbose_name="Yönetici mi? / Is Manager?"
                    ),
                ),
                (
                    "groups",
                    models.ManyToManyField(
                        blank=True,
                        help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.group",
                        verbose_name="groups",
                    ),
                ),
                (
                    "user_permissions",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Specific permissions for this user.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.permission",
                        verbose_name="user permissions",
                    ),
                ),
            ],
            options={
                "verbose_name": "user",
                "verbose_name_plural": "users",
                "abstract": False,
            },
            managers=[
                ("objects", django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name="Daire",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "no",
                    models.CharField(max_length=10, verbose_name="Daire No / Flat No"),
                ),
                (
                    "blok",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="yonetim.blok"
                    ),
                ),
                (
                    "kullanici",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Aidat",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "tutar",
                    models.DecimalField(
                        decimal_places=2, max_digits=8, verbose_name="Tutar / Amount"
                    ),
                ),
                ("tarih", models.DateField(verbose_name="Tarih / Date")),
                (
                    "aciklama",
                    models.CharField(
                        blank=True,
                        max_length=255,
                        verbose_name="Açıklama / Description",
                    ),
                ),
                (
                    "daire",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="yonetim.daire"
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Site",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "ad",
                    models.CharField(
                        max_length=100, verbose_name="Site Adı / Site Name"
                    ),
                ),
                (
                    "adres",
                    models.CharField(max_length=255, verbose_name="Adres / Address"),
                ),
                (
                    "kod",
                    models.CharField(
                        max_length=8, unique=True, verbose_name="Site Kodu / Site Code"
                    ),
                ),
                (
                    "yonetici_tel",
                    models.CharField(
                        max_length=20, verbose_name="Yönetici Telefon / Manager Phone"
                    ),
                ),
                (
                    "yonetici",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Yönetici / Manager",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Gider",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "tur",
                    models.CharField(
                        max_length=50, verbose_name="Gider Türü / Expense Type"
                    ),
                ),
                (
                    "tutar",
                    models.DecimalField(
                        decimal_places=2, max_digits=8, verbose_name="Tutar / Amount"
                    ),
                ),
                ("tarih", models.DateField(verbose_name="Tarih / Date")),
                (
                    "aciklama",
                    models.CharField(
                        blank=True,
                        max_length=255,
                        verbose_name="Açıklama / Description",
                    ),
                ),
                (
                    "site",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="yonetim.site"
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="blok",
            name="site",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="yonetim.site"
            ),
        ),
    ]
