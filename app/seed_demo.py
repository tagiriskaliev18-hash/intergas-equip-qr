from __future__ import annotations

import io
import logging
from datetime import date, timedelta
from typing import Any

from PIL import Image, ImageDraw

from app import pdf_generator, storage
from app.models import (
    ConditionState,
    DefectInput,
    EquipmentCreateInput,
    MaintenanceMaterialInput,
    MaintenanceTaskInput,
)

logger = logging.getLogger(__name__)


def _create_synthetic_nameplate_image(
    equipment_name: str,
    inv_number: str,
    node: str,
    status_text: str,
    status_color: tuple[int, int, int],
) -> bytes:
    """
    Создаёт реалистичное цифровое изображение шильдика/фотофиксации узла оборудования.
    """
    w, h = 800, 500
    img = Image.new("RGB", (w, h), (18, 20, 30))
    draw = ImageDraw.Draw(img)

    # Внешняя рамка
    draw.rectangle([10, 10, w - 10, h - 10], outline=(60, 68, 90), width=2)
    # Внутренняя акцентная плашка
    draw.rectangle([15, 15, w - 15, 80], fill=(28, 32, 48))
    draw.rectangle([15, 15, 25, 80], fill=(75, 59, 255))

    # Сетка технического фона
    for x in range(30, w - 30, 40):
        draw.line([x, 90, x, h - 20], fill=(25, 28, 42), width=1)
    for y in range(90, h - 20, 40):
        draw.line([30, y, w - 30, y], fill=(25, 28, 42), width=1)

    # Заголовок
    draw.text((35, 25), "ИНТЕРГАЗ ЦЕНТРАЛЬНАЯ АЗИЯ // ПРОТОКОЛ ФОТООСМОТРА", fill=(0, 245, 255))
    draw.text((35, 45), f"{equipment_name} [ИНВ. № {inv_number}]", fill=(245, 247, 250))

    # Плашка статуса
    draw.rectangle([w - 230, 25, w - 25, 70], fill=status_color)
    draw.text((w - 215, 40), status_text, fill=(255, 255, 255))

    # Центральное поле узла
    draw.rectangle([50, 120, w - 50, h - 60], outline=(75, 85, 115), width=2, fill=(22, 25, 38))
    draw.rectangle([50, 120, w - 50, 155], fill=(32, 38, 56))
    draw.text((70, 130), f"КОНТРОЛИРУЕМЫЙ УЗЕЛ: {node.upper()}", fill=(240, 243, 250))

    draw.text((70, 180), f"Дата и время фиксации: {date.today().strftime('%d.%m.%Y')} 10:15", fill=(180, 185, 200))
    draw.text((70, 215), "Устройство регистрации: Мобильный терминал инженера (Wi-Fi)", fill=(180, 185, 200))
    draw.text((70, 250), "Геолокация / Отметка: Технологическая площадка ЛПУ / ГРС / КС", fill=(180, 185, 200))
    draw.text((70, 285), "Контроль герметичности, вибрации и тепловизионная оценка: выполнено", fill=(180, 185, 200))

    draw.text((70, 360), "ИНТЕРГАЗ ЦЕНТРАЛЬНАЯ АЗИЯ · ЛПУ / ГРС / КС // VERIFIED ASSET", fill=(0, 245, 255))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def seed_demo_data_if_empty(force_reseed: bool = False) -> bool:
    """
    Инициализирует демонстрационную базу данных оборудования АО «Интергаз Центральная Азия»
    (газоперекачивающий агрегат ГПА КС, узел редуцирования ГРС, магистральный шаровой кран ЛПУ).
    """
    root = storage.get_docs_root()
    reg_path = root / "registry.json"
    if not force_reseed and reg_path.exists():
        existing = storage.list_equipment()
        if existing:
            return False

    logger.info("Инициализация профильной базы оборудования Интергаз Центральная Азия (КС, ГРС, ЛПУ)...")
    today = date.today()

    # -------------------------------------------------------------------------
    # 1. КС (Компрессорная станция) — Газоперекачивающий агрегат ГПА-Ц-16Л
    # -------------------------------------------------------------------------
    eq1_input = EquipmentCreateInput(
        id="ks-gpa-16-ural",
        name="Газоперекачивающий агрегат ГПА-Ц-16Л (привод ГТУ-16П, нагнетатель Н-235)",
        inventory_number="КС-ГПА-16-04",
        model="ГПА-Ц-16Л/ГТУ-16П",
        serial_number="GPA-16L-4821",
        manufacturer="ПАО «Сумское НПО» / АО «ОДК-Авиадвигатель»",
        commission_year=2019,
        location="КС-4 «Тараз» · Таразское ЛПУМГ · Компрессорный цех №1",
        status="good",
    )
    rec1 = storage.create_equipment(eq1_input)

    # Паспорт PDF
    p1_bytes = pdf_generator.generate_passport_pdf(
        rec1,
        specs={
            "Производительность нагнетателя": "32.0 млн м³/сут (22 200 м³/мин)",
            "Степень сжатия (компрессия)": "1.45 (давление на выходе 7.5 МПа / 75 кгс/см²)",
            "Привод агрегата": "Газотурбинная установка ГТУ-16П (16 МВт, 5300 об/мин)",
            "Тип нагнетателя": "Центробежный двухступенчатый нагнетатель Н-235-21-1",
            "Тип уплотнений вала": "Сухие газодинамические уплотнения (СГУ John Crane)",
            "Система воздухоочистки": "Комплексное воздухоочистительное устройство КВОУ",
            "Заправочный объём турбомасла": "1 200 литров (Тп-22С / Турбо-Т46)",
        },
    )
    storage.save_pdf_document(rec1.id, "passport", "passport_gpa_c_16l.pdf", p1_bytes)

    # Протокол вибродиагностики PDF
    diag1_bytes = pdf_generator.generate_diagnostics_pdf(
        rec1,
        title="Виброакустическая диагностика и тепловизионный контроль ГПА-Ц-16Л (агрегат №4)",
        measurements=[
            ("Виброскорость подшипника №1 нагнетателя (СКЗ V)", "1.8 мм/с", "До 4.5 мм/с (Норма по ГОСТ 30576-98)"),
            ("Виброскорость подшипника №2 нагнетателя (СКЗ V)", "2.1 мм/с", "До 4.5 мм/с (Норма по ГОСТ 30576-98)"),
            ("Вибрация опор турбокомпрессора ГТУ-16П", "3.2 мм/с", "До 7.1 мм/с (Допустимо)"),
            ("Температура упорного подшипника нагнетателя", "+72 °C", "До +95 °C (В допуске)"),
            ("Давление барьерного импульсного газа СГУ", "0.35 МПа", "0.30 - 0.40 МПа (В норме)"),
            ("Остаточный ресурс проточной части нагнетателя", "> 16 000 ч", "Плановая ревизия через 25 000 ч"),
        ],
        conclusion=(
            "Вибрационное и тепломеханическое состояние газоперекачивающего агрегата ГПА-Ц-16Л (КС-4 «Тараз») "
            "соответствует нормативным требованиям СТ РК и ПБ в газовой промышленности. "
            "Признаков помпажа, расцентровки валопровода и дефектов СГУ не выявлено. "
            "Агрегат допущен к непрерывной перекачке газа до очередного регламентного ТО-2."
        ),
    )
    storage.save_pdf_document(rec1.id, "diagnostics", "diagnostics_vibration_gpa16.pdf", diag1_bytes)

    # Регламент ТО-2 через +8 дней (попадает в окно планирования)
    due_to2 = (today + timedelta(days=8)).isoformat()
    task1 = MaintenanceTaskInput(
        code="ТО-2",
        title="Регламентное техническое обслуживание ТО-2 ГПА (2000 моточасов)",
        interval_days=90,
        last_completed_date=(today - timedelta(days=82)).isoformat(),
        next_due_date=due_to2,
        responsible="Служба эксплуатации КС Таразского ЛПУМГ",
        service_cost_rub=450000.0,
        notes="Ревизия маслосистемы, замена фильтрующих элементов топливного газа, проверка системы пожаротушения и загазованности",
        materials=[
            MaintenanceMaterialInput(
                name="Масло турбинное Тп-22С (ГОСТ 9972-74)",
                sku="OIL-TP-22S",
                unit="л",
                qty_required=80.0,
                qty_in_stock=10.0,
                unit_price_rub=2800.0,
            ),
            MaintenanceMaterialInput(
                name="Фильтроэлемент коалесцирующий очистки топливного газа ФГ-16",
                sku="FLT-FG-16C",
                unit="шт.",
                qty_required=4.0,
                qty_in_stock=0.0,
                unit_price_rub=68000.0,
            ),
            MaintenanceMaterialInput(
                name="Ремкомплект уплотнительных элементов СГУ (John Crane)",
                sku="KIT-SGU-235",
                unit="компл.",
                qty_required=1.0,
                qty_in_stock=0.0,
                unit_price_rub=180000.0,
            ),
            MaintenanceMaterialInput(
                name="Фильтроэлемент напорный тонкой очистки турбомасла",
                sku="FLT-OIL-GTU16",
                unit="шт.",
                qty_required=2.0,
                qty_in_stock=0.0,
                unit_price_rub=36000.0,
            ),
        ],
    )
    storage.upsert_maintenance_task(rec1.id, task1)

    rec1 = storage.get_equipment(rec1.id) or rec1
    sched1_bytes = pdf_generator.generate_schedule_pdf(rec1)
    storage.save_pdf_document(rec1.id, "schedule", "schedule_to2_gpa16.pdf", sched1_bytes)

    img1_bytes = _create_synthetic_nameplate_image(
        equipment_name="ГПА-Ц-16Л (ГТУ-16П / Н-235)",
        inv_number="КС-ГПА-16-04",
        node="Газовый нагнетатель и турбоблок",
        status_text="ИСПРАВНО (НОРМА)",
        status_color=(16, 185, 129),
    )
    storage.save_photo_inspection(
        equipment_id=rec1.id,
        filename="inspection_gpa16_taraz.jpg",
        content=img1_bytes,
        condition="good",
        node="Газовый нагнетатель и турбоблок",
        comment="Осмотр технологического блока ГПА-Ц-16Л. Протечек масла и утечек газа по фланцам не обнаружено. Параметры в норме.",
    )

    # -------------------------------------------------------------------------
    # 2. ГРС (Газораспределительная станция) — Узел редуцирования Tartarini
    # -------------------------------------------------------------------------
    eq2_input = EquipmentCreateInput(
        id="grs-uzel-red-tartarini",
        name="Технологический узел редуцирования давления газа ГРС (регуляторы Tartarini FL-BP / MBN)",
        inventory_number="ГРС-УР-0219",
        model="Tartarini FL-BP DN100 / ANSI 600",
        serial_number="TART-FL-100-9844",
        manufacturer="Emerson Process Management / Tartarini",
        commission_year=2020,
        location="ГРС-1 «Шымкент» · Шымкентское ЛПУМГ · Блок редуцирования",
        status="attention",
    )
    rec2 = storage.create_equipment(eq2_input)

    # Паспорт PDF
    p2_bytes = pdf_generator.generate_passport_pdf(
        rec2,
        specs={
            "Пропускная способность линии": "150 000 нм³/ч",
            "Входное давление газа": "3.5 ... 5.5 МПа (35 ... 55 кгс/см²)",
            "Выходное редуцированное давление": "0.6 ... 1.2 МПа (6 ... 12 кгс/см²)",
            "Условный диаметр": "DN 100 (4 дюйма) ANSI 600",
            "Класс герметичности затвора": "Класс А по ГОСТ 9544-2015",
            "Предохранительный клапан": "ПЗК Tartarini BM5 / ПСК Tartarini V/50",
            "Диапазон температур газа": "-30 °C ... +60 °C",
        },
    )
    storage.save_pdf_document(rec2.id, "passport", "passport_tartarini_grs.pdf", p2_bytes)

    # Внимание: diagnostics/ намеренно остаётся ПУСТОЙ (демонстрация опциональности диагностики)

    # Регламент ТО-1 просрочен на 2 дня
    due_to1_grs = (today - timedelta(days=2)).isoformat()
    task2 = MaintenanceTaskInput(
        code="ТО-1",
        title="Ежемесячное ТО и ревизия пилотных клапанов узла редуцирования",
        interval_days=30,
        last_completed_date=(today - timedelta(days=32)).isoformat(),
        next_due_date=due_to1_grs,
        responsible="Служба ГРС Шымкентского ЛПУМГ",
        service_cost_rub=85000.0,
        notes="Проверка уставки срабатывания ПЗК, контроль перепада давления на фильтрах-сепараторах, ревизия импульсных линий",
        materials=[
            MaintenanceMaterialInput(
                name="Комплект мембран и седел Tartarini FL DN100",
                sku="KIT-TART-FL100",
                unit="компл.",
                qty_required=2.0,
                qty_in_stock=0.0,
                unit_price_rub=65000.0,
            ),
            MaintenanceMaterialInput(
                name="Фильтроэлемент газового фильтра-сепаратора ФС-100",
                sku="FLT-FS-100",
                unit="шт.",
                qty_required=1.0,
                qty_in_stock=0.0,
                unit_price_rub=48000.0,
            ),
        ],
    )
    storage.upsert_maintenance_task(rec2.id, task2)

    # Дефектная ведомость: открытый дефект пилота
    def2 = DefectInput(
        node="Пилотный регулятор управления Tartarini PRX/182",
        description="Нестабильность уставки выходного давления при переменных расходах (пропуск по седлу пилота до 0.05 МПа выше нормы)",
        severity="high",
        recommended_action="Замена седла и дроссельного элемента пилотного клапана с калибровкой пружины уставки",
        estimated_cost_rub=135000.0,
    )
    storage.add_defect(rec2.id, def2)

    rec2 = storage.get_equipment(rec2.id) or rec2
    sched2_bytes = pdf_generator.generate_schedule_pdf(rec2)
    storage.save_pdf_document(rec2.id, "schedule", "schedule_to1_grs.pdf", sched2_bytes)

    defect2_bytes = pdf_generator.generate_defect_sheet_pdf(rec2)
    storage.save_pdf_document(rec2.id, "defects", "defect_sheet_grs_tartarini.pdf", defect2_bytes)

    # Фотоосмотр дефекта
    img2_bytes = _create_synthetic_nameplate_image(
        equipment_name="Узел редуцирования Tartarini FL-BP",
        inv_number="ГРС-УР-0219",
        node="Пилотный клапан PRX/182",
        status_text="ВНИМАНИЕ (ДЕФЕКТ)",
        status_color=(245, 158, 11),
    )
    storage.save_photo_inspection(
        equipment_id=rec2.id,
        filename="inspection_grs_pilot_leak.jpg",
        content=img2_bytes,
        condition="attention",
        node="Пилотный регулятор давления",
        comment="Фиксация отклонения выходного давления при малых расходах газа. Требуется ревизия седла пилота PRX/182.",
    )

    # -------------------------------------------------------------------------
    # 3. ЛПУ (Линейная часть МГ) — Магистральный шаровой кран DN1000 PN80 с ПГП
    # -------------------------------------------------------------------------
    eq3_input = EquipmentCreateInput(
        id="lpu-kran-dn1000",
        name="Кран шаровой магистральный DN1000 PN80 с пневмогидроприводом (ПГП)",
        inventory_number="ЛПУ-КШ-0412",
        model="КШ.1000.080.ПГП (с автоматом аварийного закрытия ААЗК)",
        serial_number="KSH-1000-80-0412",
        manufacturer="АО «Тяжпромарматура» / Böhmer Armaturen",
        commission_year=2018,
        location="МГ «Бухара — Урал» · 428 км · Линейная часть Актюбинского ЛПУМГ",
        status="good",
    )
    rec3 = storage.create_equipment(eq3_input)

    # Паспорт PDF
    p3_bytes = pdf_generator.generate_passport_pdf(
        rec3,
        specs={
            "Номинальный диаметр": "DN 1000 мм (40 дюймов)",
            "Рабочее давление": "PN 8.0 МПа (80 кгс/см²)",
            "Тип привода": "Пневмогидравлический привод с гидробаком от давления транспортируемого газа",
            "Время полного перекрытия": "18 ... 24 секунд",
            "Система аварийной защиты": "Автомат аварийного закрытия крана ААЗК по темпу падения давления",
            "Класс герметичности затвора": "Класс А по ГОСТ 9544-2015",
            "Климатическое исполнение": "ХЛ1 (-60 °C ... +50 °C)",
        },
    )
    storage.save_pdf_document(rec3.id, "passport", "passport_kran_dn1000_pgp.pdf", p3_bytes)

    # Протокол ревизии ПГП и ААЗК
    diag3_bytes = pdf_generator.generate_diagnostics_pdf(
        rec3,
        title="Акт проверки работоспособности узла перекрытия и времени срабатывания ААЗК",
        measurements=[
            ("Время перекрытия крана от ПГП", "19.5 сек", "18 - 25 сек (В норме)"),
            ("Герметичность уплотнения по шаровой пробке", "0 пузырьков/мин", "Класс А по ГОСТ 9544 (Герметично)"),
            ("Давление в гидросистеме привода", "7.8 МПа", "7.5 - 8.2 МПа (В допуске)"),
            ("Срабатывание пилота ААЗК по темпу падения давления", "Сработало (0.12 МПа/мин)", "0.10 - 0.15 МПа/мин (Норма)"),
            ("Состояние изоляционного покрытия шарниров", "Без отслоений", "Норма по СТ РК"),
        ],
        conclusion=(
            "Магистральный шаровой кран DN1000 PN80 на 428 км МГ «Бухара — Урал» проверен на полное открытие/закрытие. "
            "Пневмогидропривод и узел аварийного перекрытия ААЗК исправны. Запорная арматура готова к транспортировке газа."
        ),
    )
    storage.save_pdf_document(rec3.id, "diagnostics", "diagnostics_kran_aazk.pdf", diag3_bytes)

    # ТО-1 через +35 дней (в графике)
    due_to1_kran = (today + timedelta(days=35)).isoformat()
    task3 = MaintenanceTaskInput(
        code="ТО-1",
        title="Сезонное техническое обслуживание линейной запорной арматуры и узла ПГП",
        interval_days=60,
        last_completed_date=(today - timedelta(days=25)).isoformat(),
        next_due_date=due_to1_kran,
        responsible="Линейно-эксплуатационная служба (ЛЭС) Актюбинского ЛПУМГ",
        service_cost_rub=120000.0,
        notes="Набивка уплотнительной пасты в седла крана, проверка уровня масла в гидробаках ПГП, контроль состояния дренажных линий",
        materials=[
            MaintenanceMaterialInput(
                name="Смазка уплотнительная синтетическая Арматол-238 (для шаровых пробок)",
                sku="LUB-ARM-238",
                unit="кг",
                qty_required=10.0,
                qty_in_stock=15.0,
                unit_price_rub=8500.0,
            ),
            MaintenanceMaterialInput(
                name="Гидравлическое масло для привода ПГП (низкотемпературное ВМГЗ)",
                sku="OIL-VMGZ-20",
                unit="л",
                qty_required=20.0,
                qty_in_stock=20.0,
                unit_price_rub=3400.0,
            ),
        ],
    )
    storage.upsert_maintenance_task(rec3.id, task3)

    rec3 = storage.get_equipment(rec3.id) or rec3
    sched3_bytes = pdf_generator.generate_schedule_pdf(rec3)
    storage.save_pdf_document(rec3.id, "schedule", "schedule_to1_kran.pdf", sched3_bytes)

    img3_bytes = _create_synthetic_nameplate_image(
        equipment_name="Кран шаровой DN1000 PN80 с ПГП",
        inv_number="ЛПУ-КШ-0412",
        node="Узел перекрытия и пневмогидропривод",
        status_text="ИСПРАВНО (НОРМА)",
        status_color=(16, 185, 129),
    )
    storage.save_photo_inspection(
        equipment_id=rec3.id,
        filename="inspection_kran_dn1000.jpg",
        content=img3_bytes,
        condition="good",
        node="Узел перекрытия и пневмогидропривод",
        comment="Плановый осмотр кранового узла на 428 км МГ «Бухара — Урал». Подтеков гидрожидкости нет, положение затвора — «Открыто».",
    )

    logger.info("Профильная база АО «Интергаз Центральная Азия» успешно инициализирована (ГПА КС, Узел редуцирования ГРС, Кран ЛПУ).")
    return True
