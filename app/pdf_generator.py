from __future__ import annotations

import logging
from datetime import date
from typing import Any

from fpdf import FPDF

from app import config, notifications
from app.models import ConditionState, EquipmentRecord

logger = logging.getLogger(__name__)

_CONDITION_LABELS: dict[ConditionState, str] = {
    "good": "Исправно (в норме)",
    "attention": "Требует внимания (замечания)",
    "critical": "Критическое состояние (аварийный дефект)",
}

_SEVERITY_LABELS: dict[str, str] = {
    "low": "Низкая",
    "medium": "Средняя",
    "high": "Высокая",
    "critical": "Критическая / Аварийная",
}


def _format_rub(amount: float) -> str:
    rounded = int(round(amount))
    return f"{rounded:,}".replace(",", " ") + " ₽"


class MindBasePDF(FPDF):
    """
    Базовый класс отчётов с поддержкой кириллицы (ReportSans),
    фирменным колонтитулом и номерами страниц.
    """

    def __init__(
        self,
        doc_title: str = "ЭКСПЛУАТАЦИОННЫЙ ДОКУМЕНТ",
        inv_number: str = "",
        orientation: str = "P",
    ):
        super().__init__(orientation=orientation, unit="mm", format="A4")
        self.doc_title = doc_title
        self.inv_number = inv_number

        reg_font = config.STATIC_DIR / "fonts" / "ReportSans-Regular.ttf"
        bold_font = config.STATIC_DIR / "fonts" / "ReportSans-Bold.ttf"

        self.add_font("ReportSans", "", str(reg_font))
        self.add_font("ReportSans", "B", str(bold_font))
        self.set_font("ReportSans", "", 9)
        self.set_margins(15, 15, 15)
        self.set_auto_page_break(auto=True, margin=15)

    def header(self) -> None:
        if self.page_no() > 1:
            self.set_font("ReportSans", "B", 8)
            self.set_text_color(100, 100, 110)
            inv_part = f" | Инв. № {self.inv_number}" if self.inv_number else ""
            self.cell(120, 6, f"{self.doc_title}{inv_part}", align="L")
            self.cell(60, 6, date.today().strftime("%d.%m.%Y"), align="R", new_x="LMARGIN", new_y="NEXT")
            self.set_draw_color(210, 215, 225)
            self.line(15, self.get_y(), 195, self.get_y())
            self.ln(4)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("ReportSans", "", 8)
        self.set_text_color(130, 135, 145)
        self.cell(90, 6, "Система ТО и паспортизации оборудования Mind Equip", align="L")
        self.cell(90, 6, f"Страница {self.page_no()} из {{nb}}", align="R")

    def draw_top_banner(
        self,
        system_category: str,
        title: str,
        equipment_name: str,
        inv_number: str,
        location: str = "",
    ) -> None:
        # Верхняя акцентная плашка
        self.set_fill_color(18, 20, 30)
        self.rect(15, 15, 180, 26, style="F")

        # Тонкая декоративная цветная полоса слева
        self.set_fill_color(75, 59, 255)
        self.rect(15, 15, 3.5, 26, style="F")

        self.set_xy(22, 17)
        self.set_font("ReportSans", "B", 8)
        self.set_text_color(0, 245, 255)  # Cyan акцент
        self.cell(110, 4, system_category.upper(), new_x="LMARGIN", new_y="NEXT")

        self.set_x(22)
        self.set_font("ReportSans", "B", 13)
        self.set_text_color(245, 247, 250)
        self.cell(115, 7, title, new_x="LMARGIN", new_y="NEXT")

        self.set_x(22)
        self.set_font("ReportSans", "", 8.5)
        self.set_text_color(180, 185, 200)
        loc_str = f" | {location}" if location else ""
        self.cell(115, 5, f"{equipment_name}{loc_str}")

        # Правый бейдж инвентарного номера
        self.set_xy(140, 19)
        self.set_fill_color(28, 32, 48)
        self.set_draw_color(60, 68, 90)
        self.rect(142, 19, 48, 18, style="DF")

        self.set_xy(144, 21)
        self.set_font("ReportSans", "", 7.5)
        self.set_text_color(160, 165, 180)
        self.cell(44, 4, "ИНВЕНТАРНЫЙ НОМЕР", align="C", new_x="LMARGIN", new_y="NEXT")

        self.set_x(144)
        self.set_font("ReportSans", "B", 10.5)
        self.set_text_color(245, 247, 250)
        self.cell(44, 5, inv_number, align="C", new_x="LMARGIN", new_y="NEXT")

        self.set_x(144)
        self.set_font("ReportSans", "", 7)
        self.set_text_color(140, 145, 160)
        self.cell(44, 4, f"Дата: {date.today().strftime('%d.%m.%Y')}", align="C")

        self.set_y(45)

    def draw_section_heading(self, title: str) -> None:
        self.set_font("ReportSans", "B", 10.5)
        self.set_text_color(20, 24, 38)
        self.cell(180, 7, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(75, 59, 255)
        self.set_line_width(0.6)
        self.line(15, self.get_y(), 50, self.get_y())
        self.set_draw_color(220, 224, 232)
        self.set_line_width(0.2)
        self.line(50, self.get_y(), 195, self.get_y())
        self.ln(3)

    def draw_signatures(self, role1: str, role2: str) -> None:
        self.ln(6)
        self.set_font("ReportSans", "", 9)
        self.set_text_color(40, 45, 55)

        y = self.get_y()
        if y > 250:
            self.add_page()
            y = self.get_y()

        self.set_xy(15, y)
        self.cell(85, 5, f"{role1}:", new_x="LMARGIN", new_y="NEXT")
        self.set_x(15)
        self.cell(85, 5, "____________________ / ____________________ /")

        self.set_xy(110, y)
        self.cell(85, 5, f"{role2}:", new_x="LMARGIN", new_y="NEXT")
        self.set_x(110)
        self.cell(85, 5, "____________________ / ____________________ /")
        self.ln(8)


def generate_passport_pdf(record: EquipmentRecord, specs: dict[str, str] | None = None) -> bytes:
    """
    Генерирует официальный паспорт оборудования в формате PDF (A4).
    """
    pdf = MindBasePDF(doc_title="ТЕХНИЧЕСКИЙ ПАСПОРТ ОБОРУДОВАНИЯ", inv_number=record.inventory_number)
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.draw_top_banner(
        system_category="Паспорт изделия и формуляр",
        title="ТЕХНИЧЕСКИЙ ПАСПОРТ ОБОРУДОВАНИЯ",
        equipment_name=record.name,
        inv_number=record.inventory_number,
        location=record.location,
    )

    # Раздел 1: Общие сведения
    pdf.draw_section_heading("1. ОБЩИЕ СВЕДЕНИЯ ОБ ИЗДЕЛИИ")

    info_rows = [
        ["Наименование агрегата", record.name],
        ["Инвентарный номер", record.inventory_number],
        ["Модель / Модификация", record.model or "—"],
        ["Заводской (серийный) номер", record.serial_number or "—"],
        ["Предприятие-изготовитель", record.manufacturer or "—"],
        ["Год ввода в эксплуатацию", str(record.commission_year) if record.commission_year else "—"],
        ["Место установки / Подразделение", record.location],
        ["Текущее техническое состояние", _CONDITION_LABELS.get(record.status, record.status)],
    ]

    pdf.set_font("ReportSans", "", 9)
    with pdf.table(col_widths=(60, 120), text_align=("LEFT", "LEFT"), line_height=5.5) as table:
        for label, val in info_rows:
            r = table.row()
            r.cell(label)
            r.cell(val)

    pdf.ln(5)

    # Раздел 2: Технические характеристики
    pdf.draw_section_heading("2. ОСНОВНЫЕ ТЕХНИЧЕСКИЕ ХАРАКТЕРИСТИКИ")

    spec_dict = specs or {
        "Электропитание": "380 В, 3 фазы, 50 Гц",
        "Номинальная мощность": "37 кВт / 50 л.с.",
        "Режим работы": "Продолжительный (S1), промышленный",
        "Степень пылевлагозащиты": "IP54 / IP55",
        "Климатическое исполнение": "УХЛ 4 по ГОСТ 15150-69",
        "Регламентный смазочный материал": "Компрессорное / индустриальное масло по регламенту",
    }

    with pdf.table(col_widths=(70, 110), text_align=("LEFT", "LEFT"), line_height=5.5) as table:
        for param, val in spec_dict.items():
            r = table.row()
            r.cell(param)
            r.cell(val)

    pdf.ln(5)

    # Раздел 3: Регламенты технического обслуживания
    pdf.draw_section_heading("3. УТВЕРЖДЁННЫЙ ПЕРЕЧЕНЬ РЕГЛАМЕНТОВ ТО")

    if record.maintenance_tasks:
        headers = ["Код", "Наименование регламента", "Период", "След. срок", "Ответственный"]
        with pdf.table(col_widths=(22, 68, 22, 26, 42), text_align=("CENTER", "LEFT", "CENTER", "CENTER", "LEFT"), line_height=5.2) as table:
            head_row = table.row()
            for h in headers:
                head_row.cell(h)
            for t in record.maintenance_tasks:
                r = table.row()
                r.cell(t.code)
                r.cell(t.title)
                r.cell(f"{t.interval_days} дн.")
                r.cell(t.next_due_date)
                r.cell(t.responsible)
    else:
        pdf.set_font("ReportSans", "", 9)
        pdf.set_text_color(100, 105, 115)
        pdf.cell(180, 7, "Регламенты ТО формируются по мере эксплуатации агрегата.", new_x="LMARGIN", new_y="NEXT")

    pdf.draw_signatures("Главный механик предприятия", "Ответственный за эксплуатацию")
    return bytes(pdf.output())


def generate_diagnostics_pdf(
    record: EquipmentRecord,
    title: str,
    measurements: list[tuple[str, str, str]],
    conclusion: str,
) -> bytes:
    """
    Генерирует протокол технической диагностики, испытаний или виброконтроля.
    """
    pdf = MindBasePDF(doc_title="ПРОТОКОЛ ДИАГНОСТИЧЕСКОГО КОНТРОЛЯ", inv_number=record.inventory_number)
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.draw_top_banner(
        system_category="Неразрушающий контроль и диагностика",
        title="ПРОТОКОЛ ДИАГНОСТИЧЕСКИХ ИСПЫТАНИЙ",
        equipment_name=record.name,
        inv_number=record.inventory_number,
        location=record.location,
    )

    pdf.draw_section_heading(f"ТЕМА ИССЛЕДОВАНИЯ: {title.upper()}")

    pdf.set_font("ReportSans", "", 9)
    meta_rows = [
        ["Объект диагностики", f"{record.name} (мод. {record.model or '—'})"],
        ["Инвентарный / Заводской №", f"{record.inventory_number} / {record.serial_number or '—'}"],
        ["Место проведения измерений", record.location],
        ["Дата проведения контроля", date.today().strftime("%d.%m.%Y")],
    ]
    with pdf.table(col_widths=(60, 120), text_align=("LEFT", "LEFT"), line_height=5.2) as table:
        for k, v in meta_rows:
            r = table.row()
            r.cell(k)
            r.cell(v)

    pdf.ln(5)

    pdf.draw_section_heading("РЕЗУЛЬТАТЫ ИНСТРУМЕНТАЛЬНЫХ ИЗМЕРЕНИЙ")

    table_headers = ["Контрольная точка / Узел", "Измеренное значение", "Норматив / Критерий допуска"]
    with pdf.table(col_widths=(75, 50, 55), text_align=("LEFT", "CENTER", "CENTER"), line_height=5.5) as table:
        head_row = table.row()
        for h in table_headers:
            head_row.cell(h)
        for point, measured, norm in measurements:
            r = table.row()
            r.cell(point)
            r.cell(measured)
            r.cell(norm)

    pdf.ln(5)

    pdf.draw_section_heading("ЭКСПЕРТНОЕ ЗАКЛЮЧЕНИЕ И РЕКОМЕНДАЦИИ")
    pdf.set_font("ReportSans", "", 9.5)
    pdf.set_text_color(25, 30, 40)
    pdf.multi_cell(180, 5.5, conclusion)

    pdf.draw_signatures("Специалист неразрушающего контроля", "Начальник лаборатории диагностики")
    return bytes(pdf.output())


def generate_schedule_pdf(record: EquipmentRecord) -> bytes:
    """
    Генерирует утверждённый график планово-предупредительного ремонта и ТО агрегата.
    """
    pdf = MindBasePDF(doc_title="ГРАФИК ТО И РЕМОНТОВ", inv_number=record.inventory_number)
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.draw_top_banner(
        system_category="Планово-предупредительный ремонт (ППР)",
        title="ПЛАН-ГРАФИК ТЕХНИЧЕСКОГО ОБСЛУЖИВАНИЯ",
        equipment_name=record.name,
        inv_number=record.inventory_number,
        location=record.location,
    )

    pdf.draw_section_heading("1. ПЛАНОВЫЕ СРОКИ И СТОИМОСТЬ СЕРВИСНЫХ РАБОТ")

    headers = ["Код", "Регламентные работы", "Интервал", "Посл. дата", "След. дата", "Работы (₽)"]
    with pdf.table(col_widths=(20, 68, 22, 24, 24, 22), text_align=("CENTER", "LEFT", "CENTER", "CENTER", "CENTER", "RIGHT"), line_height=5.2) as table:
        head_row = table.row()
        for h in headers:
            head_row.cell(h)
        for t in record.maintenance_tasks:
            r = table.row()
            r.cell(t.code)
            r.cell(t.title)
            r.cell(f"{t.interval_days} дн.")
            r.cell(t.last_completed_date or "—")
            r.cell(t.next_due_date)
            r.cell(f"{int(t.service_cost_rub):,} ₽".replace(",", " "))

    pdf.ln(5)

    pdf.draw_section_heading("2. НОРМЫ РАСХОДА МАТЕРИАЛОВ И ЗИП НА ОБСЛУЖИВАНИЕ")

    mat_headers = ["Вид ТО", "Материал / Запчасть", "Артикул", "Норма", "Склад", "Цена (₽)"]
    has_materials = any(t.materials for t in record.maintenance_tasks)

    if has_materials:
        with pdf.table(col_widths=(22, 64, 28, 20, 20, 26), text_align=("CENTER", "LEFT", "LEFT", "CENTER", "CENTER", "RIGHT"), line_height=5.2) as table:
            head_row = table.row()
            for h in mat_headers:
                head_row.cell(h)
            for t in record.maintenance_tasks:
                for m in t.materials:
                    r = table.row()
                    r.cell(t.code)
                    r.cell(m.name)
                    r.cell(m.sku or "—")
                    r.cell(f"{m.qty_required:g} {m.unit}")
                    r.cell(f"{m.qty_in_stock:g} {m.unit}")
                    r.cell(f"{int(m.unit_price_rub):,} ₽".replace(",", " "))
    else:
        pdf.set_font("ReportSans", "", 9)
        pdf.set_text_color(100, 105, 115)
        pdf.cell(180, 7, "Нормы ТМЦ и запасных частей не заданы.", new_x="LMARGIN", new_y="NEXT")

    pdf.draw_signatures("Главный механик", "Мастер ремонтной службы")
    return bytes(pdf.output())


def generate_defect_sheet_pdf(record: EquipmentRecord) -> bytes:
    """
    Генерирует дефектную ведомость оборудования с расчётом затрат на устранение.
    """
    pdf = MindBasePDF(doc_title="ДЕФЕКТНАЯ ВЕДОМОСТЬ", inv_number=record.inventory_number)
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.draw_top_banner(
        system_category="Журнал дефектов и отказов",
        title="ДЕФЕКТНАЯ ВЕДОМОСТЬ ОБОРУДОВАНИЯ",
        equipment_name=record.name,
        inv_number=record.inventory_number,
        location=record.location,
    )

    open_defects = [d for d in record.defects if d.status == "open"]
    resolved_defects = [d for d in record.defects if d.status == "resolved"]
    total_cost = sum(d.estimated_cost_rub for d in open_defects)

    pdf.draw_section_heading(f"1. ПЕРЕЧЕНЬ ВЫЯВЛЕННЫХ ДЕФЕКТОВ (ТРЕБУЕТСЯ УСТРАНЕНИЕ)")

    if open_defects:
        headers = ["№", "Узел / Элемент", "Описание дефекта", "Степень", "Мероприятие", "Сумма (₽)"]
        with pdf.table(col_widths=(10, 36, 52, 22, 38, 22), text_align=("CENTER", "LEFT", "LEFT", "CENTER", "LEFT", "RIGHT"), line_height=5.2) as table:
            head_row = table.row()
            for h in headers:
                head_row.cell(h)
            for idx, d in enumerate(open_defects, start=1):
                r = table.row()
                r.cell(str(idx))
                r.cell(d.node)
                r.cell(d.description)
                r.cell(_SEVERITY_LABELS.get(d.severity, d.severity))
                r.cell(d.recommended_action)
                r.cell(f"{int(d.estimated_cost_rub):,} ₽".replace(",", " "))

        pdf.ln(3)
        pdf.set_fill_color(240, 243, 248)
        pdf.set_font("ReportSans", "B", 10)
        pdf.set_text_color(20, 24, 38)
        pdf.cell(140, 7, "ИТОГО ОЦЕНОЧНЫЕ ЗАТРАТЫ НА УСТРАНЕНИЕ ДЕФЕКТОВ:", border=1, align="R", fill=True)
        pdf.cell(40, 7, _format_rub(total_cost), border=1, align="R", fill=True, new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_font("ReportSans", "", 9)
        pdf.set_text_color(16, 185, 129)
        pdf.cell(180, 7, "Открытых дефектов не зафиксировано. Оборудование исправно.", new_x="LMARGIN", new_y="NEXT")

    if resolved_defects:
        pdf.ln(5)
        pdf.draw_section_heading("2. РАНЕЕ УСТРАНЁННЫЕ ДЕФЕКТЫ (АРХИВ)")
        r_headers = ["Узел", "Описание", "Принятые меры", "Дата регистрации"]
        with pdf.table(col_widths=(45, 65, 45, 25), text_align=("LEFT", "LEFT", "LEFT", "CENTER"), line_height=5.0) as table:
            head_row = table.row()
            for h in r_headers:
                head_row.cell(h)
            for d in resolved_defects:
                r = table.row()
                r.cell(d.node)
                r.cell(d.description)
                r.cell(d.recommended_action)
                r.cell(d.created_at[:10])

    pdf.draw_signatures("Мастер ремонтного участка", "Инженер по надёжности оборудования")
    return bytes(pdf.output())


def generate_budget_pdf(
    records: list[EquipmentRecord],
    title: str = "Бюджетная заявка на проведение ТО и закупку материалов",
) -> bytes:
    """
    Генерирует сводную бюджетную заявку на закупку недостающих материалов
    и проведение регламентных работ ТО по оборудованию.
    """
    pdf = MindBasePDF(doc_title="БЮДЖЕТНАЯ ЗАЯВКА НА ТО", orientation="L")
    pdf.alias_nb_pages()
    pdf.add_page()

    # В ландшафтной ориентации A4 ширина 297, поля по 15 -> рабочая ширина 267 мм
    # Верхняя плашка ландшафта
    pdf.set_fill_color(18, 20, 30)
    pdf.rect(15, 15, 267, 24, style="F")
    pdf.set_fill_color(75, 59, 255)
    pdf.rect(15, 15, 4, 24, style="F")

    pdf.set_xy(23, 17)
    pdf.set_font("ReportSans", "B", 8)
    pdf.set_text_color(0, 245, 255)
    pdf.cell(160, 4, "СВОДНОЕ ПЛАНИРОВАНИЕ ЗАТРАТ НА ТЕХНИЧЕСКОЕ ОБСЛУЖИВАНИЕ", new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(23)
    pdf.set_font("ReportSans", "B", 13)
    pdf.set_text_color(245, 247, 250)
    pdf.cell(160, 7, title, new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(23)
    pdf.set_font("ReportSans", "", 8.5)
    pdf.set_text_color(180, 185, 200)
    pdf.cell(160, 5, f"Дата формирования: {date.today().strftime('%d.%m.%Y')} | Горизонт планирования: 30 суток")

    pdf.set_xy(210, 17)
    pdf.set_fill_color(28, 32, 48)
    pdf.rect(212, 17, 65, 20, style="DF")
    pdf.set_xy(214, 19)
    pdf.set_font("ReportSans", "", 7.5)
    pdf.set_text_color(160, 165, 180)
    pdf.cell(61, 4, "СТАТУС ДОКУМЕНТА", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(214)
    pdf.set_font("ReportSans", "B", 10)
    pdf.set_text_color(0, 245, 255)
    pdf.cell(61, 5, "НА УТВЕРЖДЕНИЕ", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(214)
    pdf.set_font("ReportSans", "", 7)
    pdf.set_text_color(140, 145, 160)
    pdf.cell(61, 4, "Служба главного механика", align="C")

    pdf.set_y(44)
    pdf.set_font("ReportSans", "B", 10.5)
    pdf.set_text_color(20, 24, 38)
    pdf.cell(267, 7, "1. СВОДНАЯ ПОТРЕБНОСТЬ В ФИНАНСИРОВАНИИ ПО АГРЕГАТАМ", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(75, 59, 255)
    pdf.line(15, pdf.get_y(), 60, pdf.get_y())
    pdf.set_draw_color(220, 224, 232)
    pdf.line(60, pdf.get_y(), 282, pdf.get_y())
    pdf.ln(3)

    summary_headers = [
        "Оборудование",
        "Инв. №",
        "Вид ТО",
        "Срок ТО",
        "Статус",
        "ТМЦ к закупке (₽)",
        "Работы (₽)",
        "Требуется в бюджет (₽)",
    ]

    total_materials = 0.0
    total_service = 0.0
    total_budget = 0.0

    table_data_rows: list[list[str]] = []

    for rec in records:
        eval_data = notifications.evaluate_equipment(rec)
        for task in eval_data["tasks"]:
            b = task["budget"]
            # Включаем задачи, у которых есть потребность в бюджете или срок <= 30 дней
            if task["days_left"] <= config.BUDGET_ALERT_HORIZON_DAYS or b["budget_required_rub"] > 0:
                mat_cost = b["materials_to_buy_rub"]
                svc_cost = b["service_cost_rub"]
                req_budget = b["budget_required_rub"]

                total_materials += mat_cost
                total_service += svc_cost
                total_budget += req_budget

                table_data_rows.append([
                    rec.name,
                    rec.inventory_number,
                    f"{task['task_code']}: {task['task_title'][:30]}",
                    task["next_due_date"],
                    task["urgency_label"],
                    f"{int(mat_cost):,} ₽".replace(",", " "),
                    f"{int(svc_cost):,} ₽".replace(",", " "),
                    f"{int(req_budget):,} ₽".replace(",", " "),
                ])

    if table_data_rows:
        with pdf.table(col_widths=(55, 24, 60, 26, 38, 30, 26, 38), text_align=("LEFT", "CENTER", "LEFT", "CENTER", "CENTER", "RIGHT", "RIGHT", "RIGHT"), line_height=5.2) as table:
            head_row = table.row()
            for h in summary_headers:
                head_row.cell(h)
            for row in table_data_rows:
                r = table.row()
                for c in row:
                    r.cell(c)

        pdf.ln(3)
        pdf.set_fill_color(240, 243, 248)
        pdf.set_font("ReportSans", "B", 10)
        pdf.set_text_color(20, 24, 38)
        pdf.cell(173, 7, "ИТОГО ПО ЗАЯВКЕ:", border=1, align="R", fill=True)
        pdf.cell(30, 7, _format_rub(total_materials), border=1, align="R", fill=True)
        pdf.cell(26, 7, _format_rub(total_service), border=1, align="R", fill=True)
        pdf.cell(38, 7, _format_rub(total_budget), border=1, align="R", fill=True, new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_font("ReportSans", "", 9)
        pdf.set_text_color(16, 185, 129)
        pdf.cell(267, 7, "В ближайшие 30 суток потребности в дополнительном бюджете на ТО не выявлено.", new_x="LMARGIN", new_y="NEXT")

    pdf.draw_signatures("Главный механик", "Финансово-экономический отдел")
    return bytes(pdf.output())
