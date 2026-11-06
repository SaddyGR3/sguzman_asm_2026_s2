"""Referencia numérica independiente del alineamiento; no ejecuta el C++."""
import unittest
import numpy as np

H,N=512,1024


class Alineamiento(unittest.TestCase):
    def test_retardos_y_extremos_con_vaciado(self):
        rng=np.random.default_rng(8)
        x=rng.normal(size=H*3)
        x[0],x[-1]=8,-7
        for retardo in (0,18,512):
            # Una identidad retrasada debe coincidir exactamente tras alinear,
            # incluyendo las últimas muestras que están en el bloque de vaciado.
            y=np.r_[np.zeros(retardo),x,np.zeros(H-retardo)]
            recuperada=np.concatenate([y[n+retardo:n+retardo+H] for n in range(0,len(x),H)])
            np.testing.assert_array_equal(recuperada,x)
            self.assertEqual(np.mean((recuperada-x)**2),0)

    def test_energia_ventanas_inicial_final(self):
        rng=np.random.default_rng(9)
        x=rng.normal(size=H*3)
        ventana=np.sqrt(.5-.5*np.cos(2*np.pi*np.arange(N)/N))
        extendida=np.r_[np.zeros(H),x,np.zeros(H)]
        energia=0
        for n in range(0,len(x)+1,H):
            f=np.fft.rfft(extendida[n:n+N]*ventana)
            energia+=(abs(f[0])**2+abs(f[-1])**2+2*np.sum(abs(f[1:-1])**2))/N
        self.assertAlmostEqual(energia,np.sum(x*x),places=9)

    def test_na_proteccion_completa_y_sin_filtro(self):
        rng=np.random.default_rng(10)
        x=rng.normal(size=N)
        y=x.copy()
        f=np.fft.rfftfreq(N,1/8000)
        p=abs(np.fft.rfft(x))**2
        analisis=(f>=100)&(f<=3000)
        fuera=analisis&~((f>=100)&(f<=3000))
        self.assertEqual(p[fuera].sum(),0)  # SNR no tiene denominador válido
        self.assertEqual(np.mean((x-y)**2),0)
        self.assertEqual(100*p[analisis].sum()/p[analisis].sum(),100)


if __name__=='__main__':
    unittest.main()
