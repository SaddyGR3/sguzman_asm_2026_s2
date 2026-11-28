function resultado = comparar_frenado_por_intervalos(libre, carpetasAjuste, carpetaValidacion, ventana, marcasPorVuelta)
% Conserva RPM y reconstruye el intervalo fisico con periodo y antiguedad.
% Ajusta c30 con dos corridas y evalua promedios del modelo en la reservada.
% El modelo libre a,b queda fijo. No se modifica el analisis instantaneo previo.
carpetaScripts = fileparts(mfilename('fullpath'));
raiz = fullfile(carpetaScripts, '..', 'capturas', 'escritorio', 'reales');
if nargin < 1 || isempty(libre)
    archivo = load(fullfile(carpetaScripts, 'resultados_reales', ...
        'modelo_libre_20261127_210612_886523', 'modelo.mat'), 'resultado');
    libre = archivo.resultado;
end
if nargin < 2
    carpetasAjuste = {fullfile(raiz, '20261127_211944_350811'), ...
        fullfile(raiz, '20261127_212026_949598')};
end
if nargin < 3, carpetaValidacion = fullfile(raiz, '20261127_212109_143576'); end
if nargin < 4, ventana = [0.5 2]; end
if nargin < 5, marcasPorVuelta = 1; end
assert(isscalar(marcasPorVuelta) && marcasPorVuelta >= 1 && fix(marcasPorVuelta) == marcasPorVuelta, ...
    'Indique las marcas fisicas usadas al capturar, no las del firmware actual');
assert(numel(ventana)==2 && all(isfinite(ventana)) && ventana(1)>=0 && ventana(2)>ventana(1), 'Ventana no valida');
a = libre.a; b = libre.b;
assert(isfinite(a) && a>=0 && isfinite(b) && b>0, 'Parametros libres no validos');
carpetasAjuste = cellstr(string(carpetasAjuste));
assert(numel(carpetasAjuste)>=2, 'Se requieren dos capturas de ajuste');
ajuste = cell(numel(carpetasAjuste), 1);
for k=1:numel(ajuste), ajuste{k}=leer_intervalos(carpetasAjuste{k}, ventana, marcasPorVuelta); end
validacion=leer_intervalos(carpetaValidacion, ventana, marcasPorVuelta);
ids=cellfun(@(e) string(e.id), ajuste);
assert(numel(unique(ids))==numel(ids) && ~any(ids==string(validacion.id)), 'La corrida reservada debe ser distinta');
% Comparacion justa. Ambos metodos usan exactamente los mismos intervalos
% unicos y excluyen el primero, usado como condicion inicial, de las metricas.
c30=ajustar_c(ajuste,a,b,true);
cInstantaneo=ajustar_c(ajuste,a,b,false);
ensayos=[ajuste; {validacion}];
metricas=table(); predicciones=cell(numel(ensayos),1);
for k=1:numel(ensayos)
    e=ensayos{k};
    [base,q]=observacion(e,a,b,true);
    media=base-c30*q;
    [baseVieja,qVieja]=observacion(e,a,b,false);
    instantanea=baseVieja-cInstantaneo*qVieja;
    assert(all(isfinite(media)) && all(media>0), 'Prediccion no positiva en el intervalo');
    error=media-e.datos.rpm_validada;
    errorViejo=instantanea-e.datos.rpm_validada;
    evaluar=(1:height(e.datos))'>1;
    uso="Ajuste";
    if k==numel(ensayos), uso="Validacion reservada"; end
    fila=table(string(e.id),uso,e.registrosOriginales,height(e.datos),nnz(evaluar), ...
        mean(abs(error(evaluar))),sqrt(mean(error(evaluar).^2)),max(abs(error(evaluar))), ...
        mean(abs(errorViejo(evaluar))),sqrt(mean(errorViejo(evaluar).^2)),max(abs(errorViejo(evaluar))), ...
        'VariableNames',{'captura','uso','registros_originales','intervalos_unicos','intervalos_evaluados', ...
        'mae_intervalos_rpm','rmse_intervalos_rpm','max_intervalos_rpm', ...
        'mae_instantaneo_rpm','rmse_instantaneo_rpm','max_instantaneo_rpm'});
    metricas=[metricas;fila]; %#ok<AGROW>
    P=e.datos;
    P.rpm_modelo_media=media; P.rpm_modelo_instantaneo=instantanea;
    P.error_media_rpm=error; P.usado_en_metricas=evaluar;
    predicciones{k}=P;
