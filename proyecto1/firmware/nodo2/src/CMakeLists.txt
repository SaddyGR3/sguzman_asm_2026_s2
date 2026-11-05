# Componentes usados por el receptor UART, las dos rutas de filtrado y el DAC.
idf_component_register(
    SRCS "main.cpp" "protocolo.cpp" "recepcion.cpp" "filtros.cpp" "espectral.cpp" "salida_dac.cpp" "grabacion.cpp"
    INCLUDE_DIRS "."
    PRIV_REQUIRES esp_driver_dac esp_driver_uart esp_driver_gpio esp_timer heap
)
