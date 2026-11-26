"""Pantalla de terminal POSIX sobre el mismo Banco que utiliza el panel.

No abre un servidor HTTP ni un navegador. El hilo de Banco recibe y guarda datos.
La pantalla usa ANSI, entrada local sin eco y comandos completos con Enter.
"""
import math
import os
import queue
import select
import shutil
import sys
import time

NOMBRES_CURVA = {'lineal': 'Lineal', 'exponencial': 'Exponencial', 'coseno': 'Coseno'}
AYUDA = (
    'auto_fijo30 · auto_preparar · auto_pid · libre · tiempo6000 · cancelar',
    'sensor_on · sensor_off · motor_on · motor_off · g90 · estado · v',
    'ayuda · salir   |   Salir o Ctrl+C NO cancela el ensayo físico',
)


def texto_seguro(texto):
    """Evita que mensajes del dispositivo inyecten controles de terminal."""
    return ''.join(c if c.isprintable() else ' ' for c in str(texto))


def numero(valor, decimales=0):
    if valor is None or not isinstance(valor, (int, float)) or not math.isfinite(valor):
        return '—'
    return f'{valor:.{decimales}f}'


def dividir(valor, divisor):
    return valor/divisor if isinstance(valor, (int, float)) else None


def minigrafica(valores, ancho=40):
    """Una columna por muestra o grupo. Los huecos invalidos no se vuelven cero."""
    if not valores:
        return '·'*ancho, 'sin datos'
    # Se conservan puntos repartidos por la ventana, sin ampliar el historial.
    if len(valores) > ancho:
        valores = [valores[round(i*(len(valores)-1)/(ancho-1))] for i in range(ancho)]
    validos = [v for v in valores if isinstance(v, (int, float)) and math.isfinite(v)]
    if not validos:
        return '·'*len(valores), 'sin datos válidos'
    minimo, maximo = min(validos), max(validos)
    escala = '▁▂▃▄▅▆▇█'
    puntos = []
    for v in valores:
        if v is None or not math.isfinite(v):
            puntos.append('·')
        else:
            nivel = round(7*(v-minimo)/(maximo-minimo)) if maximo != minimo else 3
            puntos.append(escala[max(0, min(7, nivel))])
    return ''.join(puntos), numero(minimo, 1)+' a '+numero(maximo, 1)


