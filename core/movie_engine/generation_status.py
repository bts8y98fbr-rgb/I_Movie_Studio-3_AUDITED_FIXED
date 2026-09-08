def aggregate_generation_tasks(tasks):
    """Return the canonical scene aggregation without mutating tasks."""

    statuses = [
        task.get("status")
        if isinstance(task, dict)
        else None
        for task in tasks
    ]

    generated = sum(
        status == "done"
        for status in statuses
    )
    failed = sum(
        status == "failed"
        for status in statuses
    )
    cancelled = sum(
        status == "cancelled"
        for status in statuses
    )
    submitted = sum(
        status == "submitted"
        for status in statuses
    )
    running = sum(
        status == "running"
        for status in statuses
    )
    pending = sum(
        status not in (
            "done",
            "failed",
            "cancelled",
        )
        for status in statuses
    )

    if not tasks or pending > 0:
        scene_status = "pending"
    elif failed > 0 or cancelled > 0:
        scene_status = "completed_with_errors"
    else:
        scene_status = "completed"

    return {
        "generated": generated,
        "failed": failed,
        "cancelled": cancelled,
        "submitted": submitted,
        "running": running,
        "pending": pending,
        "status": scene_status,
    }