end
figura=figure('Name','Comparacion por intervalos de medicion','Color','w','Position',[100 100 1100 720]);
P=predicciones{end};
ax=axes(figura,'Position',[0.10 0.48 0.85 0.42]);
plot(ax,P.t_registro_s,P.rpm_validada,'o-','Color',[0 0.55 0.48],'LineWidth',1.5, ...
    'DisplayName','RPM originales de la tercera corrida'); hold(ax,'on');
plot(ax,P.t_registro_s,P.rpm_modelo_media,'--','Color',[0.88 0.34 0.13],'LineWidth',2, ...
    'DisplayName','Promedio del modelo en cada intervalo');
plot(ax,P.t_registro_s,P.rpm_modelo_instantaneo,':','Color',[0.35 0.40 0.45],'LineWidth',2, ...
    'DisplayName','Comparacion instantanea con mismos datos unicos');
grid(ax,'on'); xlim(ax,ventana); ylim(ax,[0 1200]);
ylabel(ax,'Velocidad [RPM]');
title(ax,'Mismas RPM, comparadas sobre sus intervalos fisicos');
legend(ax,'Location','northeast');
axError=axes(figura,'Position',[0.10 0.23 0.85 0.17]);
plot(axError,P.t_registro_s,P.error_media_rpm,'o-','Color',[0.55 0.25 0.72],'LineWidth',1.4);
yline(axError,0,':','HandleVisibility','off');grid(axError,'on');xlim(axError,ventana);
xlabel(axError,'Tiempo del registro desde el inicio del ensayo [s]');
ylabel(axError,'Error [RPM]');
annotation(figura,'textbox',[0.10 0.025 0.85 0.14], ...
    'String',sprintf(['Modelo dn/dt = -%.3f - %.5f n - %.3f. No se cambian las RPM medidas.\n' ...
    'Corrida reservada   error absoluto medio %.2f RPM   maximo %.2f RPM.\n' ...
    'Cada intervalo se cuenta una vez. El primero fija una media inicial, no una velocidad instantanea.\n' ...
    'Los tiempos de medicion de la corrida reservada se usan para evaluar promedios, sin corregir el estado.'], ...
    a,b,c30,metricas.mae_intervalos_rpm(end),metricas.max_intervalos_rpm(end)), ...
    'EdgeColor','none','FontSize',10,'Color',[0.12 0.16 0.20],'Interpreter','none');
estilo_figura(figura);
salida=fullfile(carpetaScripts,'resultados_reales',['freno30_intervalos_' validacion.id]);
if ~isfolder(salida),mkdir(salida);end
parametros=table(a,b,c30,cInstantaneo,marcasPorVuelta,'VariableNames', ...
    {'a_libre_rpm_s','b_libre_inverso_s','c30_intervalos_rpm_s','c30_instantaneo_rpm_s','marcas_por_vuelta'});
writetable(parametros,fullfile(salida,'parametros.csv'));
writetable(metricas,fullfile(salida,'metricas.csv'));
for k=1:numel(ensayos)
    writetable(predicciones{k},fullfile(salida,['intervalos_' ensayos{k}.id '.csv']));
end
print(figura,fullfile(salida,'validacion.png'),'-dpng','-r160');
savefig(figura,fullfile(salida,'validacion.fig'));
resultado=struct('a',a,'b',b,'c30',c30,'cInstantaneo',cInstantaneo,'ventana',ventana, ...
    'marcasPorVuelta',marcasPorVuelta,'ajuste',{ajuste},'validacion',validacion, ...
    'metricas',metricas,'predicciones',{predicciones},'salida',salida);
save(fullfile(salida,'modelo.mat'),'resultado');
disp(parametros);disp(metricas);
fprintf('Los parametros solo usan las dos corridas de ajuste.\n');
fprintf('Las metricas reservadas usan sus tiempos e intervalos observados, sin reajustar el modelo.\n');
fprintf('La antiguedad corresponde al ultimo inicio de marca validado. Tiempos aproximados por resolucion de registro.\n');
fprintf('El modelo libre sigue fijo y conserva las limitaciones de su ajuste anterior.\n');
fprintf('Permanece error sistematico. Esta mejora no declara el modelo definitivo.\n');
fprintf('Resultados guardados en %s\n',salida);
end

function c=ajustar_c(ensayos,a,b,porIntervalo)
numerador=0;denominador=0;
for k=1:numel(ensayos)
    e=ensayos{k};[base,q]=observacion(e,a,b,porIntervalo);
    numerador=numerador+sum(q.*(base-e.datos.rpm_validada));
    denominador=denominador+sum(q.^2);
