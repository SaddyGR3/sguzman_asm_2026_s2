function resultado = validar_giro_libre_dos_marcas
% Comprueba el modelo anterior sin ajustar parametros con estas capturas.
carpeta=fileparts(mfilename('fullpath'));
raiz=fullfile(carpeta,'..','capturas','escritorio','reales');
ids={'20261128_010755_149886','20261128_010906_181118'};
fuente=fullfile(carpeta,'resultados_reales','modelo_libre_20261127_210612_886523','parametros.csv');
parametros=readtable(fuente);a=parametros.a_rpm_s(1);b=parametros.b_inverso_s(1);
opciones=struct('bandaRPM',[500 1100],'inicioFisicoMinimoS',0.25, ...
    'marcasPorVuelta',2,'permitirParciales',false);
salida=fullfile(carpeta,'resultados_reales','validacion_libre_dos_marcas');
if ~isfolder(salida),mkdir(salida);end
resumen=table();paridad=table();ensayos=cell(numel(ids),1);
figura=figure('Name','Modelo libre anterior con dos marcas','Color','w','Position',[100 100 1200 760]);
for k=1:numel(ids)
    e=leer_intervalos_frenado(fullfile(raiz,ids{k}),45,opciones);P=e.datos;
    T=P.periodo_s;relativo=P.t_fin_intervalo_s-P.t_fin_intervalo_s(1);
    F=exp(-b*relativo).*expm1(b*T)./(b*T);razon=F/F(1);
    pred=P.rpm_validada(1)*razon-a*(1-razon)/b;
    error=pred-P.rpm_validada;evaluar=(1:height(P))'>1;
    P.rpm_modelo_anterior_media=pred;P.error_modelo_menos_medida_rpm=error;
    P.usado_en_metricas=evaluar;P.paridad=mod(P.pulsos_aceptados,2);
    resumen=[resumen;table(string(e.id),height(P),nnz(evaluar), ...
        mean(abs(error(evaluar))),sqrt(mean(error(evaluar).^2)), ...
        max(abs(error(evaluar))),mean(error(evaluar)), ...
        min(P.rpm_validada),max(P.rpm_validada), ...
        'VariableNames',{'captura','intervalos_unicos','intervalos_evaluados', ...
        'mae_rpm','rmse_rpm','max_error_absoluto_rpm','sesgo_rpm','rpm_minima','rpm_maxima'})]; %#ok<AGROW>
    for par=0:1
        seleccion=evaluar & P.paridad==par;
        paridad=[paridad;table(string(e.id),par,nnz(seleccion),mean(error(seleccion)), ...
            median(error(seleccion)), ...
            'VariableNames',{'captura','paridad_contador','intervalos_evaluados','sesgo_rpm','mediana_error_rpm'})]; %#ok<AGROW>
    end
    ax=subplot(2,numel(ids),k,'Parent',figura);hold(ax,'on');
    plot(ax,P.t_centro_intervalo_s,P.rpm_validada,'o','Color',[0 0.4 0.7], ...
        'MarkerSize',4,'DisplayName','Medias observadas');
    plot(ax,P.t_centro_intervalo_s,pred,'-','Color',[0.85 0.3 0.1], ...
        'LineWidth',1.8,'DisplayName','Modelo anterior, sin reajustar');
    title(ax,sprintf('Corrida libre %d, dos marcas',k));ylabel(ax,'RPM');
    xlabel(ax,'Centro del intervalo desde inicio [s]');grid(ax,'on');legend(ax,'Location','best');
    ax=subplot(2,numel(ids),k+numel(ids),'Parent',figura);hold(ax,'on');
    for par=0:1
        seleccion=evaluar & P.paridad==par;
        etiqueta='Pulsos pares';if par==1,etiqueta='Pulsos impares';end
        plot(ax,P.t_centro_intervalo_s(seleccion),error(seleccion),'o', ...
            'MarkerSize',4,'DisplayName',etiqueta);
    end
    yline(ax,0,'--','HandleVisibility','off');ylabel(ax,'Modelo menos medida [RPM]');
    xlabel(ax,'Centro del intervalo desde inicio [s]');grid(ax,'on');legend(ax,'Location','best');
    e.datos=P;ensayos{k}=e;
    writetable(P,fullfile(salida,['intervalos_' e.id '.csv']));
end
estilo_figura(figura);
writetable(resumen,fullfile(salida,'resumen.csv'));
writetable(paridad,fullfile(salida,'diagnostico_paridad.csv'));
print(figura,fullfile(salida,'comprobacion.png'),'-dpng','-r160');
savefig(figura,fullfile(salida,'comprobacion.fig'));
resultado=struct('a',a,'b',b,'fuente',fuente,'opciones',opciones, ...
    'resumen',resumen,'paridad',paridad,'ensayos',{ensayos},'salida',salida);
save(fullfile(salida,'validacion.mat'),'resultado');disp(resumen);disp(paridad);
fprintf('Ambas corridas comprueban el modelo anterior. No se ajustaron a, b ni un aporte nuevo.\n');
fprintf('La primera media fija una condicion inicial compatible y no entra en las metricas.\n');
fprintf('La paridad es diagnostica y no identifica por si sola la posicion de cada marca.\n');
fprintf('Resultados guardados en %s\n',salida);
end
