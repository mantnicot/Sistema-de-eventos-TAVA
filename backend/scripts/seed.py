"""Datos mínimos: admin + usuario de prueba. Sin eventos ni banners."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tava.infrastructure.bootstrap import bootstrap_application


async def seed():
    await bootstrap_application()
    print("Seed completado (modo pruebas).")
    print("Admin: admin@tavateatro.com / AdminTava2026!")
    print("Prueba: prueba@tavateatro.com / PruebaTava2026!")


if __name__ == "__main__":
    asyncio.run(seed())
