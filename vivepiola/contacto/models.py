from django.db import models


class SolicitudDemo(models.Model):
    """
    Lo que deja quien pide una demo en la portada.

    Se guarda antes de avisar por correo: si el correo falla, la solicitud
    sigue aqui y se ve en el panel de administracion. Un interesado que llena
    el formulario y nunca recibe respuesta es un cliente perdido.
    """

    nombre = models.CharField(max_length=120)
    correo = models.EmailField()
    empresa = models.CharField('Condominio o administradora', max_length=200, blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)
    atendida = models.BooleanField(default=False)
    notas = models.TextField(blank=True, help_text='Seguimiento interno: cuando se contacto, que se acordo.')

    class Meta:
        ordering = ['-creada_en']
        verbose_name = 'solicitud de demo'
        verbose_name_plural = 'solicitudes de demo'

    def __str__(self):
        return f'{self.nombre} <{self.correo}>'
