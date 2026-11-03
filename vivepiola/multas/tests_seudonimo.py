"""Lo que sale hacia la IA en el extranjero va sin identificadores directos."""

import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import Rol, Usuario
from condominios.models import Condominio, Persona, RolOcupacion, Unidad
from multas.clasificador import clasificar_con_ia
from multas.models import Ticket
from multas.seudonimo import seudonimizar


class SeudonimoTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.condominio = Condominio.objects.create(nombre='Edificio Privado')
        cls.unidad = Unidad.objects.create(condominio=cls.condominio, identificador='Depto 12')
        Persona.objects.create(
            condominio=cls.condominio, unidad=cls.unidad, rol_ocupacion=RolOcupacion.PROPIETARIO,
            nombre_completo='Juan Andres Perez Soto', cedula_identidad='12.345.678-9', domicilio='Depto 12',
        )
        cls.guardia = Usuario.objects.create_user(
            username='guardia_s', password='x', rol=Rol.FISCALIZADOR, condominio=cls.condominio,
        )

    def test_quita_rut_correo_telefono_patente_y_nombres(self):
        texto = ('Juan Perez (RUT 12.345.678-9, juan@mail.cl, +56 9 8765 4321) dejo el auto '
                 'BBCD12 en la rampa. Perez dijo que volvia.')
        limpio = seudonimizar(texto, self.condominio)
        for dato in ('Juan', 'Perez', '12.345.678-9', 'juan@mail.cl', '8765', 'BBCD12'):
            self.assertNotIn(dato, limpio)
        self.assertIn('dejo el auto', limpio, 'el hecho se conserva')
        self.assertIn('[PERSONA]', limpio)

    @override_settings(ANTHROPIC_API_KEY='sk-ant-de-prueba')
    def test_el_clasificador_no_envia_el_nombre(self):
        ticket = Ticket.objects.create(
            condominio=self.condominio, unidad=self.unidad, creado_por=self.guardia,
            descripcion='Juan Andres Perez Soto dejo basura en el pasillo', fecha_hecho=timezone.now(),
        )
        enviado = {}

        def crear(**kw):
            enviado['contenido'] = kw['messages'][0]['content']
            texto = json.dumps({'codigo': None, 'confianza': 0, 'fundamento': ''})
            return SimpleNamespace(content=[SimpleNamespace(type='text', text=texto)])

        with patch('anthropic.Anthropic', return_value=SimpleNamespace(messages=SimpleNamespace(create=crear))):
            clasificar_con_ia(ticket, [])
        self.assertNotIn('Perez', enviado['contenido'])
        self.assertIn('dejo basura en el pasillo', enviado['contenido'])
