from pathlib import Path
import json
import numpy as np
import matplotlib.pyplot as plt
from scipy.io import wavfile
from scipy.signal import butter, sosfiltfilt, chirp, get_window
RAIZ = Path(__file__).resolve().parents[1]

def rms(x):
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64))))

def snr_db(clean, observed):
    error = observed - clean
    return 10*np.log10((np.sum(clean**2)+1e-15)/(np.sum(error**2)+1e-15))

def fade(x, fs, ms=20):
    n = min(int(fs*ms/1000), len(x)//2)
    if n > 0:
        ramp = np.sin(np.linspace(0, np.pi/2, n))**2
        x = x.copy(); x[:n] *= ramp; x[-n:] *= ramp[::-1]
    return x

def normalizar_conjunto(*signals, peak=0.8):
    maximum = max(np.max(np.abs(x)) for x in signals)
    gain = peak/maximum if maximum > 0 else 1.0
    return [x*gain for x in signals], gain

def generar_limpia(kind, t, freqs, amps, phases_deg, rng):
    if kind == 'tono':
        return amps[0]*np.sin(2*np.pi*freqs[0]*t + np.deg2rad(phases_deg[0]))
    if kind == 'multitono':
        return sum(a*np.sin(2*np.pi*f*t + np.deg2rad(p)) for f,a,p in zip(freqs,amps,phases_deg))
    if kind == 'chirp':
        return chirp(t, f0=freqs[0], f1=freqs[-1], t1=t[-1], method='linear')
    if kind == 'armonicos':
        f0 = freqs[0]
        return sum((1/k)*np.sin(2*np.pi*k*f0*t + rng.uniform(-np.pi,np.pi)) for k in range(1,6))
    if kind == 'transitoria':
        env = np.exp(-5*(t % 1.0))*(np.sin(2*np.pi*2*t)>0)
        return env*np.sin(2*np.pi*freqs[0]*t)
    raise ValueError(f'Tipo de señal no reconocido: {kind}')

def ruido_banda(n, fs, band, rng):
    low, high = band
    if not (0 < low < high < fs/2):
        raise ValueError(f'BANDA_RUIDO debe cumplir 0 < low < high < {fs/2}')
    sos = butter(6, [low, high], btype='bandpass', fs=fs, output='sos')
    return sosfiltfilt(sos, rng.standard_normal(n))

def generar_ruido(kind, t, fs, f_int, band, impulses, rng):
    n = len(t)
    tonal = np.sin(2*np.pi*f_int*t + rng.uniform(-np.pi,np.pi))
    red = sum((1/k)*np.sin(2*np.pi*60*k*t + rng.uniform(-np.pi,np.pi)) for k in range(1,5))
    white = rng.standard_normal(n)
    band_noise = ruido_banda(n, fs, band, rng)
    impulse = np.zeros(n)
    locations = rng.choice(np.arange(int(.1*fs), n-int(.1*fs)), size=min(impulses,max(1,n//100)), replace=False)
    for loc in locations:
        width = max(2, int(rng.uniform(.0005,.004)*fs))
        stop = min(n, loc+width)
        impulse[loc:stop] += rng.choice([-1,1])*np.hanning(2*(stop-loc))[:stop-loc]
    options = {'tonal':tonal, 'red_60hz':red, 'blanco':white, 'banda':band_noise, 'impulsivo':impulse}
    if kind == 'mixto':
        return 0.55*tonal + 0.30*band_noise + 0.15*impulse
    if kind not in options: raise ValueError(f'Tipo de ruido no reconocido: {kind}')
    return options[kind]

def escalar_ruido_para_snr(clean, noise, target_db):
    target_noise_rms = rms(clean)/(10**(target_db/20))
    return noise*(target_noise_rms/(rms(noise)+1e-15))

def espectro(x, fs):
    w = get_window('hann', len(x), fftbins=True)
    X = np.fft.rfft(x*w)
    f = np.fft.rfftfreq(len(x), 1/fs)
    mag = 20*np.log10(np.maximum(np.abs(X)/(np.sum(w)/2), 1e-12))
    return f, mag

def regenerar():
    from pathlib import Path
    import json
    import numpy as np
    from scipy.io import wavfile
    from scipy.signal import butter, sosfiltfilt
    import matplotlib.pyplot as plt

    FS_22, N_BLOQUE_22, L_22 = 8000, 1024, 8192
    CASOS_22 = [
        ('caso_1', 'tonal', 2150, None, 0.0, 202601),
        ('caso_2', 'blanco', None, None, 5.0, 202602),
        ('caso_3', 'banda', None, (900,1300), 3.0, 202603),
    ]
    BASE_22 = (RAIZ / 'pruebas')
    BASE_22.mkdir(parents=True, exist_ok=True)
    for nombre, tipo, interferencia, banda, snr_obj, semilla in CASOS_22:
        rng_22 = np.random.default_rng(semilla)
        tiempo = np.arange(L_22)/FS_22
        limpia = generar_limpia('multitono', tiempo, [300,700,1100], [1,.55,.30], [0,35,-50], rng_22)
        limpia = fade(limpia, FS_22, 20)
        if tipo == 'tonal':
            ruido_bruto = np.sin(2*np.pi*interferencia*tiempo + rng_22.uniform(-np.pi,np.pi))
        elif tipo == 'blanco':
            ruido_bruto = rng_22.standard_normal(L_22)
        else:
            ruido_bruto = ruido_banda(L_22, FS_22, banda, rng_22)
        ruido = escalar_ruido_para_snr(limpia, ruido_bruto, snr_obj)
        contaminada = limpia + ruido
        (limpia, ruido, contaminada), ganancia = normalizar_conjunto(limpia, ruido, contaminada, peak=0.8)
        snr_real = snr_db(limpia, contaminada)
        assert abs(snr_real-snr_obj) < 1e-8
        carpeta = BASE_22/nombre
        carpeta.mkdir(parents=True, exist_ok=True)
        for archivo, senal in [('01_referencia_limpia.wav',limpia),('02_ruido.wav',ruido),('03_entrada_contaminada.wav',contaminada)]:
            wavfile.write(carpeta/archivo, FS_22, np.int16(np.clip(senal,-1,1)*32767))
        np.savez(carpeta/'muestras_exactas.npz', limpia=limpia, ruido=ruido, contaminada=contaminada, fs=FS_22)
        config = dict(semilla=semilla, fs_Hz=FS_22, N_bloque=N_BLOQUE_22, duracion_s=L_22/FS_22,
                      frecuencias_utiles_Hz=[300,700,1100], tipo_ruido=tipo,
                      frecuencia_interferencia_Hz=interferencia, banda_ruido_Hz=banda,
                      snr_objetivo_dB=snr_obj, snr_obtenida_dB=float(snr_real))
        (carpeta/'metadatos_prueba.json').write_text(json.dumps(config,indent=2,ensure_ascii=False))
        print(nombre, 'SNR objetivo:',snr_obj,'SNR obtenida:',round(snr_real,9))

    import numpy as np
    import matplotlib.pyplot as plt
    from pathlib import Path

    # Parámetros
    FS = 8000
    BASE = (RAIZ / "pruebas")

    SALIDA = (RAIZ / "resultados/regenerados/generacion/figuras")
    SALIDA.mkdir(parents=True, exist_ok=True)


    def graficar_caso(numero):

        # Crear carpeta para las gráficas de este caso
        carpeta_figuras = SALIDA / f"caso_{numero}"

        carpeta_figuras.mkdir(
            parents=True,
            exist_ok=True
        )

        # Cargar las señales originales
        ruta = BASE / f"caso_{numero}" / "muestras_exactas.npz"

        datos = np.load(ruta)

        print("Variables disponibles:", datos.files)

        # Obtener las señales
        limpia = datos["limpia"]
        ruido = datos["ruido"]
        contaminada = datos["contaminada"]

        N = len(limpia)
        tiempo = np.arange(N) / FS


        # GRÁFICA 1: DOMINIO TEMPORAL
        plt.figure(figsize=(12, 7))

        muestras = 200

        plt.plot(
            tiempo[:muestras],
            limpia[:muestras],
            label="Señal limpia"
        )

        plt.plot(
            tiempo[:muestras],
            ruido[:muestras],
            label="Ruido",
            alpha=0.7
        )

        plt.plot(
            tiempo[:muestras],
            contaminada[:muestras],
            label="Señal contaminada",
            alpha=0.7
        )

        plt.title(f"Caso {numero}: Señales en el tiempo")
        plt.xlabel("Tiempo (s)")
        plt.ylabel("Amplitud")
        plt.legend()
        plt.grid()

        plt.tight_layout()

        plt.savefig(
        carpeta_figuras / "temporal.png",
        dpi=300
    )

        plt.close()

        # GRÁFICA 2: MAGNITUD ESPECTRAL

        frecuencias = np.fft.rfftfreq(N, 1 / FS)

        fft_limpia = np.fft.rfft(limpia)
        fft_ruido = np.fft.rfft(ruido)
        fft_contaminada = np.fft.rfft(contaminada)

        plt.figure(figsize=(12, 6))

        plt.plot(
            frecuencias,
            20 * np.log10(np.abs(fft_limpia) + 1e-12),
            label="Señal limpia"
        )

        plt.plot(
            frecuencias,
            20 * np.log10(np.abs(fft_ruido) + 1e-12),
            label="Ruido"
        )

        plt.plot(
            frecuencias,
            20 * np.log10(np.abs(fft_contaminada) + 1e-12),
            label="Señal contaminada"
        )

        plt.title(f"Caso {numero}: Magnitud espectral")
        plt.xlabel("Frecuencia (Hz)")
        plt.ylabel("Magnitud (dB)")
        plt.legend()
        plt.grid()

        plt.tight_layout()

        plt.savefig(
            carpeta_figuras / "magnitud.png",
            dpi=300
        )

        plt.close()

        # GRÁFICA 3: FASE ESPECTRAL
        umbral = 0.01 * np.max(np.abs(fft_contaminada))

        fase = np.angle(fft_contaminada)

        fase[np.abs(fft_contaminada) < umbral] = np.nan

        plt.figure(figsize=(12, 6))

        plt.plot(
            frecuencias,
            fase
        )

        plt.ylim(-np.pi, np.pi)
        # Fase sin leyenda: las curvas originales no tienen etiquetas.

        plt.title(f"Caso {numero}: Fase espectral")
        plt.xlabel("Frecuencia (Hz)")
        plt.ylabel("Fase (radianes)")
        plt.grid()

        plt.tight_layout()

        plt.savefig(
        carpeta_figuras / "fase.png",
        dpi=300
        )

        plt.close()


        # GRÁFICA 4: ENERGÍA POR BANDAS
    
        # Bandas de 500 Hz
        bandas = np.arange(0, FS / 2 + 500, 500)

        potencia = np.abs(fft_contaminada) ** 2 / N

        pesos = np.ones_like(potencia)
        pesos[1:-1] = 2

        energia_bandas = []

        for i in range(len(bandas) - 1):

            if i == len(bandas) - 2:
                mascara = (
                    (frecuencias >= bandas[i]) &
                    (frecuencias <= bandas[i + 1])
                )
            else:
                mascara = (
                    (frecuencias >= bandas[i]) &
                    (frecuencias < bandas[i + 1])
                )

            energia = np.sum(potencia[mascara] * pesos[mascara])

            energia_bandas.append(energia)

        plt.figure(figsize=(12, 6))

        plt.bar(
            bandas[:-1],
            energia_bandas,
            width=450,
            align="edge"
        )

        plt.title(f"Caso {numero}: Energía por bandas")
        plt.xlabel("Frecuencia (Hz)")
        plt.ylabel("Energía (amplitud² · muestras)")
        plt.grid(axis="y")

        plt.tight_layout()

        plt.savefig(
        carpeta_figuras / "energia.png",
        dpi=300
        )

        plt.close()



    # GENERAR GRÁFICAS PARA LOS TRES CASOS

    for caso in [1, 2, 3]:

        print(f"\nGenerando gráficas del caso {caso}")

        graficar_caso(caso)

    print("\nTodas las gráficas fueron generadas.")
    import numpy as np
    import json
    from pathlib import Path

    # Parámetros
    FS = 8000

    BASE = (RAIZ / "pruebas")

    SALIDA_RUIDO = (RAIZ / "resultados/regenerados/generacion/identificacion_ruido")

    SALIDA_RUIDO.mkdir(
        parents=True,
        exist_ok=True
    )


    def analizar_ruido(numero):

        # Cargar las señales
        ruta = BASE / f"caso_{numero}" / "muestras_exactas.npz"

        datos = np.load(ruta)

        ruido = datos["ruido"]

        N = len(ruido)

        # Calcular FFT
        frecuencias = np.fft.rfftfreq(N, 1 / FS)

        espectro = np.abs(np.fft.rfft(ruido))

        potencia = espectro**2

        # Diccionario para almacenar resultados
        resultados = {
            "caso": numero,
            "frecuencia_muestreo_Hz": FS,
            "numero_muestras": N,
            "resolucion_frecuencial_Hz": FS / N
        }

        print(f"\n========== CASO {numero} ==========")

        # CASO 1: INTERFERENCIA SINUSOIDAL
        if numero == 1:

            indice = np.argmax(espectro[1:]) + 1

            frecuencia = float(frecuencias[indice])

            resultados["tipo_ruido"] = "Interferencia sinusoidal"

            resultados["frecuencia_detectada_Hz"] = frecuencia

            resultados["frecuencia_configurada_Hz"] = 2150

            resultados["error_absoluto_Hz"] = abs(
                frecuencia - 2150
            )

            print("Tipo: Interferencia sinusoidal")

            print(
                f"Frecuencia detectada: {frecuencia:.2f} Hz"
            )

            print(
                f"Error absoluto: {resultados['error_absoluto_Hz']:.2f} Hz"
            )

        # CASO 2: RUIDO BLANCO GAUSSIANO
        elif numero == 2:

            bandas = np.arange(0, FS / 2 + 500, 500)

            energias = []

            for i in range(len(bandas) - 1):

                mascara = (
                    (frecuencias >= bandas[i]) &
                    (frecuencias < bandas[i + 1])
                )

                energia = float(
                    np.sum(potencia[mascara])
                )

                energias.append(energia)

            energias = np.array(energias)

            coeficiente_variacion = float(
                np.std(energias) / np.mean(energias)
            )

            resultados["tipo_ruido"] = "Ruido blanco gaussiano"

            resultados["energia_por_bandas"] = {}

            for i, energia in enumerate(energias):

                nombre_banda = (
                    f"{int(bandas[i])}-{int(bandas[i+1])} Hz"
                )

                resultados["energia_por_bandas"][nombre_banda] = float(
                    energia
                )

            resultados["coeficiente_variacion"] = (
                coeficiente_variacion
            )

            resultados["coeficiente_variacion_porcentaje"] = (
                coeficiente_variacion * 100
            )

            print("Tipo: Ruido blanco gaussiano")

            print("Distribución de energía por bandas:")

            for banda, energia in resultados["energia_por_bandas"].items():

                print(f"{banda}: {energia:.2f}")

            print(
                f"Coeficiente de variación: "
                f"{coeficiente_variacion:.4f}"
            )

        # CASO 3: RUIDO DE BANDA LIMITADA
        elif numero == 3:

            ventana = 101

            kernel = np.ones(ventana) / ventana

            potencia_suavizada = np.convolve(
                potencia,
                kernel,
                mode="same"
            )

            umbral = 0.1 * np.max(potencia_suavizada)

            indices = np.where(
                potencia_suavizada > umbral
            )[0]

            resultados["tipo_ruido"] = "Ruido de banda limitada"

            resultados["banda_configurada_Hz"] = [
                900,
                1300
            ]

            resultados["ventana_suavizado"] = ventana

            resultados["umbral_relativo"] = 0.1

            if len(indices) > 0:

                f_inicio = float(frecuencias[indices[0]])

                f_fin = float(frecuencias[indices[-1]])

                resultados["banda_detectada_Hz"] = [
                    f_inicio,
                    f_fin
                ]

                resultados["error_limite_inferior_Hz"] = abs(
                    f_inicio - 900
                )

                resultados["error_limite_superior_Hz"] = abs(
                    f_fin - 1300
                )

                print("Tipo: Ruido de banda limitada")

                print(
                    f"Banda detectada: "
                    f"{f_inicio:.2f} - {f_fin:.2f} Hz"
                )

            else:

                resultados["banda_detectada_Hz"] = None

                print("No se detectó una banda dominante.")

        # GUARDAR RESULTADOS

        carpeta_caso = SALIDA_RUIDO / f"caso_{numero}"

        carpeta_caso.mkdir(
            parents=True,
            exist_ok=True
        )

        archivo_json = carpeta_caso / "resultados.json"

        with open(
            archivo_json,
            "w",
            encoding="utf-8"
        ) as archivo:

            json.dump(
                resultados,
                archivo,
                indent=4,
                ensure_ascii=False
            )

        print(f"Resultados guardados en: {archivo_json}")

        return resultados


    # EJECUTAR LOS TRES CASOS

    resultados_casos = {}

    for caso in [1, 2, 3]:

        resultados_casos[caso] = analizar_ruido(caso)

    print("\nTodos los resultados fueron guardados correctamente.")
    configuraciones = {'caso_1': {'fs_Hz': 8000, 'N_bloque': 1024, 'muestras_totales': 8192, 'duracion_s': 1.024, 'semilla': 202601, 'tipo_senal': 'multitono', 'frecuencias_utiles_Hz': [300, 700, 1100], 'amplitudes_utiles': [1, 0.55, 0.3], 'fases_grados': [0, 35, -50], 'tipo_ruido': 'tonal', 'frecuencia_interferencia_Hz': 2150, 'banda_ruido_Hz': None, 'snr_objetivo_dB': 0, 'snr_obtenida_dB': -4.821637332766436e-16, 'ganancia_comun': 0.2877012618993703, 'pico_maximo': 0.8}, 'caso_2': {'fs_Hz': 8000, 'N_bloque': 1024, 'muestras_totales': 8192, 'duracion_s': 1.024, 'semilla': 202602, 'tipo_senal': 'multitono', 'frecuencias_utiles_Hz': [300, 700, 1100], 'amplitudes_utiles': [1, 0.55, 0.3], 'fases_grados': [0, 35, -50], 'tipo_ruido': 'blanco', 'frecuencia_interferencia_Hz': None, 'banda_ruido_Hz': None, 'snr_objetivo_dB': 5, 'snr_obtenida_dB': 4.999999999999999, 'ganancia_comun': 0.22620499167166933, 'pico_maximo': 0.8}, 'caso_3': {'fs_Hz': 8000, 'N_bloque': 1024, 'muestras_totales': 8192, 'duracion_s': 1.024, 'semilla': 202603, 'tipo_senal': 'multitono', 'frecuencias_utiles_Hz': [300, 700, 1100], 'amplitudes_utiles': [1, 0.55, 0.3], 'fases_grados': [0, 35, -50], 'tipo_ruido': 'banda', 'frecuencia_interferencia_Hz': None, 'banda_ruido_Hz': [900, 1300], 'snr_objetivo_dB': 3, 'snr_obtenida_dB': 3.000000000000001, 'ganancia_comun': 0.2323877641910516, 'pico_maximo': 0.8}}
    for nombre, conf in configuraciones.items():
        meta=json.loads((RAIZ / 'pruebas' / nombre / 'metadatos_prueba.json').read_text())
        conf['snr_obtenida_dB']=meta['snr_obtenida_dB']
    (RAIZ / 'metadatos').mkdir(exist_ok=True)
    (RAIZ / 'metadatos/configuraciones.json').write_text(json.dumps(configuraciones,indent=2,ensure_ascii=False)+'\n')

