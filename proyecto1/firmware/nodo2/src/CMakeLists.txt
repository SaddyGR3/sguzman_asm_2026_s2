# Componentes usados por el receptor UART, los filtros y la salida DAC.
idf_component_register(
    SRCS "main.cpp" "protocolo.cpp" "recepcion.cpp" "filtros.cpp" "salida_dac.cpp" "grabacion.cpp"
    INCLUDE_DIRS "."
    PRIV_REQUIRES esp_driver_dac esp_driver_uart esp_driver_gpio esp_timer heap
)
