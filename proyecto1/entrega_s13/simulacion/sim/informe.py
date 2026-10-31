"""Figuras del diseño y punto de entrada para regenerar las tablas y figuras."""
from pathlib import Path

import numpy as np
from scipy.signal import freqz

from sim import analogico, comparacion, costo, dft, nodo2

RAIZ = Path(__file__).resolve().parents[1]


def _dibujar():
    """Carga el backend sin interfaz solo al solicitar una figura."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _db(respuesta):
    # Piso numérico para representar ceros sin log10(0); no es un parámetro de diseño.
    return 20 * np.log10(np.maximum(np.abs(respuesta), 1e-10))


def _guardar(plt, figura, destino):
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        figura.savefig(destino, dpi=150)
    finally:
        plt.close(figura)
    return destino


def figura_polos_ceros(cfg_pruebas, cfg_n2, destino):
    """Plano z, ROC causal y estabilidad del FIR protegido y del notch de P1."""
    plt = _dibujar()
    fs = cfg_pruebas["global"]["fs_Hz"]
    p1 = cfg_pruebas["pruebas"]["P1"]
    banda = p1["banda_protegida_Hz"]
    fir = nodo2.fir_banda_protegida(banda, cfg_n2, fs)
    q = cfg_n2["notch"]["q_automatico"]
    f0 = p1["ruido"]["frecuencia_Hz"]
    b, a = nodo2.notch(f0, q, fs)
    filtros = [(f"FIR: banda {banda[0]:g}–{banda[1]:g} Hz", fir, [1.0]),
               (f"Notch: {f0:g} Hz, Q = {q:g}", b, a)]
    fig, ejes = plt.subplots(1, 2, figsize=(11, 5), constrained_layout=True)
    angulos = np.linspace(0, 2 * np.pi, 512)
    for eje, (titulo, numerador, denominador) in zip(ejes, filtros):
        polos, ceros = nodo2.polos_ceros(numerador, denominador)
        radio = nodo2.radio_roc(polos)
        eje.plot(np.cos(angulos), np.sin(angulos), color="gray", label="Círculo unitario")
        eje.plot(ceros.real, ceros.imag, "o", fillstyle="none", color="tab:blue",
                 label=f"Ceros ({len(ceros)})")
        eje.plot(polos.real, polos.imag, "x", color="tab:red", label=f"Polos ({len(polos)})")
        if radio > 0:
            eje.plot(radio * np.cos(angulos), radio * np.sin(angulos), "--",
                     color="tab:orange", label=f"|z| = {radio:.4f}")
        else:
            eje.annotate(f"{len(polos)} polos en z = 0", xy=(0, 0), xytext=(0.12, 0.22),
                         arrowprops={"arrowstyle": "->"})
        limite = max(1.2, float(np.max(np.abs(ceros))) * 1.15, radio * 1.15)
        eje.axhline(0, color="gray", linewidth=0.6)
        eje.axvline(0, color="gray", linewidth=0.6)
        eje.set_aspect("equal")
        eje.set(xlim=(-limite, limite), ylim=(-limite, limite), xlabel="Parte real",
                ylabel="Parte imaginaria", title=titulo)
        estabilidad = "estable" if nodo2.es_estable(polos) else "inestable"
        roc = "0" if radio == 0 else f"{radio:.4f}"
        eje.text(0.03, 0.03, f"ROC causal: |z| > {roc}\n{estabilidad}",
                 transform=eje.transAxes, bbox={"facecolor": "white", "alpha": 0.9})
        eje.grid(alpha=0.25)
        eje.legend(loc="upper right", fontsize=8)
    return _guardar(plt, fig, destino)


def figura_respuesta_nodo2(cfg_pruebas, cfg_n2, destino):
    """Magnitud de los FIR y notch, y comparación de fase FIR/IIR."""
    plt = _dibujar()
    fs = cfg_pruebas["global"]["fs_Hz"]
    pruebas = cfg_pruebas["pruebas"]
    f = np.linspace(0, fs / 2, 4096)
    fig, ejes = plt.subplots(3, 1, figsize=(11, 10), constrained_layout=True)
    respuesta_fir = None
    for nombre in ("P1", "P3"):
        banda = pruebas[nombre]["banda_protegida_Hz"]
        b = nodo2.fir_banda_protegida(banda, cfg_n2, fs)
        respuesta = freqz(b, [1.0], worN=f, fs=fs)[1]
        ejes[0].plot(f, _db(respuesta), label=f"FIR {banda[0]:g}–{banda[1]:g} Hz")
        if nombre == "P1":
            respuesta_fir = respuesta
    rechazo = cfg_n2["fir_banda_protegida"]["atenuacion_diseno_dB"]
    ejes[0].axhline(-rechazo, linestyle="--", color="gray", label=f"−{rechazo:g} dB de diseño")
    ejes[0].set(title="FIR de la banda protegida", ylabel="Magnitud (dB)", ylim=(-100, 5))

    p1, p5 = pruebas["P1"], pruebas["P5"]
    q = cfg_n2["notch"]["q_automatico"]
    f0 = p1["ruido"]["frecuencia_Hz"]
    b, a = nodo2.notch(f0, q, fs)
    respuesta_notch = freqz(b, a, worN=f, fs=fs)[1]
    ejes[1].plot(f, _db(respuesta_notch), label=f"P1: {f0:g} Hz, Q = {q:g}")
    for q_p5 in dict.fromkeys(nivel["q_notch"] for nivel in p5["barrido"]):
        b, a = nodo2.notch(p5["frecuencia_notch_Hz"], q_p5, fs)
        ejes[1].plot(f, _db(freqz(b, a, worN=f, fs=fs)[1]),
                     label=f"P5: {p5['frecuencia_notch_Hz']:g} Hz, Q = {q_p5:g}")
    for tono in p5["senal"]["frecuencias_Hz"]:
        ejes[1].axvline(tono, linestyle=":", color="gray", alpha=0.6)
    ejes[1].set(title="Notch de P1 y barrido de P5; líneas punteadas: tonos útiles",
                ylabel="Magnitud (dB)", ylim=(-60, 5))
    ejes[2].plot(f, np.rad2deg(np.unwrap(np.angle(respuesta_fir))), label="FIR de P1")
    ejes[2].plot(f, np.rad2deg(np.unwrap(np.angle(respuesta_notch))), label="Notch de P1")
    ejes[2].set(title="Fase de los filtros", ylabel="Fase (grados)")
    for eje in ejes:
        eje.set(xlabel="Frecuencia (Hz)", xlim=(0, fs / 2))
        eje.grid(alpha=0.25)
        eje.legend(fontsize=9)
    return _guardar(plt, fig, destino)


def figura_cadena_analogica(cfg_analogica, destino):
    """Respuestas de entrada, decimación y reconstrucción de la salida."""
    plt = _dibujar()
    fs_adc = cfg_analogica["tasas"]["fs_adc_Hz"]
    fs = cfg_analogica["tasas"]["fs_Hz"]
    fc, q = analogico.sallen_key_parametros(cfg_analogica)
    fig, ejes = plt.subplots(3, 1, figsize=(11, 10), constrained_layout=True)
    f = np.geomspace(10, fs_adc, 4096)
    ejes[0].semilogx(f, _db(analogico.respuesta_sallen_key(cfg_analogica, f)),
                     label=f"Sallen-Key: fc = {fc:.1f} Hz, Q = {q:.3f}")
    ejes[0].axvline(fc, color="tab:orange", linestyle="--", label="Frecuencia natural fc")
    # Marcas de lectura del gráfico, no parámetros del filtro.
    for marca in (3000, 21000):
        ejes[0].axvline(marca, color="gray", linestyle=":", label=f"Referencia {marca:g} Hz")
    ejes[0].set(title="Filtro analógico de entrada", xlim=(10, fs_adc))

    f = np.linspace(0, fs_adc / 2, 4096)
    ejes[1].plot(f, _db(analogico.respuesta_decimacion(cfg_analogica, f)), label="FIR de decimación")
    for marca in (3000, 5000):
        ejes[1].axvline(marca, color="gray", linestyle=":", label=f"Referencia {marca:g} Hz")
    # Se identifica el parámetro Kaiser real, sin inventar un criterio de rechazo.
    atenuacion = cfg_analogica["decimacion"]["atenuacion_beta_dB"]
    ejes[1].axhline(-atenuacion, color="tab:orange", linestyle="--",
                    label=f"Parámetro Kaiser: {atenuacion:g} dB")
    ejes[1].set(title="FIR previo a la decimación", xlim=(0, fs_adc / 2), ylim=(-100, 5))

    f = np.linspace(0, fs / 2, 4096)
    retencion = analogico.respuesta_zoh(cfg_analogica, f)
    filtro = analogico.respuesta_sallen_key(cfg_analogica, f)
    ejes[2].plot(f, _db(retencion), label="Retención de orden cero")
    ejes[2].plot(f, _db(filtro), label="Sallen-Key")
    ejes[2].plot(f, _db(retencion * filtro), label="Producto: salida completa")
    ejes[2].set(title="Reconstrucción de salida de los nodos 2 y 3", xlim=(0, fs / 2))
    for eje in ejes:
        eje.set(xlabel="Frecuencia (Hz)", ylabel="Magnitud (dB)")
        eje.grid(alpha=0.25)
        eje.legend(fontsize=9)
    return _guardar(plt, fig, destino)


def figura_dft_fft(config, destino):
    """Espectros superpuestos y diferencia absoluta de ambas transformadas."""
    plt = _dibujar()
    x = dft.senal_p1(config)
    fs = config["global"]["fs_Hz"]
    directo, rapido = dft.dft_directa(x), np.fft.fft(x)
    # Señal real: basta mostrar la mitad no negativa, incluida Nyquist.
    bins = x.size // 2 + 1
    f = np.fft.rfftfreq(x.size, 1 / fs)
    fig, ejes = plt.subplots(2, 1, figsize=(11, 7), constrained_layout=True)
    ejes[0].plot(f, _db(directo[:bins]), label="DFT directa", linewidth=2)
    ejes[0].plot(f, _db(rapido[:bins]), "--", label="FFT NumPy")
    ejes[0].set(title="P1: magnitud de la DFT y la FFT", ylabel="Magnitud (dB)")
    # El piso solo permite dibujar diferencias exactamente nulas en escala logarítmica.
    diferencia = np.maximum(np.abs(directo[:bins] - rapido[:bins]), np.finfo(float).tiny)
    ejes[1].semilogy(f, diferencia, label="|DFT − FFT|")
    error_rel = np.max(np.abs(directo - rapido)) / np.max(np.abs(rapido))
    ejes[1].set(title=f"Diferencia absoluta; error máximo relativo = {error_rel:.3e}",
                ylabel="Error absoluto")
    for eje in ejes:
        eje.set(xlabel="Frecuencia (Hz)", xlim=(0, fs / 2))
        eje.grid(alpha=0.25)
        eje.legend()
    return _guardar(plt, fig, destino)


def generar_todo(salida=None):
    """Regenera las tablas y nueve figuras a partir de una carga de configuración."""
    salida = RAIZ / "resultados" if salida is None else Path(salida)
    configs = comparacion.cargar_configuraciones()
    comparacion.generar_comparacion(configs, salida)
    dft.generar_dft(configs["pruebas"], salida)
    costo.generar_costo(configs["pruebas"], configs["nodo2"], configs["analogica"],
                        configs["nodo3"], salida)
    figuras = salida / "figuras"
    nuevas = [
        figura_polos_ceros(configs["pruebas"], configs["nodo2"], figuras / "nodo2_polos_ceros.png"),
        figura_respuesta_nodo2(configs["pruebas"], configs["nodo2"], figuras / "nodo2_respuesta.png"),
        figura_cadena_analogica(configs["analogica"], figuras / "cadena_analogica.png"),
        figura_dft_fft(configs["pruebas"], figuras / "dft_fft.png"),
    ]
    archivos = [salida / nombre for nombre in
                ("comparacion.csv", "comparacion_resumen.csv", "dft_fft.json", "costo.csv")]
    archivos += [figuras / f"{prueba}.png" for prueba in configs["pruebas"]["pruebas"]]
    archivos += nuevas
    print("\nArchivos generados:")
    for archivo in archivos:
        print(f"  {archivo}")
    return archivos


if __name__ == "__main__":
    generar_todo()
