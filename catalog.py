# -*- coding: utf-8 -*-
import os, io, requests
from datetime import datetime
from html import escape
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                Image, PageBreak, KeepTogether)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER

GOLD = HexColor("#D4AF37")
DARK = HexColor("#141414")
LIGHT = HexColor("#F5F5F5")
GREY = HexColor("#AAAAAA")

FONT_URLS = [
    ("DejaVuSans", "https://cdn.jsdelivr.net/gh/dejavu-fonts/dejavu-fonts@master/ttf/DejaVuSans.ttf"),
    ("DejaVuSans-Bold", "https://cdn.jsdelivr.net/gh/dejavu-fonts/dejavu-fonts@master/ttf/DejaVuSans-Bold.ttf"),
]

_FONTS_OK = None

def fonts_ok():
    global _FONTS_OK
    if _FONTS_OK is None:
        os.makedirs("data", exist_ok=True)
        for name, url in FONT_URLS:
            path = os.path.join("data", f"{name}.ttf")
            if not os.path.exists(path):
                try:
                    r = requests.get(url, timeout=60)
                    if r.status_code == 200:
                        with open(path, "wb") as f:
                            f.write(r.content)
                except Exception as e:
                    print(f"font download error {name}: {e}")
            if os.path.exists(path):
                try:
                    pdfmetrics.registerFont(TTFont(name, path))
                except Exception as e:
                    print(f"font register error {name}: {e}")
        names = set(pdfmetrics.getRegisteredFontNames())
        _FONTS_OK = ("DejaVuSans" in names) and ("DejaVuSans-Bold" in names)
        print(f"Каталог: шрифты DejaVu = {_FONTS_OK}")
    return _FONTS_OK

def F(bold=False):
    if fonts_ok():
        return "DejaVuSans-Bold" if bold else "DejaVuSans"
    return "Helvetica-Bold" if bold else "Helvetica"

def styles():
    return {
        "title": ParagraphStyle("title", fontName=F(True), fontSize=30, textColor=GOLD,
                                alignment=TA_CENTER, leading=38),
        "subtitle": ParagraphStyle("subtitle", fontName=F(), fontSize=13, textColor=LIGHT,
                                   alignment=TA_CENTER, leading=19),
        "h": ParagraphStyle("h", fontName=F(True), fontSize=16, textColor=GOLD, leading=21),
        "body": ParagraphStyle("body", fontName=F(), fontSize=10.5, textColor=LIGHT, leading=15),
        "meta": ParagraphStyle("meta", fontName=F(), fontSize=10, textColor=GREY, leading=14),
        "price": ParagraphStyle("price", fontName=F(True), fontSize=13, textColor=GOLD, leading=18),
    }

def bg(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(DARK)
    canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(0.8)
    canvas.line(1.5*cm, 1.2*cm, A4[0]-1.5*cm, 1.2*cm)
    canvas.setFillColor(GREY)
    canvas.setFont(F(), 8)
    canvas.drawCentredString(A4[0]/2, 0.75*cm, "КомИнвест — коммерческая недвижимость Крыма")
    canvas.restoreState()

def build_catalog(objects):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=1.6*cm, rightMargin=1.6*cm,
                            topMargin=1.6*cm, bottomMargin=1.9*cm,
                            title="КомИнвест — каталог объектов")
    st = styles()
    story = []

    story.append(Spacer(1, 7*cm))
    story.append(Paragraph("КОМИНВЕСТ", st["title"]))
    story.append(Spacer(1, 0.6*cm))
    story.append(Paragraph("Каталог коммерческой недвижимости Крыма", st["subtitle"]))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(datetime.now().strftime("%d.%m.%Y"), st["meta"]))
    story.append(PageBreak())

    for o in objects:
        block = []
        data = o.get("_cover_bytes")
        if data:
            try:
                reader = ImageReader(io.BytesIO(data))
                w, h = reader.getSize()
                scale = min(17.5*cm / w, 9.5*cm / h)
                block.append(Image(io.BytesIO(data), width=w*scale, height=h*scale))
                block.append(Spacer(1, 0.4*cm))
            except Exception as e:
                print(f"img error obj {o.get('id')}: {e}")
        block.append(Paragraph(escape(o.get("title", "")), st["h"]))
        block.append(Spacer(1, 0.15*cm))
        block.append(Paragraph(escape(o.get("price", "")), st["price"]))
        block.append(Paragraph(
            f"Локация: {escape(o.get('location', '-'))} &nbsp;|&nbsp; "
            f"Площадь: {escape(str(o.get('area', '-')))} &nbsp;|&nbsp; "
            f"Тип: {escape(str(o.get('type', '-')))}", st["meta"]))
        block.append(Spacer(1, 0.25*cm))
        block.append(Paragraph(escape(o.get("description", ""))[:900], st["body"]))
        block.append(Spacer(1, 0.4*cm))
        story.append(block if len(block) > 5 else KeepTogether(block))
        story.append(PageBreak())

    story.append(Spacer(1, 6*cm))
    story.append(Paragraph("ХОТИТЕ ПОСМОТРЕТЬ ОБЪЕКТ?", st["title"]))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("Оставьте заявку в боте — юрист свяжется с вами<br/>"
                           "и организует показ в удобное время.", st["subtitle"]))
    story.append(Spacer(1, 0.7*cm))
    story.append(Paragraph("t.me/KomInvest_Crimea_bot", st["price"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph("t.me/KomInvest_Crimea", st["meta"]))

    doc.build(story, onFirstPage=bg, onLaterPages=bg)
    return buf.getvalue()