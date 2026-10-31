"""
Version HTML de los correos que envia el sistema.

El texto plano sigue siendo el cuerpo principal del correo: es lo que queda
como constancia y lo que lee cualquier cliente. El HTML es la misma
informacion presentada con la marca y con un boton para abrir el caso, porque
un enlace largo en medio de un parrafo es facil de pasar por alto.

Los estilos van en linea y la estructura en tablas: Gmail y Outlook ignoran
las hojas de estilo y las cajas flexibles. Todo el texto se escapa; nada de lo
que viene del caso (descripciones, nombres) puede inyectar marcado.
"""

import re
from html import escape

from django.core.mail import EmailMultiAlternatives

_URL = re.compile(r'(https?://[^\s<]+)')

TINTA = '#15142b'
SUAVE = '#4a4a68'
TENUE = '#85869f'
INDIGO = '#4f46e5'
FONDO = '#f3f4f9'


def _parrafo(texto):
    """Escapa, convierte los enlaces en enlaces y respeta los saltos de linea."""
    seguro = escape(texto)
    seguro = _URL.sub(
        lambda m: f'<a href="{m.group(1)}" style="color:{INDIGO};word-break:break-all">{m.group(1)}</a>',
        seguro,
    )
    return seguro.replace('\n', '<br>')


def html_correo(*, comunidad, titulo, parrafos, boton=None, destacado=None, pie=''):
    """
    Arma el HTML de un correo.

    - comunidad: nombre que encabeza el correo (de donde viene).
    - parrafos: textos en orden; se escapan.
    - boton: (texto, url) opcional, va despues del primer bloque.
    - destacado: texto que va en una caja (el monto, o que no hay cobro).
    - pie: nota final en letra chica.
    """
    cuerpo = []
    for i, texto in enumerate(parrafos):
        cuerpo.append(
            f'<p style="margin:0 0 16px;font-size:15px;line-height:1.55;color:{SUAVE}">{_parrafo(texto)}</p>'
        )
        if i == 1 and destacado:
            cuerpo.append(
                f'<div style="margin:4px 0 20px;padding:14px 16px;border-radius:12px;background:#eef0ff;'
                f'border:1px solid #d4d8ff;font-size:15px;line-height:1.5;color:{TINTA};font-weight:600">'
                f'{_parrafo(destacado)}</div>'
            )
        if i == 1 and boton:
            texto_boton, url = boton
            cuerpo.append(
                '<table role="presentation" cellspacing="0" cellpadding="0" style="margin:8px 0 22px"><tr>'
                f'<td style="border-radius:12px;background:{INDIGO}">'
                f'<a href="{escape(url, quote=True)}" style="display:inline-block;padding:14px 26px;'
                f'font-size:15px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:12px">'
                f'{escape(texto_boton)}</a></td></tr></table>'
            )

    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(titulo)}</title></head>
<body style="margin:0;padding:0;background:{FONDO};font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:{FONDO};padding:24px 12px">
<tr><td align="center">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:580px">
    <tr><td style="padding:0 4px 14px">
      <table role="presentation" cellspacing="0" cellpadding="0"><tr>
        <td style="width:34px;height:34px;border-radius:9px;background:#0b0b14;text-align:center;vertical-align:middle;font-size:18px;font-weight:800;color:#3b82f6">&#10003;</td>
        <td style="padding-left:10px;font-size:13px;font-weight:800;letter-spacing:.06em;line-height:1.1;color:{TINTA}">SIN<br>CONFLICTO</td>
      </tr></table>
    </td></tr>
    <tr><td style="background:#ffffff;border:1px solid #e7e7f0;border-radius:16px;padding:28px 26px">
      <p style="margin:0 0 6px;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:{TENUE}">{escape(comunidad)}</p>
      <h1 style="margin:0 0 20px;font-size:21px;line-height:1.25;color:{TINTA}">{escape(titulo)}</h1>
      {''.join(cuerpo)}
    </td></tr>
    <tr><td style="padding:16px 8px 0;font-size:12px;line-height:1.5;color:{TENUE};text-align:center">
      {_parrafo(pie) if pie else ''}{'<br>' if pie else ''}Enviado por SINCONFLICTO para {escape(comunidad)} &middot; sinconflicto.cl
    </td></tr>
  </table>
</td></tr></table>
</body></html>"""


def correo_con_html(*, asunto, texto, html, from_email, to, cc=None, reply_to=None):
    """Correo con texto plano como cuerpo y el HTML como alternativa."""
    correo = EmailMultiAlternatives(
        subject=asunto, body=texto, from_email=from_email,
        to=to, cc=cc or [], reply_to=reply_to or None,
    )
    correo.attach_alternative(html, 'text/html')
    return correo
