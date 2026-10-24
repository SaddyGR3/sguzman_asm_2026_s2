#include <cstdio>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "dsps_fft2r.h"

extern "C" void app_main(void)
{
    int n = 0;
    while (true) {
        printf("nodo1 vivo %d\n", n++);
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}