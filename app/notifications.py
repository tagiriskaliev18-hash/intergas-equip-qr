from __future__ import annotations

import logging
from datetime import date
from typing import Any

from app import config, storage
from app.models import DocumentFile, EquipmentRecord, MaintenanceTask

logger = logging.getLogger(__name__)


def _format_rub_number(amount: float) -> str:
    """
    Форматирует число с разделением тысяч неразрывным пробелом (напр. 34 800).
    """
    rounded = int(round(amount))
    return f"{rounded:,}".replace(",", " ")


def calculate_task_budget(task: MaintenanceTask) -> dict[str, Any]:
    """
    Рассчитывает потребность в ЗИП и материалах на выполнение регламентного ТО:
    - по каждому материалу: qty_to_buy = max(0, required - in_stock);
    - количество позиций ТМЦ в дефиците (к закупке / поставке);
    - детализированный список материалов.
    """
    materials_detail: list[dict[str, Any]] = []
    materials_to_buy_rub = 0.0
    materials_norm_rub = 0.0
    deficit_items_count = 0

    for mat in task.materials:
        qty_req = float(mat.qty_required)
        qty_stock = float(mat.qty_in_stock)
        price = float(mat.unit_price_rub)

        qty_to_buy = max(0.0, round(qty_req - qty_stock, 3))
        if qty_to_buy > 0:
            deficit_items_count += 1
        cost_to_buy = round(qty_to_buy * price, 2)
        norm_cost = round(qty_req * price, 2)

        materials_to_buy_rub += cost_to_buy
        materials_norm_rub += norm_cost

        materials_detail.append({
            "id": mat.id,
            "name": mat.name,
            "sku": mat.sku,
            "unit": mat.unit,
            "qty_required": qty_req,
            "qty_in_stock": qty_stock,
            "qty_to_buy": qty_to_buy,
            "unit_price_rub": price,
            "cost_to_buy_rub": cost_to_buy,
            "norm_cost_rub": norm_cost,
        })

    service_cost = float(task.service_cost_rub)
    budget_required = round(materials_to_buy_rub + service_cost, 2)
    full_cycle_cost = round(materials_norm_rub + service_cost, 2)

    return {
        "task_id": task.id,
        "task_code": task.code,
        "task_title": task.title,
        "service_cost_rub": round(service_cost, 2),
        "materials_to_buy_rub": round(materials_to_buy_rub, 2),
        "materials_norm_rub": round(materials_norm_rub, 2),
        "budget_required_rub": budget_required,
        "full_cycle_cost_rub": full_cycle_cost,
        "materials_detail": materials_detail,
        "deficit_items_count": deficit_items_count,
    }


