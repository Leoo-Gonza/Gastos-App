"""Errores propios de la lógica de la app."""


class ErrorDeValidacion(Exception):
    """Un dato ingresado por el usuario no es válido.

    El mensaje está escrito para mostrarse tal cual en pantalla.
    "campo" dice qué dato falló (ej. "monto", "nombre") para que la pantalla
    muestre el mensaje debajo del campo correcto. Puede ser None si el error
    no corresponde a un campo en particular.
    """

    def __init__(self, mensaje: str, campo: str | None = None) -> None:
        super().__init__(mensaje)
        self.campo = campo
