function resultado = caracterizar_angulos_freno(grupos, opciones)
% Compara aportes constantes por angulo en una banda comun de RPM medidas.
% Dos primeras corridas ajustan. Las restantes comprueban sin reajustar.
% Los ensayos fallidos solo aportan tramos parciales expresamente etiquetados.
carpetaScripts=fileparts(mfilename('fullpath'));
raiz=fullfile(carpetaScripts,'..','capturas','escritorio','reales');
if nargin<1 || isempty(grupos)
    grupos=struct('angulo',{},'capturas',{});
    ids={ ...
        {'20261127_220904_313271','20261127_221025_334470','20261127_221108_074927'}, ...
        {'20261127_211944_350811','20261127_212026_949598','20261127_212109_143576'}, ...
        {'20261127_221826_686696','20261127_221914_060863','20261127_221959_439179'}, ...
        {'20261127_221348_439279','20261127_221444_959171','20261127_221525_825693','20261127_221607_093612'}};
    angulos=[33 30 28 25];
    for k=1:numel(angulos)
        rutas=cellfun(@(id) fullfile(raiz,id),ids{k},'UniformOutput',false);
        grupos(k)=struct('angulo',angulos(k),'capturas',{rutas});
    end
end
if nargin<2,opciones=struct();end
opciones=defecto(opciones,'bandaRPM',[500 1100]);
opciones=defecto(opciones,'inicioFisicoMinimoS',0.25);
opciones=defecto(opciones,'marcasPorVuelta',1);
opciones=defecto(opciones,'permitirParciales',true);
opciones=defecto(opciones,'permitirExploratorios',false);
opciones=defecto(opciones,'permitirAporteNegativo',false);
opciones=defecto(opciones,'modeloLibre',fullfile(carpetaScripts,'resultados_reales', ...
    'modelo_libre_20261127_210612_886523','modelo.mat'));
opciones=defecto(opciones,'salida',fullfile(carpetaScripts,'resultados_reales','caracterizacion_angulos_actual'));
assert(numel(opciones.bandaRPM)==2 && all(isfinite(opciones.bandaRPM)) && ...
    opciones.bandaRPM(1)>0 && opciones.bandaRPM(2)>opciones.bandaRPM(1),'Banda de RPM no valida');
assert(isscalar(opciones.marcasPorVuelta) && opciones.marcasPorVuelta>=1 && ...
    fix(opciones.marcasPorVuelta)==opciones.marcasPorVuelta,'Marcas por vuelta no validas');
