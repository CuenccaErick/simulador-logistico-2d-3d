"""
Simulador Logístico Interactivo 2D/3D: Trazado de Rutas de Transporte y Áreas de Cobertura
Graficación por Computadora — ESCOM IPN — Grupo 6CV3
Autor: Erick Daniel Cuenca Castillo

Uso:
    python main.py                      # menú principal (botones para todo lo demás)
    python main.py --2d                 # simulador 2D (Tkinter, rasterización propia)
    python main.py --3d                 # mundo 3D aleatorio que se dibuja solo (OpenGL)
    python main.py --3d 1234            # el mundo número 1234 (siempre sale igual)
    python main.py --capturas carpeta   # imágenes y GIF de la vista 3D
"""

import sys


def principal(args):
    if args and args[0] == "--2d":
        from src.app import ejecutar
        ejecutar()
    elif args and args[0] == "--3d":
        from src.vista3d import ejecutar_3d
        ejecutar_3d(int(args[1]) if len(args) > 1 and args[1].isdigit() else None)
    elif args and args[0] == "--capturas":
        from src.vista3d import capturas
        capturas(args[1] if len(args) > 1 else "capturas")
    else:
        from src.menu import ejecutar
        ejecutar()


if __name__ == "__main__":
    principal(sys.argv[1:])
