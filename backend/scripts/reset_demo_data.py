"""Limpia la base de datos y deja solo dos usuarios para pruebas."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tava.infrastructure.demo_reset import ADMIN_EMAIL, TEST_EMAIL, reset_demo_data
from tava.infrastructure.persistence.database import AsyncSessionLocal, init_db


async def main():
    await init_db()
    async with AsyncSessionLocal() as session:
        await reset_demo_data(session, force=True)
        await session.commit()
    print(f"Base limpia. Usuarios: {ADMIN_EMAIL}, {TEST_EMAIL}")


if __name__ == "__main__":
    asyncio.run(main())