archivo=load(opciones.modeloLibre,'resultado');a=archivo.resultado.a;b=archivo.resultado.b;
assert(isfinite(a) && a>=0 && isfinite(b) && b>0,'Modelo libre no valido');
resumen=table();corridas=table();analisis=cell(numel(grupos),1);
for g=1:numel(grupos)
    capturas=cellstr(string(grupos(g).capturas));
    assert(numel(capturas)>=3 || (opciones.permitirExploratorios && ~isempty(capturas)), ...
        'Cada angulo necesita dos corridas de ajuste y una de comprobacion');
    nAjuste=min(2,numel(capturas));
    ensayos=cell(numel(capturas),1);
    for k=1:numel(capturas),ensayos{k}=leer_intervalos_frenado(capturas{k},grupos(g).angulo,opciones);end
    ids=cellfun(@(e) string(e.id),ensayos);
    assert(numel(unique(ids))==numel(ids),'No repita capturas dentro de un grupo');
    numerador=0;denominador=0;
    for k=1:nAjuste
        [base,q]=observacion(ensayos{k}.datos,a,b);
        numerador=numerador+sum(q.*(base-ensayos{k}.datos.rpm_validada));
        denominador=denominador+sum(q.^2);
    end
    c=numerador/denominador;
    assert(isfinite(c) && (c>=0 || opciones.permitirAporteNegativo),'Aporte comun no valido');
    individuales=zeros(numel(ensayos),1);completas=0;minN=Inf;maxN=0;erroresComprobacion=[];
    for k=1:numel(ensayos)
        e=ensayos{k};P=e.datos;[base,q]=observacion(P,a,b);
        pred=base-c*q;error=pred-P.rpm_validada;
        assert(all(isfinite(pred)) && all(pred>0),'Prediccion no positiva');
        evaluar=(1:height(P))'>1;
        individuales(k)=sum(q.*(base-P.rpm_validada))/sum(q.^2);
        uso="Ajuste";
        if numel(ensayos)<3,uso="Ajuste exploratorio sin comprobacion reservada";end
        if k>nAjuste,uso="Comprobacion reservada";end
        calidad="Completa";if ~e.completa,calidad="Tramo parcial de ensayo fallido";end
        completas=completas+e.completa;minN=min(minN,height(P));maxN=max(maxN,height(P));
        mae=mean(abs(error(evaluar)));
        if k>nAjuste,erroresComprobacion=[erroresComprobacion;abs(error(evaluar))];end %#ok<AGROW>
        fila=table(grupos(g).angulo,string(e.id),uso,calidad,string(e.terminacion), ...
            e.rpmInicial,height(P),nnz(evaluar),min(P.rpm_validada),max(P.rpm_validada), ...
            min(P.t_inicio_intervalo_s),max(P.t_fin_intervalo_s), ...
            e.rechazosCortos,e.saltosRechazados,individuales(k),mae, ...
            sqrt(mean(error(evaluar).^2)),max(abs(error(evaluar))), ...
            'VariableNames',{'servo_grados','captura','uso','calidad','terminacion', ...
            'rpm_inicial_ensayo','intervalos_unicos','intervalos_evaluados','rpm_minima','rpm_maxima', ...
            'inicio_fisico_s','final_fisico_s','pulsos_cortos_rechazados','saltos_rechazados', ...
            'c_individual_diagnostico_rpm_s','mae_rpm','rmse_rpm','max_error_rpm'});
        corridas=[corridas;fila]; %#ok<AGROW>
        P.rpm_modelo_media=pred;P.error_rpm=error;P.usado_en_metricas=evaluar;
        e.datos=P;ensayos{k}=e;
    end
    nota="Aproximacion local";
    if numel(ensayos)<3,nota="Exploratorio sin comprobacion reservada";end
    if minN<8,nota="Pocos intervalos de medicion";end
    if completas<numel(ensayos),nota="Exploratorio, ensayos fallidos y pocos intervalos";end
    fila=table(grupos(g).angulo,numel(ensayos),completas,numel(ensayos)-completas,c, ...
        min(individuales),max(individuales),minN,maxN,mean(erroresComprobacion),nota, ...
        'VariableNames',{'servo_grados','corridas','completas','parciales','c_comun_rpm_s', ...
        'c_individual_min_rpm_s','c_individual_max_rpm_s','intervalos_min','intervalos_max', ...
        'mae_comprobacion_rpm','alcance'});
    resumen=[resumen;fila]; %#ok<AGROW>
    analisis{g}=struct('angulo',grupos(g).angulo,'c',c,'ensayos',{ensayos});
end
assert(numel(unique(corridas.captura))==height(corridas),'Una captura aparece en mas de un grupo');
figura=figure('Name','Aporte estimado segun orden al servo','Color','w','Position',[100 100 1100 650]);
ax=axes(figura,'Position',[0.10 0.32 0.85 0.57]);hold(ax,'on');
for g=1:height(resumen)
    color=[0 0.55 0.48];if resumen.parciales(g)>0,color=[0.85 0.35 0.15];end
    % El rango muestra ajustes individuales, no intervalos de confianza.
    plot(ax,[resumen.servo_grados(g) resumen.servo_grados(g)], ...
        [resumen.c_individual_min_rpm_s(g) resumen.c_individual_max_rpm_s(g)], ...
        '-','Color',color,'LineWidth',2,'HandleVisibility','off');
    plot(ax,resumen.servo_grados(g),resumen.c_comun_rpm_s(g),'o','Color',color, ...
        'MarkerSize',9,'LineWidth',2,'HandleVisibility','off');
    desplazamiento=max(2,0.04*max(resumen.c_individual_max_rpm_s));
    if mod(g,2)==1,desplazamiento=desplazamiento*3;end
    text(ax,resumen.servo_grados(g),resumen.c_individual_max_rpm_s(g)+desplazamiento, ...
        sprintf('%.0f RPM/s',resumen.c_comun_rpm_s(g)), ...
        'HorizontalAlignment','center','Color',color,'FontSize',11);
end
set(ax,'XDir','reverse');xticks(ax,sort(resumen.servo_grados));
xlim(ax,[min(resumen.servo_grados)-1 max(resumen.servo_grados)+1]);
ylim(ax,[min(0,min(resumen.c_individual_min_rpm_s)-10) ...
    max(10,1.2*max(resumen.c_individual_max_rpm_s)+50)]);grid(ax,'on');