def renderizar(estado, entrada='', aviso='', columnas=110, filas=34):
    """Construye una vista sin escribir a la terminal. Datos y eventos siguen vivos."""
    ancho = max(10, columnas)
    d = estado.get('ultimo', {})
    simulado = estado.get('fuente') == 'SIMULACION'
    fuente = 'SIMULACIÓN · PLANTA FICTICIA' if simulado else estado.get('fuente', 'SIN CONEXIÓN')
    activo = 'CONECTADO' if estado.get('activo') else 'DESCONECTADO'
    edad = estado.get('edad_diag_s')
    calidad = 'esperando diagnóstico' if edad is None else 'diagnóstico hace '+numero(edad, 1)+' s'
    if estado.get('activo') and (edad is None or edad > 1):
        calidad += ' · SIN DATOS RECIENTES'
    entrada_visible = entrada[-max(1, ancho-5):]
    lineas = [
        ' BANCO DE FRENADO  /  CE1110  /  TERMINAL',
        f' {fuente}  ·  {activo}  ·  {d.get("modo", "—")}  ·  {calidad}',
        ' Figura activa · '+NOMBRES_CURVA.get(estado.get('curva'), '—'),
        '─'*ancho,
        ' RPM '+numero(d.get('rpm_mostrada',d.get('rpm_validada')))+(' (cero estimado)' if d.get('cero_estimado') else '')+'   Referencia '+numero(d.get('referencia_rpm'))+
        '   Error '+numero(d.get('error_rpm'))+' RPM',
        ' Servo '+numero(d.get('angulo'))+'°   Acción al servo '+numero(d.get('u_aplicada'), 3)+
        '   Ensayo '+numero(dividir(d.get('tiempo_ensayo_ms'), 1000), 1)+' s',
        ' Medición '+str(d.get('estado_medicion', '—'))+'   Motor ordenado '+
        ('—' if d.get('motor_encendido') is None else 'ENCENDIDO' if d['motor_encendido'] else 'APAGADO'),
        ' PID '+str(d.get('pid_estado', '—'))+'   P '+numero(d.get('pid_p'), 3)+
        '   I '+numero(d.get('pid_i'), 3)+'   D '+numero(d.get('pid_d'), 3),
        ' Acción solicitada '+numero(d.get('u_solicitada'), 3)+'   Limitada '+numero(d.get('pid_u_limitada'), 3),
        ' Pulsos '+numero(d.get('pulsos_aceptados'))+'   Cortos '+numero(d.get('pulsos_rechazados'))+
        '   Saltos '+numero(d.get('saltos_rechazados'))+'   Cola perdida '+numero(d.get('perdidos_cola')),
        ' RPM cruda '+numero(d.get('rpm_cruda'))+'   Edad '+numero(dividir(d.get('antiguedad_us'), 1000), 1)+
        ' ms   Periodo rechazado '+numero(d.get('ultimo_periodo_rechazado_us'))+' µs',
        ' dt PID '+numero(dividir(d.get('pid_dt_us'), 1000), 1)+' ms   Omitidos '+numero(d.get('pid_omitidos'))+
        '   Cálculo '+('no medido en ESP32' if simulado else numero(d.get('pid_tiempo_calculo_us'))+' µs'),
    ]
    historia = estado.get('historia', [])[-120:]
    sensor=estado.get('sensor', {})
    if sensor.get('activo') or sensor.get('cambios'):
        lineas.append(' GPIO34 · '+('DIAGNÓSTICO ACTIVO' if sensor.get('activo') else 'DIAGNÓSTICO FINALIZADO')+
                      ' · nivel '+numero(sensor.get('nivel'))+' · perdidos '+str(sensor.get('perdidos',0)))
        lineas.append('      ISR     Tiempo µs       Desde anterior µs   Nivel   Aceptados   Cortos')
        for c in sensor.get('cambios', [])[-4:]:
            lineas.append(f"   {c['numero']:6d}   {c['tiempo_us']:12d}   {c['intervalo_us']:17d}   {c['nivel']:5d}   {c['aceptados']:9d}   {c['cortos']:6d}")
        lineas.append(' Cada fila es una llamada a la ISR de cambios. CSV completo en sensor_1.csv.')
        if sensor.get('perdidos'): lineas.append(' CAPTURA INCOMPLETA · hubo llamadas que no cupieron en la cola.')
    else:
        for etiqueta, clave in [('RPM', 'rpm_mostrada'), ('Referencia', 'referencia_rpm'), ('Freno PID', 'u_aplicada')]:
            grafica, rango = minigrafica([f.get(clave) for f in historia], max(8, min(55, ancho-43)))
            lineas.append(f' {etiqueta:<11} {grafica}  {rango}')
        lineas.append(' Minigráficas · últimas 120 muestras · escala propia por señal')
    lineas.append('─'*ancho)
    lineas.append(' EVENTOS RECIENTES')
    cantidad = max(1, filas-len(lineas)-8)
    for evento in estado.get('eventos', [])[-cantidad:]:
        lineas.append(' '+evento.get('hora', '')+'  '+evento.get('texto', ''))
    lineas.append('─'*ancho)
    lineas.extend(' '+linea for linea in AYUDA)
    lineas.append(' Captura · '+estado.get('carpeta', 'sin iniciar'))
    lineas.append(' '+(estado.get('error') or aviso or 'Escribe un comando y pulsa Enter.'))
    lineas.append(' > '+entrada_visible+'▌')
    if filas < 26:
        # En ventanas pequeñas se conservan el resumen, los avisos y el prompt.
        lineas = lineas[:min(9, max(3, filas-6))]+[
            ' Amplía la terminal para ver gráficas y diagnóstico completo.',
            ' cancelar · ayuda · salir',
            ' '+(estado.get('error') or aviso),
            ' > '+entrada_visible+'▌',
        ]
    return '\n'.join(texto_seguro(linea)[:ancho] for linea in lineas)


def procesar_orden(banco, texto):
    """Devuelve aviso y si se debe cerrar. Una orden enviada no implica aceptacion."""
    texto = texto.strip()
    if not texto:
        return '', False
    if texto == 'ayuda':
        return ' · '.join(AYUDA), False
    if texto == 'salir':
        return 'Cierre de captura solicitado. No se envía cancelación.', True
    alias = {'libre': 'auto_fijo45', 'pico': 'pico_simulado', 'motor on': 'motor_on', 'motor off': 'motor_off', 'sensor on': 'sensor_on', 'sensor off': 'sensor_off'}
    comando = alias.get(texto, texto)
    partes = texto.split()
    if len(partes) == 2 and partes[0] in ('curva', 'figura'):
        comando = 'curva_'+partes[1]
    elif len(partes) == 2 and partes[0] in ('fijo', 'auto_fijo', 'tiempo', 'g'):
        comando = partes[0]+partes[1]
    try:
        banco.enviar(comando)
    except ValueError as exc:
        return str(exc), False
    return 'Orden enviada · '+comando+' · comprueba su evento y estado', False


