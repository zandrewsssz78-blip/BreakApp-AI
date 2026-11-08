"""Compatibilidad histórica: redirige al generador idempotente vigente.

Ejecutar `python scripts/generate_orders.py` tiene el mismo efecto que
`python scripts/expand_dataset.py`: 800 líneas sintéticas y 100 usuarios.
"""
from expand_dataset import main

if __name__ == '__main__':
    main()
