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
    draw.text((35, 25), "MIND EQUIP // ПРОТОКОЛ ФОТООСМОТРА ОБОРУДОВАНИЯ", fill=(0, 245, 255))
    draw.text((35, 45), f"{equipment_name} [ИНВ. № {inv_number}]", fill=(245, 247, 250))

    # Плашка статуса
    draw.rectangle([w - 230, 25, w - 25, 70], fill=status_color)
    draw.text((w - 215, 40), status_text, fill=(255, 255, 255))

    # Центральное поле узла
    draw.rectangle([50, 120, w - 50, h - 60], outline=(75, 85, 115), width=2, fill=(22, 25, 38))
    draw.rectangle([50, 120, w - 50, 155], fill=(32, 38, 56))
    draw.text((70, 130), f"КОНТРОЛИРУЕМЫЙ УЗЕЛ: {node.upper()}", fill=(240, 243, 250))

    draw.text((70, 180), f"Дата и время фиксации: {date.today().strftime('%d.%m.%Y')} 10:15", fill=(180, 185, 200))
    draw.text((70, 215), f"Устройство регистрации: Промышленный терминал инспектора (Wi-Fi)", fill=(180, 185, 200))
    draw.text((70, 250), f"Геолокация / Отметка: Цеховой контур, пост оператора", fill=(180, 185, 200))
    draw.text((70, 285), f"Контроль утечек и тепловизионная оценка: выполнено", fill=(180, 185, 200))

    draw.text((70, 360), "MIND INDUSTRIAL ECOSYSTEM // VERIFIED ASSET", fill=(0, 245, 255))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def seed_demo_data_if_empty() -> bool:
    """
    Инициализирует демонстрационную базу данных оборудования с 3 реальными агрегатами,
    если хранилище ещё пусто.
    Возвращает True если данные были созданы, иначе False.
    """
    root = storage.get_docs_root()
    reg_path = root / "registry.json"
    if reg_path.exists():
        existing = storage.list_equipment()
        if existing:
            return False

    logger.info("Инициализация демонстрационной базы оборудования...")
    today = date.today()

    # -------------------------------------------------------------------------
    # 1. Винтовой компрессор Ремеза ВК50Е-10
    # -------------------------------------------------------------------------
    eq1_input = EquipmentCreateInput(
        id="kompressor-vk50",
        name="Винтовой компрессор Ремеза ВК50Е-10",
        inventory_number="КМ-0104",
        model="ВК50Е-10",
        serial_number="RZ-5010-8492",
        manufacturer="ЗАО «Ремеза»",
        commission_year=2021,
        location="Компрессорная станция №1",
        status="good",
    )
    rec1 = storage.create_equipment(eq1_input)

    # Паспорт PDF
    p1_bytes = pdf_generator.generate_passport_pdf(
        rec1,
        specs={
            "Производительность": "5.5 м³/мин (5500 л/мин)",
            "Рабочее давление": "10 бар (1.0 МПа)",
            "Мощность электродвигателя": "37 кВт (3000 об/мин)",
            "Винтовой блок": "Termomeccanica SCA 10",
            "Тип охлаждения": "Воздушное принудительное",
            "Заправочный объём масла": "20 литров (VDL-100)",
        },
    )
    storage.save_pdf_document(rec1.id, "passport", "passport_remeza_vk50e.pdf", p1_bytes)

    # Протокол вибродиагностики PDF
    diag1_bytes = pdf_generator.generate_diagnostics_pdf(
        rec1,
        title="Виброакустическая диагностика подшипниковых узлов и винтового блока",
        measurements=[
            ("Подшипник передний винтового блока (СКЗ V)", "1.8 мм/с", "До 2.8 мм/с (Норма, класс А)"),
            ("Подшипник задний винтового блока (СКЗ V)", "1.6 мм/с", "До 2.8 мм/с (Норма, класс А)"),
            ("Передний подшипник электродвигателя 37 кВт", "1.2 мм/с", "До 2.3 мм/с (Норма, класс А)"),
            ("Температура корпуса винтовой пары", "+74 °C", "До +95 °C (В допуске)"),
            ("Остаточный ресурс подшипников", "> 8500 ч", "Плановая замена через 12000 ч"),
        ],
        conclusion=(
            "Вибрационное состояние компрессора Ремеза ВК50Е-10 соответствует ГОСТ ИСО 10816-3 (класс А). "
            "Признаков кавитации, дисбаланса роторов и дефектов дорожек качения подшипников не обнаружено. "
            "Оборудование допущено к непрерывной эксплуатации до очередного планового ТО-2."
        ),
    )
    storage.save_pdf_document(rec1.id, "diagnostics", "diagnostics_vibration_2026.pdf", diag1_bytes)

    # Регламент ТО-2 через +9 дней
    due_to2 = (today + timedelta(days=9)).isoformat()
    task1 = MaintenanceTaskInput(
        code="ТО-2",
        title="Регламентное техническое обслуживание (2000 моточасов)",
        interval_days=90,
        last_completed_date=(today - timedelta(days=81)).isoformat(),
        next_due_date=due_to2,
        responsible="Служба главного механика (участок пневмосистем)",
        service_cost_rub=12000.0,
        notes="Замена компрессорного масла, всех фильтрующих элементов и проверка натяжения ремней",
        materials=[
            MaintenanceMaterialInput(
                name="Масло компрессорное Shell Corena S4 R 46 (VDL-100)",
                sku="OIL-SH-46",
                unit="л",
                qty_required=20.0,
                qty_in_stock=4.0,
                unit_price_rub=850.0,
            ),
            MaintenanceMaterialInput(
                name="Фильтр-сепаратор воздушно-масляный",
                sku="SEP-VK50-01",
                unit="шт.",
                qty_required=1.0,
                qty_in_stock=0.0,
                unit_price_rub=5200.0,
            ),
            MaintenanceMaterialInput(
                name="Масляный фильтр тонкой очистки",
                sku="FLT-OIL-50",
                unit="шт.",
                qty_required=1.0,
                qty_in_stock=0.0,
                unit_price_rub=2100.0,
            ),
            MaintenanceMaterialInput(
                name="Воздушный фильтр панельный",
                sku="FLT-AIR-VK",
                unit="шт.",
                qty_required=1.0,
                qty_in_stock=0.0,
                unit_price_rub=1900.0,
            ),
        ],
    )
    storage.upsert_maintenance_task(rec1.id, task1)

    # График ТО PDF
    rec1 = storage.get_equipment(rec1.id) or rec1
    sched1_bytes = pdf_generator.generate_schedule_pdf(rec1)
    storage.save_pdf_document(rec1.id, "schedule", "schedule_to2_vk50.pdf", sched1_bytes)

    # Фотоосмотр
    img1_bytes = _create_synthetic_nameplate_image(
        equipment_name="Винтовой компрессор ВК50Е-10",
        inv_number="КМ-0104",
        node="Винтовой блок и маслосистема",
        status_text="ИСПРАВНО",
        status_color=(16, 185, 129),
    )
    storage.save_photo_inspection(
        equipment_id=rec1.id,
        filename="inspection_vk50.jpg",
        content=img1_bytes,
        condition="good",
        node="Винтовой блок и маслосистема",
        comment="Штатный осмотр перед ТО-2. Подтёков масла нет, вибрация в пределах нормы.",
    )

    # -------------------------------------------------------------------------
    # 2. Насосный агрегат Grundfos CR 32-4
    # -------------------------------------------------------------------------
    eq2_input = EquipmentCreateInput(
        id="nasos-cr32-02",
        name="Насосный агрегат Grundfos CR 32-4",
        inventory_number="НС-0219",
        model="CR 32-4 A-F-A-E-HQQE",
        serial_number="GF-9651-7714",
        manufacturer="Grundfos Holding A/S",
        commission_year=2019,
        location="Участок водоподготовки, Цех №2",
        status="attention",
    )
    rec2 = storage.create_equipment(eq2_input)

    # Паспорт PDF
    p2_bytes = pdf_generator.generate_passport_pdf(
        rec2,
        specs={
            "Номинальная подача": "32 м³/ч",
            "Номинальный напор": "62 м вод. ст. (6.2 бар)",
            "Мощность двигателя": "7.5 кВт (2900 об/мин)",
            "Тип уплотнения вала": "Картриджное одинарное HQQE",
            "Диапазон температур": "-20 °C ... +120 °C",
            "Материал проточной части": "Нержавеющая сталь AISI 304",
        },
    )
    storage.save_pdf_document(rec2.id, "passport", "passport_grundfos_cr32.pdf", p2_bytes)

    # Внимание: папка diagnostics/ намеренно остаётся ПУСТОЙ (демонстрация кейса)

    # Регламент ТО-1 просрочен на 2 дня
    due_to1_nasos = (today - timedelta(days=2)).isoformat()
    task2 = MaintenanceTaskInput(
        code="ТО-1",
        title="Ежемесячное ТО и ревизия подшипниковых узлов насоса",
        interval_days=30,
        last_completed_date=(today - timedelta(days=32)).isoformat(),
        next_due_date=due_to1_nasos,
        responsible="Слесарная группа цеха водоподготовки",
        service_cost_rub=4500.0,
        notes="Проверка зазоров муфты, смазка подшипников двигателя, контроль утечек сальника",
        materials=[
            MaintenanceMaterialInput(
                name="Смазка высокотемпературная водостойкая Mobil Polyrex EM",
                sku="MOBIL-EM-400",
                unit="туба",
                qty_required=0.5,
                qty_in_stock=0.5,
                unit_price_rub=1200.0,
            ),
        ],
    )
    storage.upsert_maintenance_task(rec2.id, task2)

    # Дефектная ведомость: открытый дефект торцевого уплотнения
    def2 = DefectInput(
        node="Торцевое уплотнение вала насоса",
        description="Капельная течь перекачиваемой среды через картриджное уплотнение (до 15 капель/мин)",
        severity="high",
        recommended_action="Замена картриджного торцевого уплотнения HQQE и проверка центровки муфты",
        estimated_cost_rub=18500.0,
    )
    storage.add_defect(rec2.id, def2)

    rec2 = storage.get_equipment(rec2.id) or rec2
    sched2_bytes = pdf_generator.generate_schedule_pdf(rec2)
    storage.save_pdf_document(rec2.id, "schedule", "schedule_to1_cr32.pdf", sched2_bytes)

    defect2_bytes = pdf_generator.generate_defect_sheet_pdf(rec2)
    storage.save_pdf_document(rec2.id, "defects", "defect_sheet_cr32.pdf", defect2_bytes)

    # Фотоосмотр дефекта со статусом attention
    img2_bytes = _create_synthetic_nameplate_image(
        equipment_name="Насосный агрегат Grundfos CR 32-4",
        inv_number="НС-0219",
        node="Торцевое уплотнение",
        status_text="ВНИМАНИЕ (ТЕЧЬ)",
        status_color=(245, 158, 11),
    )
    storage.save_photo_inspection(
        equipment_id=rec2.id,
        filename="inspection_cr32_leak.jpg",
        content=img2_bytes,
        condition="attention",
        node="Торцевое уплотнение вала",
        comment="Фиксация капельной течи сальника на фланце насосной части. Требуется замена картриджа.",
    )

    # -------------------------------------------------------------------------
    # 3. Токарный станок с ЧПУ 16К20Ф3
    # -------------------------------------------------------------------------
    eq3_input = EquipmentCreateInput(
        id="stanok-16k20-f3",
        name="Токарный станок с ЧПУ 16К20Ф3",
        inventory_number="СТ-0412",
        model="16К20Ф3С39",
        serial_number="KZ-1620-3301",
        manufacturer="Московский станкостроительный завод «Красный пролетарий»",
        commission_year=2018,
        location="Механосборочный цех, пролёт Б",
        status="good",
    )
    rec3 = storage.create_equipment(eq3_input)

    # Паспорт PDF
    p3_bytes = pdf_generator.generate_passport_pdf(
        rec3,
        specs={
            "Наибольший диаметр обработки": "400 мм",
            "Длина обрабатываемой детали (РМЦ)": "1000 мм",
            "Система ЧПУ": "NC-210 / Балт-Систем",
            "Мощность главного привода": "11 кВт",
            "Диапазон частот вращения шпинделя": "10 ... 2000 об/мин",
            "Масса станка": "4000 кг",
        },
    )
    storage.save_pdf_document(rec3.id, "passport", "passport_stanok_16k20f3.pdf", p3_bytes)

    # Протокол проверки точности ШВП в diagnostics
    diag3_bytes = pdf_generator.generate_diagnostics_pdf(
        rec3,
        title="Протокол лазерной интерферометрии и проверки кинематической точности ШВП",
        measurements=[
            ("Люфт шарико-винтовой пары оси X", "0.004 мм", "До 0.010 мм (В допуске)"),
            ("Позиционирование по оси Z (на длине 500 мм)", "0.008 мм", "До 0.015 мм (В допуске)"),
            ("Радиальное биение конуса шпинделя", "0.003 мм", "До 0.005 мм (В норме)"),
            ("Давление в гидросистеме зажима патрона", "3.0 МПа", "3.0 ± 0.2 МПа (Норма)"),
        ],
        conclusion=(
            "Геометрическая и кинематическая точность токарного станка 16К20Ф3 соответствует классу П (повышенная точность) "
            "по ГОСТ 8-82. Люфты по осям X и Z компенсированы системой ЧПУ. Станок готов к прецизионной обработке."
        ),
    )
    storage.save_pdf_document(rec3.id, "diagnostics", "diagnostics_accuracy_shvp.pdf", diag3_bytes)

    # ТО-1 через +45 дней (в графике)
    due_to1_stanok = (today + timedelta(days=45)).isoformat()
    task3 = MaintenanceTaskInput(
        code="ТО-1",
        title="Периодическое ТО гидравлической станции и направляющих",
        interval_days=60,
        last_completed_date=(today - timedelta(days=15)).isoformat(),
        next_due_date=due_to1_stanok,
        responsible="Бригада ремонта станков с ЧПУ",
        service_cost_rub=8000.0,
        notes="Замена картриджа напорного фильтра гидравлики, очистка бака СОЖ, контроль натяжения ремней",
        materials=[
            MaintenanceMaterialInput(
                name="Масло гидравлическое И-20А (ГОСТ 20799-88)",
                sku="OIL-I20A-20",
                unit="л",
                qty_required=15.0,
                qty_in_stock=30.0,
                unit_price_rub=180.0,
            ),
            MaintenanceMaterialInput(
                name="Фильтроэлемент напорный 10 мкм (Н-240)",
                sku="FLT-HYD-10M",
                unit="шт.",
                qty_required=1.0,
                qty_in_stock=2.0,
                unit_price_rub=2400.0,
            ),
        ],
    )
    storage.upsert_maintenance_task(rec3.id, task3)

    rec3 = storage.get_equipment(rec3.id) or rec3
    sched3_bytes = pdf_generator.generate_schedule_pdf(rec3)
    storage.save_pdf_document(rec3.id, "schedule", "schedule_to1_stanok.pdf", sched3_bytes)

    img3_bytes = _create_synthetic_nameplate_image(
        equipment_name="Токарный станок 16К20Ф3",
        inv_number="СТ-0412",
        node="Суппортная группа и шпиндель",
        status_text="ИСПРАВНО",
        status_color=(16, 185, 129),
    )
    storage.save_photo_inspection(
        equipment_id=rec3.id,
        filename="inspection_stanok_spindle.jpg",
        content=img3_bytes,
        condition="good",
        node="Суппортная группа и шпиндель",
        comment="Плановый контроль направляющих станины. Геометрия в допуске.",
    )

    logger.info("Демонстрационная база успешно инициализирована (3 единицы оборудования).")
    return True
