from fastapi import HTTPException

from tava.presentation.api.error_handlers import _error_body


def raise_user_error(status_code: int, code: str, message: str) -> None:
    raise HTTPException(
        status_code=status_code,
        detail=_error_body(
            error_type="user",
            code=code,
            message=message,
            status_code=status_code,
        ),
    )


def raise_system_error(status_code: int, code: str, message: str) -> None:
    raise HTTPException(
        status_code=status_code,
        detail=_error_body(
            error_type="system",
            code=code,
            message=message,
            status_code=status_code,
        ),
    )
