"""Colores y tamaños de letra de la app (docs/diseno.md §2.1 y §2.2)."""

import flet as ft

# Azul petróleo de los encabezados de la planilla. Flet arma con este color
# toda la paleta de Material 3 (fondos, botones, bordes) en claro y en oscuro.
PRIMARIO = "#1F5F7A"

# Colores neutros: se usan los "roles" de Material en vez de colores fijos,
# así cambian solos entre tema claro y oscuro.
TEXTO_SECUNDARIO = ft.Colors.ON_SURFACE_VARIANT
SUPERFICIE_VARIANTE = ft.Colors.SURFACE_CONTAINER_HIGHEST
BORDE = ft.Colors.OUTLINE_VARIANT

# Tamaños de letra (§2.2). Como constantes, para cambiarlos todos de una vez.
TAM_TITULO = 24
TAM_SECCION = 16
TAM_TEXTO = 15
TAM_AYUDA = 13

# Colores de estado (§2.1). Estos sí van fijos porque tienen que ser exactos
# (contraste mínimo 4,5:1), uno por tema.
_SEMANTICOS = {
    ft.Brightness.LIGHT: {
        "positivo": "#1E7B34",
        "positivo_suave": "#E3F2E6",
        "pendiente": "#9A5800",
        "pendiente_suave": "#FFF1DC",
        "negativo": "#B3261E",
        "negativo_suave": "#FCE8E6",
        "sobre_negativo": "#FFFFFF",  # Texto encima de un fondo "negativo".
        "info": "#1F5F7A",
        "info_suave": "#E3EFF4",
    },
    ft.Brightness.DARK: {
        "positivo": "#74D38F",
        "positivo_suave": "#1D3324",
        "pendiente": "#FFB95C",
        "pendiente_suave": "#3A2C14",
        "negativo": "#FF8A80",
        "negativo_suave": "#3D1F1D",
        "sobre_negativo": "#1A1C1E",
        "info": "#8CCDF0",
        "info_suave": "#1A3340",
    },
}


def aplicar_tema(page: ft.Page) -> None:
    page.theme = ft.Theme(color_scheme_seed=PRIMARIO)
    page.dark_theme = ft.Theme(color_scheme_seed=PRIMARIO)
    # "Como el sistema": claro u oscuro según la configuración de Windows/macOS.
    page.theme_mode = ft.ThemeMode.SYSTEM


def color(page: ft.Page, rol: str) -> str:
    """Color de estado según el tema que se está viendo. Ej.: color(page, "negativo")."""
    if page.theme_mode == ft.ThemeMode.DARK:
        oscuro = True
    elif page.theme_mode == ft.ThemeMode.LIGHT:
        oscuro = False
    else:
        oscuro = page.platform_brightness == ft.Brightness.DARK
    return _SEMANTICOS[ft.Brightness.DARK if oscuro else ft.Brightness.LIGHT][rol]