end
assert(denominador>0,'No hay intervalo suficiente para ajustar');
c=numerador/denominador;
assert(isfinite(c) && c>=0,'El aporte de freno debe ser no negativo');
end

function [base,q]=observacion(e,a,b,porIntervalo)
P=e.datos;
if porIntervalo
    % Para n'= -A-b*n, la media en [s,f] es (N0+A/b)*F-A/b.
    % N0 es la velocidad al final del primer intervalo. Su media medida fija
    % N0 para cada A=a+c. El cociente F/F(1) elimina N0 sin ajustarlo aparte.
    T=P.periodo_s;
    final=P.t_fin_intervalo_s-P.t_fin_intervalo_s(1);
    F=exp(-b*final).*expm1(b*T)./(b*T);
    razon=F/F(1);
else
    razon=exp(-b*(P.t_registro_s-P.t_registro_s(1)));
end
q=(1-razon)/b;
base=P.rpm_validada(1)*razon-a*q;
end

function e=leer_intervalos(carpeta,ventana,marcas)
D=readtable(fullfile(carpeta,'diagnostico_1.csv'),'TextType','string');
E=readtable(fullfile(carpeta,'eventos_1.csv'),'TextType','string');
inicio=find(E.tipo=="ENSAYO_FIJO_INICIO");assert(isscalar(inicio),'Se requiere un solo ensayo fijo');
t0=E.tiempo_ms(inicio);
fin=find(startsWith(E.tipo,"ENSAYO_FIN_DURACION") & E.tiempo_ms>t0);
assert(isscalar(fin) && E.tiempo_ms(fin)>=t0+1000*ventana(2),'Ensayo incompleto');
activos=E.tiempo_ms>=t0 & E.tiempo_ms<E.tiempo_ms(fin);
enVentana=activos & E.tiempo_ms<=t0+1000*ventana(2);
servo=E.valor(enVentana & E.tipo=="SERVO_CMD");
assert(~isempty(servo) && all(servo==30),'Se requiere orden de 30 grados');
assert(~any(startsWith(E.tipo(activos),"FALLO_")),'El ensayo contiene fallos');
filas=D.modo=="FIJO" & D.tiempo_ms>=t0 & D.tiempo_ms<E.tiempo_ms(fin);
D=D(filas,:);t=(D.tiempo_ms-t0)/1000;
seleccion=t>=ventana(1) & t<=ventana(2);D=D(seleccion,:);t=t(seleccion);
assert(height(D)>=10 && all(diff(t)>0 & diff(t)<=0.15),'Registro insuficiente o con huecos');
assert(all(D.estado_medicion=="RECIENTE" & isfinite(D.rpm_validada)),'Hay medidas invalidas');
assert(all(D.motor_encendido==0) && all(D.perdidos_cola==0),'Motor o cola no validos');
assert(all(D.periodo_us>0 & isfinite(D.antiguedad_us) & D.antiguedad_us>=0),'Periodo o antiguedad no validos');
assert(all(abs(D.rpm_validada-60000000./(D.periodo_us*marcas))<0.02), ...
    'Las RPM no corresponden al periodo y las marcas indicadas');
registrosOriginales=height(D);
final=t-D.antiguedad_us/1e6;
inicial=final-D.periodo_us/1e6;
% Cada marca validada debe reconstruirse con el mismo final dentro del
% redondeo temporal, aun cuando figure en varias filas seriales.
[~,indices]=unique(D.pulsos_aceptados,'stable');
for j=1:numel(indices)
    grupo=D.pulsos_aceptados==D.pulsos_aceptados(indices(j));
    assert(all(D.periodo_us(grupo)==D.periodo_us(indices(j))) && ...
        max(final(grupo))-min(final(grupo))<=0.002,'Marca repetida incoherente');
end
D=D(indices,:);t=t(indices);final=final(indices);inicial=inicial(indices);
assert(height(D)>=8 && all(diff(final)>0) && all(inicial>=0.25), ...
    'No hay suficientes intervalos despues del transitorio inicial');
P=table(D.tiempo_ms,t,D.rpm_validada,D.periodo_us/1e6,D.antiguedad_us/1e6, ...
    inicial,final,(inicial+final)/2,D.pulsos_aceptados, ...
    'VariableNames',{'tiempo_original_ms','t_registro_s','rpm_validada','periodo_s', ...
    'antiguedad_s','t_inicio_intervalo_s','t_fin_intervalo_s','t_centro_intervalo_s','pulsos_aceptados'});
[~,id]=fileparts(carpeta);
e=struct('id',id,'carpeta',carpeta,'registrosOriginales',registrosOriginales,'datos',P);
end