def evaluate_equipment(
    record: EquipmentRecord,
    docs: dict[str, list[DocumentFile]] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """
    Анализирует агрегат:
    - проверяет сроки и срочность регламентов ТО;
    - формирует целевые оповещения о регламентных работах и дефиците ЗИП (без денежных сумм);
    - рассчитывает потребность в ЗИП и материалах;
    - проверяет наличие паспорта и документов диагностики.
    """
    today_dt = today or date.today()

    if docs is None:
        try:
            docs = storage.list_documents(record.id)
        except Exception:
            docs = {}

    has_passport = bool(docs.get("passport"))
    has_diagnostics = bool(docs.get("diagnostics"))

    evaluated_tasks: list[dict[str, Any]] = []
    maintenance_budget_30d_rub = 0.0
    total_materials_deficit_positions = 0

    for task in record.maintenance_tasks:
        try:
            due_dt = date.fromisoformat(task.next_due_date)
        except Exception:
            due_dt = today_dt

        days_left = (due_dt - today_dt).days
        task_budget = calculate_task_budget(task)
        def_count = task_budget.get("deficit_items_count", 0)
        total_materials_deficit_positions += def_count

        if days_left < 0:
            urgency = "overdue"
            urgency_label = "Просрочено"
            alert_message = (
                f"Просрочено на {abs(days_left)} дн.! Требуется срочное проведение "
                f"{task.code} ({task.title})."
            )
        elif days_left <= config.URGENT_ALERT_HORIZON_DAYS:
            urgency = "urgent"
            urgency_label = "Срочно ТО"
            if def_count > 0:
                alert_message = (
                    f"Через {days_left} дн. плановое {task.code} ({task.title}). "
                    f"Требуется ревизия узлов и комплектация ЗИП (дефицит: {def_count} поз.)."
                )
            else:
                alert_message = (
                    f"Через {days_left} дн. плановое {task.code} ({task.title}). "
                    f"Требуется ревизия узлов и подготовка рабочего места (ЗИП укомплектован)."
                )
        elif days_left <= config.BUDGET_ALERT_HORIZON_DAYS:
            urgency = "soon"
            urgency_label = "Скоро регламентное ТО"
            if def_count > 0:
                alert_message = (
                    f"Через {days_left} дн. плановое {task.code} ({task.title}). "
                    f"Запланируйте поставку ЗИП (дефицит: {def_count} поз.)."
                )
            else:
                alert_message = (
                    f"Через {days_left} дн. плановое {task.code} ({task.title}). "
                    f"Запланируйте проведение регламентных работ (ЗИП в наличии)."
                )
        else:
            urgency = "ok"
            urgency_label = "В графике"
            alert_message = f"Плановое {task.code} запланировано на {task.next_due_date} (через {days_left} дн.)."

        if days_left <= config.BUDGET_ALERT_HORIZON_DAYS:
            maintenance_budget_30d_rub += task_budget["budget_required_rub"]

        evaluated_tasks.append({
            "task_id": task.id,
            "task_code": task.code,
            "task_title": task.title,
            "interval_days": task.interval_days,
            "last_completed_date": task.last_completed_date,
            "next_due_date": task.next_due_date,
            "responsible": task.responsible,
            "days_left": days_left,
            "urgency": urgency,
            "urgency_label": urgency_label,
            "alert_message": alert_message,
            "budget": task_budget,
            "deficit_items_count": def_count,
            "notes": task.notes,
        })

    # Сортировка задач: просроченные и срочные первыми
    evaluated_tasks.sort(key=lambda t: t["days_left"])

    open_defects = [d for d in record.defects if d.status == "open"]
    open_defects_count = len(open_defects)
    defects_budget_rub = round(sum(float(d.estimated_cost_rub) for d in open_defects), 2)
    maintenance_budget_30d_rub = round(maintenance_budget_30d_rub, 2)
    total_budget_needed_rub = round(maintenance_budget_30d_rub + defects_budget_rub, 2)

    due_window_tasks = [t for t in evaluated_tasks if t["days_left"] <= config.BUDGET_ALERT_HORIZON_DAYS]
    total_materials_needed_rub = round(
        sum(float(t["budget"]["materials_to_buy_rub"]) for t in due_window_tasks), 2
    )
    total_services_rub = round(
        sum(float(t["budget"]["service_cost_rub"]) for t in due_window_tasks), 2
    )
    urgent_alerts = [t for t in evaluated_tasks if t["urgency"] in ("overdue", "urgent")]
    budget_alerts = [t for t in evaluated_tasks if t["urgency"] == "soon"]
    next_task = evaluated_tasks[0] if evaluated_tasks else None

    return {
        "id": record.id,
        "equipment_id": record.id,
        "name": record.name,
        "inventory_number": record.inventory_number,
        "model": record.model,
        "location": record.location,
        "status": record.status,
        "has_passport": has_passport,
        "has_diagnostics": has_diagnostics,
        "next_maintenance_date": next_task["next_due_date"] if next_task else None,
        "next_maintenance_code": next_task["task_code"] if next_task else None,
        "days_until_maintenance": next_task["days_left"] if next_task else None,
        "maintenance_status": next_task["urgency"] if next_task else "ok",
        "tasks": evaluated_tasks,
        "urgent_alerts": urgent_alerts,
        "budget_alerts": budget_alerts,
        "materials_deficit_items_count": total_materials_deficit_positions,
        "open_defects_count": open_defects_count,
        "defects_budget_rub": defects_budget_rub,
        "total_materials_needed_rub": total_materials_needed_rub,
        "total_services_rub": total_services_rub,
        "maintenance_budget_30d_rub": maintenance_budget_30d_rub,
        "total_budget_needed_rub": total_budget_needed_rub,
        "total_budget_rub": total_budget_needed_rub,
    }


def build_overview(today: date | None = None) -> dict[str, Any]:
    """
    Формирует общую сводку по всему оборудованию предприятия:
    - список агрегатов с их оценками;
    - упорядоченный список предупреждений (просроченные первыми);
    - агрегированные технические показатели (сроки, ЗИП, дефекты).
    """
    today_dt = today or date.today()
    records = storage.list_equipment()

    equipment_list: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []

    for record in records:
        eval_res = evaluate_equipment(record, today=today_dt)
        equipment_list.append(eval_res)

        for task_info in eval_res["tasks"]:
            if task_info["urgency"] in ("overdue", "urgent", "soon"):
                b = task_info["budget"]
                alerts.append({
                    "equipment_id": record.id,
                    "equipment_name": record.name,
                    "inventory_number": record.inventory_number,
                    "location": record.location,
                    "task_id": task_info["task_id"],
                    "task_code": task_info["task_code"],
                    "task_title": task_info["task_title"],
                    "next_due_date": task_info["next_due_date"],
                    "days_left": task_info["days_left"],
                    "is_overdue": task_info["days_left"] < 0,
                    "urgency": task_info["urgency"],
                    "urgency_label": task_info["urgency_label"],
                    "message": task_info["alert_message"],
                    "deficit_items_count": task_info.get("deficit_items_count", 0),
                    "budget_required_rub": b["budget_required_rub"],
                    "total_cost": b["budget_required_rub"],
                    "materials_to_buy_rub": b["materials_to_buy_rub"],
                    "materials_cost": b["materials_to_buy_rub"],
                    "service_cost_rub": b["service_cost_rub"],
                })

    # Сортировка предупреждений по дням (наиболее просроченные первыми)
    alerts.sort(key=lambda a: a["days_left"])

    total_equipment = len(records)
    overdue_count = sum(1 for a in alerts if a["urgency"] == "overdue")
    upcoming_30d_count = sum(1 for a in alerts if a["urgency"] in ("urgent", "soon"))
    open_defects_count = sum(e["open_defects_count"] for e in equipment_list)
    materials_deficit_items_count = sum(e.get("materials_deficit_items_count", 0) for e in equipment_list)

    materials_budget_rub = round(sum(float(a["materials_to_buy_rub"]) for a in alerts), 2)
    service_budget_rub = round(sum(float(a["service_cost_rub"]) for a in alerts), 2)
    maintenance_budget_30d_rub = round(sum(e["maintenance_budget_30d_rub"] for e in equipment_list), 2)
    defects_budget_rub = round(sum(e["defects_budget_rub"] for e in equipment_list), 2)
    total_budget_needed_rub = round(maintenance_budget_30d_rub + defects_budget_rub, 2)

    return {
        "equipment": equipment_list,
        "alerts": alerts,
        "summary": {
            "total_equipment": total_equipment,
            "due_count": len(alerts),
            "overdue_count": overdue_count,
            "upcoming_30d_count": upcoming_30d_count,
            "open_defects_count": open_defects_count,
            "materials_deficit_items_count": materials_deficit_items_count,
            "materials_budget_rub": materials_budget_rub,
            "service_budget_rub": service_budget_rub,
            "maintenance_budget_30d_rub": maintenance_budget_30d_rub,
            "defects_budget_rub": defects_budget_rub,
            "total_budget_needed_rub": total_budget_needed_rub,
            "total_budget_rub": total_budget_needed_rub,
        },
    }
