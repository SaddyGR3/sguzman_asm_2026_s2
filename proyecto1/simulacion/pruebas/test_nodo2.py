import numpy as np
import pytest
from scipy.signal import firwin, freqz, iirnotch, kaiser_beta, lfilter
from scipy.signal.windows import kaiser

from sim import analogico, nodo2, senales

CFG_N2 = nodo2.cargar_config_nodo2()
CONFIG = senales.cargar_config()
CFG_ANALOGICA = analogico.cargar_config_analogica()
FS = CONFIG["global"]["fs_Hz"]
H = CONFIG["global"]["H"]
FIR = CFG_N2["fir_banda_protegida"]
TRANSICION = FIR["transicion_Hz"]
Q_AUTOMATICO = CFG_N2["notch"]["q_automatico"]
P5 = CONFIG["pruebas"]["P5"]
F0_P5 = P5["frecuencia_notch_Hz"]
Q_BARRIDO = sorted({nivel["q_notch"] for nivel in P5["barrido"]})

# Valores de la Tarea 1 para la banda (100, 1200): k = 0…18; el resto es simétrico.
TAREA1_MITAD = [
    1.1281118305568869e-03, 2.3012855797120866e-03, -2.6611140796740475e-18,
    -4.6418238294469606e-03, -4.7669952206183322e-03, 3.3770127372078889e-03,
    1.1336913791783341e-02, 5.4957536078769128e-03, -1.2734199171669404e-02,
    -2.0730780518584790e-02, 1.0245579273282646e-17, 3.2081736006478692e-02,
    3.0810901887059709e-02, -2.1259777528944767e-02, -7.2924291746006925e-02,
    -3.8636615819073801e-02, 1.0998222858046637e-01, 2.9201113153602493e-01,
    3.7433881655435630e-01,
]


def _db(razon):
    return 20 * np.log10(razon)


def _amplitud(senal, f_Hz, t0, t1):
    """Amplitud del tono de f_Hz entre t0 y t1 (s): mínimos cuadrados de [cos, sin, 1]."""
    i0, i1 = round(t0 * FS), round(t1 * FS)
    t = np.arange(i0, i1) / FS
    base = np.column_stack((np.cos(2 * np.pi * f_Hz * t), np.sin(2 * np.pi * f_Hz * t),
                            np.ones_like(t)))
    coef = np.linalg.lstsq(base, senal[i0:i1], rcond=None)[0]
    return float(np.hypot(coef[0], coef[1]))


def _respuesta(b, a, f_Hz):
    """Magnitud de la respuesta en las frecuencias f_Hz."""
    return np.abs(freqz(b, a, worN=np.atleast_1d(f_Hz), fs=FS)[1])


def _fir(banda):
    return nodo2.fir_banda_protegida(banda, CFG_N2, FS)


def _referencia_firwin(cortes, pasa_banda):
    ventana = ("kaiser", kaiser_beta(FIR["atenuacion_diseno_dB"]))
    return firwin(FIR["coeficientes"], cortes, window=ventana, pass_zero=not pasa_banda, fs=FS)


# --- Ventana de Kaiser ---

@pytest.mark.parametrize("x", [0, 0.5, 1, 3.975, 5, 10])
def test_bessel_i0(x):
    assert abs(nodo2.bessel_i0(x) - np.i0(x)) <= 1e-12 * np.i0(x)


@pytest.mark.parametrize("atenuacion", [10, 21, 45, 50, 60])
def test_beta_kaiser(atenuacion):
    assert abs(nodo2.beta_kaiser(atenuacion) - kaiser_beta(atenuacion)) <= 1e-12


def test_ventana_kaiser():
    beta = kaiser_beta(FIR["atenuacion_diseno_dB"])
    diferencia = nodo2.ventana_kaiser(FIR["coeficientes"], beta) - kaiser(FIR["coeficientes"], beta)
    assert np.max(np.abs(diferencia)) <= 1e-12


# --- FIR de la banda protegida ---

@pytest.mark.parametrize("prueba", ["P1", "P2", "P4", "P5"])
def test_fir_igual_a_tarea1(prueba):
    banda = CONFIG["pruebas"][prueba]["banda_protegida_Hz"]
    esperado = np.array(TAREA1_MITAD + TAREA1_MITAD[-2::-1])
    assert not nodo2.es_pasa_banda(banda, CFG_N2)
    assert np.max(np.abs(_fir(banda) - esperado)) <= 1e-6


