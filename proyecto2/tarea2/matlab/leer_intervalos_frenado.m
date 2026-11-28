function e=leer_intervalos_frenado(carpeta,angulo,opciones)
% Extrae un ensayo sin interpolar y conserva los intervalos observados.
% Las opciones requieren bandaRPM, inicioFisicoMinimoS, marcasPorVuelta y permitirParciales.
selector=regexp(carpeta,'#ensayo=(\d+)$','tokens','once');
numero=[];
if ~isempty(selector)
    numero=str2double(selector{1});
    carpeta=regexprep(carpeta,'#ensayo=\d+$','');
end
D=readtable(fullfile(carpeta,'diagnostico_1.csv'),'TextType','string');
E=readtable(fullfile(carpeta,'eventos_1.csv'),'TextType','string');
% -1 indica tiempo sin origen. RPM_INICIO lleva cero literal y puede anunciarse
% despues de eventos ya temporizados. Ninguno representa un reinicio de placa.
E=E(E.tiempo_ms>=0 & E.tipo~="RPM_INICIO",:);
D=D(D.tiempo_ms>=0,:);
% Los tiempos pueden reiniciarse dentro de una conexion. No ordenar ni unir epocas.
epocaE=cumsum([0;diff(E.tiempo_ms)<0]);epocaD=cumsum([0;diff(D.tiempo_ms)<0]);
inicio=find(E.tipo=="ENSAYO_FIJO_INICIO");
if ~isempty(numero),inicio=inicio(E.valor(inicio)==numero);end
assert(isscalar(inicio),'Se requiere un ensayo unico o un selector #ensayo=N');
assert(max(epocaE)==max(epocaD),'Reinicios no coincidentes entre eventos y diagnostico');
epoca=epocaE(inicio);
E=E(epocaE==epoca,:);D=D(epocaD==epoca,:);
inicio=find(E.tipo=="ENSAYO_FIJO_INICIO");
if ~isempty(numero),inicio=inicio(E.valor(inicio)==numero);end
assert(isscalar(inicio),'Selector ambiguo dentro de la epoca');
t0=E.tiempo_ms(inicio);
% Las capturas antiguas miden un sector. Las nuevas registran la vuelta completa.
intervalosMedicion=1;
metadato=find(E.tipo=="MEDICION_INTERVALOS" & E.tiempo_ms<=t0,1,'last');
if ~isempty(metadato)
    intervalosMedicion=E.valor(metadato);
    assert(intervalosMedicion==opciones.marcasPorVuelta, ...
        'Configuracion de marcas no coincide con la ventana de vuelta completa');
end
terminal=find(E.tiempo_ms>t0 & (startsWith(E.tipo,"ENSAYO_FIN_DURACION") | startsWith(E.tipo,"FALLO_") | E.tipo=="ENSAYO_CANCELADO"),1);
assert(~isempty(terminal),'El ensayo sigue abierto o no tiene final registrado');
completa=startsWith(E.tipo(terminal),"ENSAYO_FIN_DURACION");
assert(completa || (opciones.permitirParciales && E.tipo(terminal)=="FALLO_MEDICION"), ...
    'Final no admitido. No se mezclan cancelaciones u otros fallos');
fin=E.tiempo_ms(terminal);
rpmInicial=E.valor(E.tipo=="RPM_INICIAL_X100" & E.tiempo_ms>=t0 & E.tiempo_ms<fin)/100;
assert(isscalar(rpmInicial),'Falta velocidad inicial unica');
filas=D.modo=="FIJO" & D.tiempo_ms>=t0 & D.tiempo_ms<fin;
D=D(filas,:);t=(D.tiempo_ms-t0)/1000;
assert(height(D)>=3 && all(diff(t)>0 & diff(t)<=0.15),'Registro incompleto o desordenado');
assert(all(D.motor_encendido==0) && all(D.perdidos_cola==0),'Motor encendido o perdidas de cola');
validas=D.estado_medicion=="RECIENTE" & isfinite(D.rpm_validada) & D.periodo_us>0;
final=t-D.antiguedad_us/1e6;inicial=final-D.periodo_us/1e6;
seleccion=validas & D.rpm_validada>=opciones.bandaRPM(1) & D.rpm_validada<=opciones.bandaRPM(2) & ...
    inicial>=opciones.inicioFisicoMinimoS;
D=D(seleccion,:);t=t(seleccion);final=final(seleccion);inicial=inicial(seleccion);
assert(height(D)>=3,'No hay al menos tres intervalos candidatos en la banda');
assert(all(abs(D.rpm_validada-60000000*intervalosMedicion./(D.periodo_us*opciones.marcasPorVuelta))<0.02), ...
    'Marcas y periodos no corresponden a las RPM');
activos=E.tiempo_ms>=t0 & E.tiempo_ms<=t0+1000*max(t);
servo=E.valor(activos & E.tipo=="SERVO_CMD");
assert(~isempty(servo) && all(servo==angulo),'La orden del servo no corresponde al grupo');
assert(~any(E.tipo(activos)=="MOTOR_CMD" & E.valor(activos)~=0),'Motor encendido durante el tramo');
[~,indices]=unique(D.pulsos_aceptados,'stable');
for k=1:numel(indices)
    conjunto=D.pulsos_aceptados==D.pulsos_aceptados(indices(k));
    assert(all(D.periodo_us(conjunto)==D.periodo_us(indices(k))) && ...
        max(final(conjunto))-min(final(conjunto))<=0.002,'Repeticiones de marca incoherentes');
end
D=D(indices,:);t=t(indices);final=final(indices);inicial=inicial(indices);
assert(height(D)>=3 && all(diff(final)>0),'Muy pocos intervalos unicos o tiempos incoherentes');
P=table(D.tiempo_ms,t,D.rpm_validada,D.periodo_us/1e6,D.antiguedad_us/1e6,inicial,final, ...
    (inicial+final)/2,D.pulsos_aceptados,'VariableNames',{'tiempo_original_ms','t_registro_s', ...
    'rpm_validada','periodo_s','antiguedad_s','t_inicio_intervalo_s','t_fin_intervalo_s', ...
    't_centro_intervalo_s','pulsos_aceptados'});
[~,id]=fileparts(carpeta);
if ~isempty(numero),id=sprintf('%s_ensayo%d',id,numero);end
e=struct('id',id,'carpeta',carpeta,'completa',completa,'terminacion',E.tipo(terminal), ...
    'rpmInicial',rpmInicial,'rechazosCortos',max(D.pulsos_rechazados), ...
    'saltosRechazados',max(D.saltos_rechazados),'datos',P);
end

