"""Referencias numéricas de subbloques, OLA y alineamiento. No ejecutan C++."""
import unittest
import numpy as np

BLOQUE=512


def reconstruir(x,n):
    h=n//2
    ventana=np.sqrt(.5-.5*np.cos(2*np.pi*np.arange(n)/n))
    previo=np.zeros(h);solape=np.zeros(h);salida=[]
    extendida=np.r_[x,np.zeros(BLOQUE)]
    for paquete in extendida.reshape(-1,BLOQUE):
        for off in range(0,BLOQUE,h):
            actual=paquete[off:off+h]
            frame=np.r_[previo,actual]
            transformada=np.fft.rfft(frame*ventana)
            sintetizada=np.fft.irfft(transformada,n)*ventana
            salida.extend(solape+sintetizada[:h])
            solape=sintetizada[h:];previo=actual.copy()
    return np.array(salida)


class TamanoConfigurable(unittest.TestCase):
    def test_ola_identidad_y_retardo_todos_n(self):
        rng=np.random.default_rng(32)
        x=rng.normal(size=4*BLOQUE);x[0]=5;x[-1]=-6
        for n in (1024,512,256,1024):
            h=n//2
            y=reconstruir(x,n)
            esperado=np.r_[np.zeros(h),x,np.zeros(BLOQUE-h)]
            np.testing.assert_allclose(y,esperado,atol=2e-14)

    def test_metricas_alineadas_incluyen_bordes_y_energia(self):
        rng=np.random.default_rng(33)
        x=rng.normal(size=3*BLOQUE);x[0]=8;x[-1]=-7
        for n in (256,512,1024):
            h=n//2
            fir=np.r_[np.zeros(18),.5*x,np.zeros(BLOQUE-18)]
            notch=np.r_[.8*x,np.zeros(BLOQUE)]
            espec=np.r_[np.zeros(h),.25*x,np.zeros(BLOQUE-h)]
            aligned=[[],[],[],[]]
            for off in range(0,len(x),BLOQUE):
                # Métricas se cierran al llegar el paquete posterior, incluso
                # cuando solo se necesita una fracción de ese paquete (N menor).
                anterior=slice(off,off+BLOQUE);actual=slice(off+BLOQUE,off+2*BLOQUE)
                arrays=[np.r_[x,np.zeros(BLOQUE)],fir,notch,espec]
                for pos in range(BLOQUE):
                    for modo,delay in enumerate((0,18,0,h)):
                        j=pos+delay
                        bloque=arrays[modo][anterior] if j<BLOQUE else arrays[modo][actual]
                        aligned[modo].append(bloque[j%BLOQUE])
            for a,g in zip(aligned,(1,.5,.8,.25)):
                np.testing.assert_allclose(a,g*x,atol=1e-14)
            v=np.sqrt(.5-.5*np.cos(2*np.pi*np.arange(n)/n))
            def energia(a):
                a=np.r_[np.zeros(h),a,np.zeros(h)];total=0
                for pos in range(0,len(x)+1,h):
                    f=np.fft.rfft(a[pos:pos+n]*v)
                    total+=(abs(f[0])**2+abs(f[-1])**2+2*np.sum(abs(f[1:-1])**2))/n
                return total
            ex=energia(aligned[0])
            for a,g in zip(aligned,(1,.5,.8,.25)):
                self.assertAlmostEqual(energia(a)/ex,g*g,places=12)
                self.assertAlmostEqual(np.mean((np.asarray(a)-x)**2),(g-1)**2*np.mean(x*x),places=12)

    def test_ventanas_diagnostico_en_lotes_512(self):
        x=np.arange(4*BLOQUE,dtype=float)
        for n in (256,512,1024):
            h=n//2;hist=np.zeros(1024)
            for inicio in range(0,len(x),BLOQUE):
                hist=np.r_[hist[BLOQUE:],x[inicio:inicio+BLOQUE]]
                for off in range(0,BLOQUE,h):
                    pos=BLOQUE+off+h-n
                    frame=hist[pos:pos+n]
                    fin=inicio+off+h
                    esperado=np.r_[np.zeros(max(n-fin,0)),x[max(0,fin-n):fin]]
                    np.testing.assert_array_equal(frame,esperado)


if __name__=='__main__':
    unittest.main()