@pytest.mark.parametrize("banda", [(100, 1200), (100, 3000)])
def test_fir_pasa_bajas_contra_firwin(banda):
    esperado = _referencia_firwin(banda[1] + TRANSICION / 2, pasa_banda=False)
    assert np.max(np.abs(_fir(banda) - esperado)) <= 1e-6


@pytest.mark.parametrize("banda", [(800, 2000), (1000, 3000)])
def test_fir_pasa_banda_contra_firwin(banda):
    esperado = _referencia_firwin([banda[0] - TRANSICION / 2, banda[1] + TRANSICION / 2],
                                  pasa_banda=True)
    assert np.max(np.abs(_fir(banda) - esperado)) <= 1e-6


@pytest.mark.parametrize("banda", [(100, 1200), (100, 3000), (800, 2000), (1000, 3000)])
def test_fir_simetria_y_retardo(banda):
    h = _fir(banda)
    assert len(h) == FIR["coeficientes"]
    assert np.max(np.abs(h - h[::-1])) <= 1e-15
    # Fase lineal con retardo de 18 muestras: H(w)·e^{jw·18} es real.
    w = np.linspace(0, np.pi, 200)
    respuesta = freqz(h, worN=w)[1]
    assert np.max(np.abs(np.imag(respuesta * np.exp(1j * w * 18)))) <= 1e-12


@pytest.mark.parametrize("banda", [(100, 1200), (100, 3000)])
def test_fir_pasa_bajas_rechazo(banda):
    f = np.linspace(0, FS / 2, 4096)
    magnitud = _respuesta(_fir(banda), [1.0], f)
    assert abs(_db(magnitud[0])) <= 1e-9
    assert -np.max(_db(magnitud[f >= banda[1] + TRANSICION])) >= 45


@pytest.mark.parametrize("banda", [(800, 2000), (1000, 3000)])
def test_fir_pasa_banda_rechazo(banda):
    lo, hi = banda
    h = _fir(banda)
    f = np.linspace(0, FS / 2, 4096)
    magnitud = _db(_respuesta(h, [1.0], f))
    assert -np.max(magnitud[f <= lo - TRANSICION]) >= 40
    assert -np.max(magnitud[f >= hi + TRANSICION]) >= 40
    assert abs(_respuesta(h, [1.0], (lo + hi) / 2)[0] - 1) <= 1e-9


def test_limite_pasa_bajas_pasa_banda():
    borde = FIR["borde_inferior_min_pasa_banda_Hz"]
    assert not nodo2.es_pasa_banda((borde - 0.1, 2000), CFG_N2)
    assert nodo2.es_pasa_banda((borde, 2000), CFG_N2)


@pytest.mark.parametrize("banda", [(1200, 100), (0, 1200), (100, 3800)])
def test_fir_validacion(banda):
    with pytest.raises(ValueError):
        _fir(banda)


def test_fir_polos_ceros_roc():
    polos, ceros = nodo2.polos_ceros(_fir((100, 1200)), [1.0])
    assert len(polos) == len(ceros) == 36
    assert np.all(polos == 0)
    assert nodo2.radio_roc(polos) == 0
    assert nodo2.es_estable(polos)


# --- Notch IIR ---

@pytest.mark.parametrize("f0, q", [(F0_P5, 10), (F0_P5, 2.75), (F0_P5, 1), (2150, Q_AUTOMATICO)])
def test_notch_contra_iirnotch(f0, q):
    b, a = nodo2.notch(f0, q, FS)
    b_ref, a_ref = iirnotch(f0, q, fs=FS)
    assert np.max(np.abs(b - b_ref)) <= 1e-12
    assert np.max(np.abs(a - a_ref)) <= 1e-12


@pytest.mark.parametrize("q", Q_BARRIDO)
def test_notch_polos_ceros_ganancias(q):
    b, a = nodo2.notch(F0_P5, q, FS)
    polos, ceros = nodo2.polos_ceros(b, a)
    w0 = 2 * np.pi * F0_P5 / FS
    radio = np.sqrt(2 / (1 + np.tan(w0 / q / 2)) - 1)       # √(2g − 1)
    assert np.max(np.abs(np.abs(ceros) - 1)) <= 1e-12
    assert np.max(np.abs(np.abs(np.angle(ceros)) - w0)) <= 1e-9
    assert np.all(np.abs(polos) < 1) and nodo2.es_estable(polos)
    assert abs(nodo2.radio_roc(polos) - radio) <= 1e-12
    assert np.max(np.abs(np.abs(polos) - radio)) <= 1e-12
    assert _respuesta(b, a, F0_P5)[0] <= 1e-4
    assert abs(_db(_respuesta(b, a, 0.0)[0])) <= 1e-9
    assert abs(_db(_respuesta(b, a, FS / 2)[0])) <= 1e-9


