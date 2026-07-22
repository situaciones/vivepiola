from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('username', 'email', 'rol', 'condominio', 'is_active')
    list_filter = ('rol', 'condominio', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('Rol legal', {'fields': ('rol', 'condominio', 'persona', 'telefono')}),
    )
