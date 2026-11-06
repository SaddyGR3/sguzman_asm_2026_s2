"""Referencia temporal independiente; no compila ni ejecuta el C++ ni WAV."""
import numpy as np

H = 512
rng = np.random.default_rng(20261106)

def caracteristicas(x):
    corto = np.sqrt(np.mean(x.reshape(16, 32)**2, axis=1))
    pico = np.max(np.abs(x))
    rms = np.sqrt(np.mean(x*x))
    return corto, pico, rms

def referencia(bloques):
    medidas = [caracteristicas(b) for b in bloques]
    # Rango superior más cercano: índice 30 de las 32 observaciones.
    q = lambda x: np.sort(x)[30]
    return (np.sqrt(np.mean([r*r for c,p,r in medidas])),
            q([np.max(c) for c,p,r in medidas]), q([p for c,p,r in medidas]))

def candidato(x, fondo, pl02):
    if not np.all(np.isfinite(x)) or np.max(np.abs(x)) >= .999:
        return False
    c, p, rms = caracteristicas(x)
    if rms <= .0001:
        return False
    r, qc, qp = fondo
    base = max(np.median(c), r, .0001)
    cresta = p / rms
    n = np.count_nonzero(c > (2 if cresta > 6 else 3) * base)
    anterior = 1 <= n <= 4 and cresta > 3 and p > 3*max(r, .0001)
    return bool(anterior and (not pl02 or (c.max() > 1.5*qc and p > 1.5*qp)))

def fondo_con_transitorios(n):
    x = rng.normal(0, .0025, (n,H))
    for j in range(n):
        if j % 4 != 0:
            k = rng.integers(0,H-32)
            x[j,k:k+32] += rng.uniform(.045,.05)*np.hanning(32)
    return x

def evaluar(nombre, bloques, fondo):
    viejo = np.array([candidato(x,fondo,False) for x in bloques])
    nuevo = np.array([candidato(x,fondo,True) for x in bloques])
    assert np.all(~nuevo | viejo), 'PL02 solo puede retirar candidatos'
    confirm = lambda a: np.count_nonzero(np.convolve(a.astype(int),[1,1,1],mode='full')[:len(a)]>=2)
    print(f'{nombre}: candidatos antes {viejo.sum()}, PL02 {nuevo.sum()}; confirmaciones 2/3 antes {confirm(viejo)}, PL02 {confirm(nuevo)} / {len(bloques)}')
    return nuevo,confirm(nuevo)

cal = fondo_con_transitorios(32)
fondo = referencia(cal)
print('Fondo RMS, corto P95, pico P95:', fondo)
x=fondo_con_transitorios(256)
res,conf=evaluar('Fondo con transitorios habituales',x,fondo)
assert not res.any() and conf==0
z=x.copy()
for j in range(len(z)):
    z[j,180:192] += .3*np.hanning(12)
res,conf=evaluar('Impulsos añadidos por encima del fondo',z,fondo)
assert res.sum()>=.9*len(z) and conf>=.9*len(z)

t=np.arange(256*H)/8000
util=.2*np.sin(2*np.pi*700*t)*((t%1)<.2)
z=rng.normal(0,.0025,(256,H))+util.reshape(256,H)
res,conf=evaluar('Ráfagas útiles de 200 ms',z,fondo)
assert conf==0
for valor in (np.nan,np.inf,1.,-1.):
    x=np.zeros(H); x[20]=valor
    assert not candidato(x,fondo,True)
assert not candidato(np.zeros(H),(0.,0.,0.),True)
assert referencia(np.zeros((32,H)))==(0.,0.,0.)
print('OK: inválidos, recorte, silencio digital y PL02 nunca agrega candidatos.')
