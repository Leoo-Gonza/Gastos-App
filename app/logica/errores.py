"""Errores propios de la lógica de la app."""


class ErrorDeValidacion(Exception):
    """Un dato ingresado por el usuario no es válido.

    El mensaje está escrito para mostrarse tal cual en pantalla.
    """
