# This file was automatically generated for projects
# without default 'CMakeLists.txt' file.

FILE(GLOB_RECURSE app_sources ${CMAKE_SOURCE_DIR}/src/*.*)

# El glob anterior incluye entrada_adc.cpp junto con las fuentes existentes.
idf_component_register(SRCS ${app_sources} PRIV_REQUIRES esp_driver_dac esp_adc)