def ejecutar_terminal(banco, opciones, sin_color=False):
    """Abre una fuente y restaura entrada y pantalla aun con error o Ctrl+C.

    Cerrar nunca envia una orden implicita al motor. Comparte Banco con el panel,
    pero ambas interfaces no deben abrir simultaneamente el mismo puerto serial.
    """
    if os.name != 'posix':
        raise RuntimeError('La interfaz de terminal requiere Linux o un sistema POSIX')
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise RuntimeError('Abre este modo en una terminal interactiva, sin redirigir entrada o salida')
    import termios
    import tty
    print('Preparando '+opciones['fuente']+' y captura…', flush=True)
    banco.iniciar(dict(opciones, interfaz='terminal'))
    descriptor = sys.stdin.fileno()
    anterior = None
    entrada = ''
    aviso = ''
    escapando = False
    siguiente = 0.0
    try:
        anterior = termios.tcgetattr(descriptor)
        tty.setcbreak(descriptor)
        sys.stdout.write('\x1b[?1049h\x1b[?25l')
        sys.stdout.flush()
        terminar = False
        while not terminar:
            ahora = time.monotonic()
            if ahora >= siguiente:
                estado = banco.estado_actual()
                tamano = shutil.get_terminal_size((110, 34))
                vista = renderizar(estado, entrada, aviso, tamano.columns, tamano.lines)
                if not sin_color:
                    primera, resto = vista.split('\n', 1)
                    vista = '\x1b[1;36m'+primera+'\x1b[0m\n'+resto
                sys.stdout.write('\x1b[H'+vista+'\x1b[J')
                sys.stdout.flush()
                siguiente = ahora+.2
            if not select.select([descriptor], [], [], .05)[0]:
                continue
            datos = os.read(descriptor, 128)
            if not datos:
                break
            for caracter in datos.decode('utf-8', errors='ignore'):
                if caracter in ('\x03', '\x04'):
                    terminar = True
                    break
                if caracter == '\x1b':
                    escapando = True
                    continue
                if escapando:
                    if caracter.isalpha() or caracter == '~':
                        escapando = False
                    continue
                if caracter in ('\r', '\n'):
                    aviso, terminar = procesar_orden(banco, entrada)
                    entrada = ''
                    siguiente = 0
                    if terminar:
                        break
                elif caracter in ('\x7f', '\b'):
                    entrada = entrada[:-1]
                elif caracter == '\x15':
                    entrada = ''
                elif caracter.isascii() and caracter.isprintable() and len(entrada) < 100:
                    entrada += caracter
    except KeyboardInterrupt:
        pass
    finally:
        try:
            if anterior is not None:
                termios.tcsetattr(descriptor, termios.TCSADRAIN, anterior)
        finally:
            sys.stdout.write('\x1b[0m\x1b[?25h\x1b[?1049l')
            sys.stdout.flush()
            banco.desconectar()
            print('Captura guardada en '+banco.carpeta)
            print('Cerrar la terminal no envía cancelación al dispositivo.')
    return 0


def ejecutar_terminal_lineas(banco, opciones, sin_color=False):
    """Imprime mensajes sin ANSI ni borrar historial. Entrada normal con Enter."""
    if os.name != 'posix' or not sys.stdin.isatty() or not sys.stdout.isatty():
        raise RuntimeError('Abre este modo en una terminal interactiva')
    print('BANCO DE FRENADO · TERMINAL CON HISTORIAL', flush=True)
    print('Escribe comandos y pulsa Enter. sensor_on muestra cambios y conteos de marcas completas.', flush=True)
    print('sensor_off lo desactiva. salir cierra la captura.', flush=True)
    banco.iniciar(dict(opciones, interfaz='terminal'))
    siguiente=0.0
    perdidos_vistos=0
    try:
        terminar=False
        while not terminar:
            # Consumir una cantidad acotada para que los comandos sigan respondiendo.
            for _ in range(128):
                try: linea=banco.salida_terminal.get_nowait()
                except queue.Empty: break
                print(texto_seguro(linea), flush=True)
            if banco.salida_terminal_perdida != perdidos_vistos:
                perdidos_vistos=banco.salida_terminal_perdida
                print('La pantalla omitió '+str(perdidos_vistos)+' mensajes. Revisa el CSV completo.', flush=True)
            estado=banco.estado_actual()
            ahora=time.monotonic()
            if ahora>=siguiente:
                if not estado.get('sensor',{}).get('activo'):
                    d=estado.get('ultimo',{})
                    print('RPM '+numero(d.get('rpm_mostrada',d.get('rpm_validada')))+(' (cero estimado tras 1 s sin pulsos)' if d.get('cero_estimado') else '')+' | pulsos '+numero(d.get('pulsos_aceptados'))+
                          ' | medición '+str(d.get('estado_medicion','sin datos'))+
                          ' | '+str(d.get('modo','esperando ESP32')), flush=True)
                siguiente=ahora+1
            if not estado.get('activo'):
                print('Captura detenida · '+(estado.get('error') or 'conexión cerrada'), flush=True)
                break
            if select.select([sys.stdin],[],[],.05)[0]:
                entrada=sys.stdin.readline()
                if not entrada: break
                aviso,terminar=procesar_orden(banco,entrada)
                print(texto_seguro(aviso), flush=True)
    except KeyboardInterrupt:
        print('\nCierre solicitado.', flush=True)
    finally:
        banco.desconectar()
        print('Captura guardada en '+banco.carpeta, flush=True)
        print('El cierre no envía cancelación ni sensor_off al dispositivo.', flush=True)
    return 0
