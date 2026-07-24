"""Reportes PDF y Excel del panel administrativo."""
import io
from datetime import datetime

from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

GOLD = colors.HexColor("#C9A227")
BURGUNDY = colors.HexColor("#6B1A2A")


def build_kpis_pdf(kpis: dict) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4
    c.setFillColor(BURGUNDY)
    c.rect(0, h - 3 * cm, w, 3 * cm, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 20)
    report_title = kpis.get("event_name") or "Reporte general"
    c.drawString(2 * cm, h - 2 * cm, "TAVA Teatro — Reporte de métricas")
    c.setFillColor(colors.HexColor("#333333"))
    c.setFont("Helvetica", 10)
    c.drawString(2 * cm, h - 2.6 * cm, f"{report_title} · {datetime.now():%Y-%m-%d %H:%M}")

    rows = [
        ("Eventos activos", kpis.get("eventos_activos", 0)),
        ("Boletas vendidas", kpis.get("boletas_vendidas", 0)),
        ("Ingresos (COP)", f"${kpis.get('ingresos', 0):,.0f}"),
        ("Asistentes (check-in)", kpis.get("asistentes", 0)),
        ("Pendientes de ingreso", kpis.get("pendientes_ingreso", 0)),
        ("Ocupación (%)", f"{kpis.get('ocupacion_porcentaje', 0)}%"),
        ("Conversión (%)", f"{kpis.get('conversion_porcentaje', 0)}%"),
    ]
    y = h - 5 * cm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2 * cm, y, "Indicador")
    c.drawString(12 * cm, y, "Valor")
    y -= 0.6 * cm
    c.setStrokeColor(GOLD)
    c.line(2 * cm, y, w - 2 * cm, y)
    y -= 0.8 * cm
    c.setFont("Helvetica", 11)
    for label, value in rows:
        c.drawString(2 * cm, y, str(label))
        c.drawString(12 * cm, y, str(value))
        y -= 0.75 * cm

    c.setFont("Helvetica-Oblique", 9)
    c.setFillColor(colors.grey)
    c.drawString(2 * cm, 2 * cm, "Generado por Sistema de eventos TAVA")
    c.showPage()
    c.save()
    return buffer.getvalue()


def build_kpis_xlsx(kpis: dict) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Métricas"
    ws.append(["Indicador", "Valor"])
    ws.append(["Alcance", kpis.get("event_name") or "Reporte general"])
    if kpis.get("event_date"):
        ws.append(["Fecha del evento", kpis["event_date"]])
    if kpis.get("event_status"):
        ws.append(["Estado del evento", kpis["event_status"]])
    if kpis.get("capacity"):
        ws.append(["Capacidad", kpis["capacity"]])
    ws.append(["Eventos activos", kpis.get("eventos_activos", 0)])
    ws.append(["Boletas vendidas", kpis.get("boletas_vendidas", 0)])
    ws.append(["Ingresos COP", kpis.get("ingresos", 0)])
    ws.append(["Asistentes", kpis.get("asistentes", 0)])
    ws.append(["Pendientes de ingreso", kpis.get("pendientes_ingreso", 0)])
    ws.append(["Ocupación %", kpis.get("ocupacion_porcentaje", 0)])
    ws.append(["Órdenes pagadas", kpis.get("ordenes_pagadas", 0)])
    ws.append(["Órdenes totales", kpis.get("ordenes_totales", 0)])
    ws.append(["Conversión %", kpis.get("conversion_porcentaje", 0)])
    ws.append([])
    ws.append(["Generado", datetime.now().isoformat()])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