xlabel(ax,'Orden al servo [grados], mayor frenado hacia la derecha');
ylabel(ax,'Aporte adicional estimado [RPM/s]');
title(ax,'Caracterizacion exploratoria por angulo, sin interpolar entre condiciones');
annotation(figura,'textbox',[0.10 0.025 0.85 0.17], ...
    'String',sprintf(['Modelo local dn/dt = -%.3f - %.5f n - c(angulo). Banda medida de %g a %g RPM.\n' ...
    'Circulos ajustados con hasta dos corridas. Rangos individuales, no intervalos de confianza.\n' ...
    'Verde para ensayos completos. Naranja para tramos medidos de ensayos fallidos.\n' ...
    'Pocos intervalos en los frenados fuertes. No es una calibracion definitiva ni una ley continua del servo.'], ...
    a,b,opciones.bandaRPM), ...
    'EdgeColor','none','FontSize',10,'Color',[0.12 0.16 0.20],'Interpreter','none');
estilo_figura(figura);
comprobacion=figure('Name','Comprobacion por angulo','Color','w','Position',[100 100 1200 790]);
for g=1:numel(analisis)
    ax=subplot(ceil(numel(analisis)/2),2,g,'Parent',comprobacion);hold(ax,'on');
    es=analisis{g}.ensayos;
    mostrar=3:numel(es);
    if numel(es)<3,mostrar=1:numel(es);end
    for k=mostrar
        P=es{k}.datos;
        colorMedida=[0 0.40 0.70];colorModelo=[0.88 0.34 0.13];
        if k>3,colorMedida=[0.55 0.25 0.72];colorModelo=[0.25 0.30 0.35];end
        plot(ax,P.t_centro_intervalo_s,P.rpm_validada,'o-','Color',colorMedida,'LineWidth',1.4, ...
            'DisplayName',sprintf('Medida corrida %d',k));
        plot(ax,P.t_centro_intervalo_s,P.rpm_modelo_media,'--','Color',colorModelo,'LineWidth',1.8, ...
            'DisplayName',sprintf('Modelo corrida %d',k));
    end
    grid(ax,'on');ylim(ax,[400 1150]);xlabel(ax,'Centro del intervalo [s]');ylabel(ax,'RPM');
    etiqueta='Ensayos completos';if resumen.parciales(g)>0,etiqueta='Tramos parciales, no ensayos completos';end
    if numel(es)<3,etiqueta='Ajuste exploratorio, sin comprobacion reservada';end
    title(ax,{sprintf('%g grados',analisis{g}.angulo),etiqueta});legend(ax,'Location','best');
end
estilo_figura(comprobacion);
salida=opciones.salida;if ~isfolder(salida),mkdir(salida);end
writetable(resumen,fullfile(salida,'resumen_angulos.csv'));
writetable(corridas,fullfile(salida,'corridas.csv'));
for g=1:numel(analisis)
    es=analisis{g}.ensayos;
    for k=1:numel(es)
        writetable(es{k}.datos,fullfile(salida,['intervalos_' es{k}.id '.csv']));
    end
end
print(figura,fullfile(salida,'mapa_angulos.png'),'-dpng','-r160');
savefig(figura,fullfile(salida,'mapa_angulos.fig'));
print(comprobacion,fullfile(salida,'comprobacion.png'),'-dpng','-r160');
savefig(comprobacion,fullfile(salida,'comprobacion.fig'));
resultado=struct('a',a,'b',b,'opciones',opciones,'grupos',grupos,'resumen',resumen, ...
    'corridas',corridas,'analisis',{analisis},'salida',salida);
save(fullfile(salida,'caracterizacion.mat'),'resultado');
disp(resumen);
fprintf('Los fallos no se convirtieron en corridas completas. Sus estimaciones son parciales.\n');
fprintf('La banda permitida es comun, pero los intervalos y rangos efectivamente medidos difieren.\n');
if any(resumen.servo_grados==30)
    fprintf('30 grados se recalcula en la misma banda sin modificar su modelo anterior.\n');
end
fprintf('Los grupos con menos de tres corridas no tienen comprobacion reservada.\n');
fprintf('Un aporte negativo permitido es diagnostico de discrepancia respecto del modelo libre, no aceleracion del freno.\n');
fprintf('La estimacion individual de comprobacion es solo diagnostica y no cambia el modelo comun.\n');
fprintf('Resultados guardados en %s\n',salida);
end

function [base,q]=observacion(P,a,b)
T=P.periodo_s;final=P.t_fin_intervalo_s-P.t_fin_intervalo_s(1);
F=exp(-b*final).*expm1(b*T)./(b*T);razon=F/F(1);
q=(1-razon)/b;base=P.rpm_validada(1)*razon-a*q;
end

function opciones=defecto(opciones,nombre,valor)
if ~isfield(opciones,nombre),opciones.(nombre)=valor;end
end