def test_compromiso_p5():
    ganancias_700 = []
    for q in Q_BARRIDO:
        b, a = nodo2.notch(F0_P5, q, FS)
        ganancias_700.append(_respuesta(b, a, 700.0)[0])
        assert _respuesta(b, a, F0_P5)[0] <= 1e-4
    # Q_BARRIDO está en orden creciente: a menor Q, mayor pérdida en 700 Hz.
    assert np.all(np.diff(ganancias_700) > 0)


def test_q_automatico():
    error_max = FS / CONFIG["global"]["N"] / 2          # medio bin de la FFT del nodo 1
    for error in (-error_max, error_max):
        b, a = nodo2.notch(2150 + error, Q_AUTOMATICO, FS)
        assert _db(_respuesta(b, a, 2150.0)[0]) <= -30
        assert _db(_respuesta(b, a, 700.0)[0]) >= -0.1


@pytest.mark.parametrize("f0, q", [(0, 2.75), (FS / 2, 2.75), (F0_P5, 0)])
def test_notch_validacion(f0, q):
    with pytest.raises(ValueError):
        nodo2.notch(f0, q, FS)


# --- Bloques con estado ---

@pytest.mark.parametrize("filtro", ["fir", "notch"])
def test_bloques_igual_a_senal_entera(filtro):
    x = np.random.default_rng(0).standard_normal(80000)
    if filtro == "fir":
        b, a = _fir(CONFIG["pruebas"]["P1"]["banda_protegida_Hz"]), np.array([1.0])
    else:
        b, a = nodo2.notch(F0_P5, 2.75, FS)
    entera = lfilter(b, a, x)
    bloques = nodo2.filtrar_por_bloques(b, a, x, H)
    if filtro == "fir":
        # Con a = [1], scipy calcula el FIR por convolución, y cortar en bloques cambia el orden
        # de la suma (redondeo de ~1e-16).
        assert np.max(np.abs(bloques - entera)) <= 1e-12
    else:
        assert np.array_equal(bloques, entera)


def test_largo_con_ultimo_bloque_corto():
    b, a = nodo2.notch(F0_P5, 2.75, FS)
    x = np.random.default_rng(0).standard_normal(1000)
    assert len(nodo2.filtrar_por_bloques(b, a, x, H)) == 1000


# --- Señales del banco pasadas por la cadena del paso 2 ---

def _entrada(prueba, semilla):
    caso = senales.generar_caso(CONFIG, prueba, semilla)
    salida = analogico.entrada_nodo1(caso["x"], caso["s"], CFG_ANALOGICA)
    return salida["x"], salida["s"]


def test_p1_notch():
    cfg = CONFIG["pruebas"]["P1"]
    x8, s8 = _entrada("P1", cfg["semillas"][0])
    f_interferencia = cfg["ruido"]["frecuencia_Hz"]
    b, a = nodo2.disenar_filtro_nodo2(cfg, CFG_N2, FS, f0_Hz=f_interferencia)
    y = nodo2.filtrar_por_bloques(b, a, x8, H)
    atenuacion = _db(_amplitud(y, f_interferencia, 2, 9) / _amplitud(x8, f_interferencia, 2, 9))
    f_senal = cfg["senal"]["frecuencia_Hz"]
    diferencia = _db(_amplitud(y, f_senal, 2, 9) / _amplitud(s8, f_senal, 2, 9))
    assert atenuacion <= -30
    assert abs(diferencia) <= 0.1


def test_p2_fir():
    cfg = CONFIG["pruebas"]["P2"]
    x8, s8 = _entrada("P2", cfg["semillas"][0])
    b, a = nodo2.disenar_filtro_nodo2(cfg, CFG_N2, FS)
    y = nodo2.filtrar_por_bloques(b, a, x8, H)

    def energia_banda(senal):
        tramo = senal[round(2 * FS):round(9 * FS)]
        f = np.fft.rfftfreq(len(tramo), 1 / FS)
        lo, hi = cfg["banda_atenuacion_Hz"]
        return np.sum(np.abs(np.fft.rfft(tramo))[(f >= lo) & (f <= hi)] ** 2)

    assert 10 * np.log10(energia_banda(x8) / energia_banda(y)) >= 40
    for f_tono in cfg["senal"]["frecuencias_Hz"]:
        assert abs(_db(_amplitud(y, f_tono, 2, 9) / _amplitud(s8, f_tono, 2, 9))) <= 0.1
