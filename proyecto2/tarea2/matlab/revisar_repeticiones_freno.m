function resultado = revisar_repeticiones_freno(intervalos)
% Diagnostico posterior. No modifica el modelo comun ni sus metricas reservadas.
% Estimar c en la tercera corrida usa sus datos y NO es validacion independiente.
carpetaScripts=fileparts(mfilename('fullpath'));
if nargin < 1 || isempty(intervalos)
    archivo=load(fullfile(carpetaScripts,'resultados_reales', ...
        'freno30_intervalos_20261127_212109_143576','modelo.mat'),'resultado');
    intervalos=archivo.resultado;
end
a=intervalos.a;b=intervalos.b;cComun=intervalos.c30;
resumen=table();diagnosticos=cell(numel(intervalos.predicciones),1);
for k=1:numel(intervalos.predicciones)
    P=intervalos.predicciones{k};
    T=P.periodo_s;final=P.t_fin_intervalo_s-P.t_fin_intervalo_s(1);
    F=exp(-b*final).*expm1(b*T)./(b*T);razon=F/F(1);
    q=(1-razon)/b;base=P.rpm_validada(1)*razon-a*q;
    cIndividual=sum(q.*(base-P.rpm_validada))/sum(q.^2);
    assert(isfinite(cIndividual) && cIndividual>=0,'Estimacion individual no valida');
    pred=base-cIndividual*q;error=pred-P.rpm_validada;
    evaluar=P.usado_en_metricas;
    % Usar los mismos intervalos y operador de observacion del modelo comun.
    assert(max(abs(base-cComun*q-P.rpm_modelo_media))<1e-6,'Modelo comun incoherente');
    fila=table(intervalos.metricas.captura(k),intervalos.metricas.uso(k),cIndividual, ...
        100*(cIndividual-cComun)/cComun,mean(abs(P.error_media_rpm(evaluar))), ...
        mean(abs(error(evaluar))),max(abs(error(evaluar))), ...
        'VariableNames',{'captura','uso_original','c30_diagnostico_rpm_s', ...
        'diferencia_respecto_comun_porcentaje','mae_comun_rpm', ...
        'mae_ajuste_individual_rpm','max_ajuste_individual_rpm'});
    resumen=[resumen;fila]; %#ok<AGROW>
    diagnosticos{k}=table(P.t_centro_intervalo_s,P.rpm_validada,pred,error,evaluar, ...
        'VariableNames',{'centro_intervalo_s','rpm_medida','rpm_ajuste_individual', ...
        'error_individual_rpm','usado_en_metricas'});
end
figura=figure('Name','Diagnostico de las repeticiones de frenado','Color','w', ...
    'Position',[100 100 1100 760]);
ax=axes(figura,'Position',[0.10 0.55 0.85 0.34]);
bar(ax,resumen.c30_diagnostico_rpm_s,0.55,'FaceColor',[0.30 0.50 0.75]);
hold(ax,'on');yline(ax,cComun,'--','Modelo comun','LineWidth',1.4);
xticks(ax,1:height(resumen));xticklabels(ax,compose('Corrida %d',1:height(resumen)));
ylim(ax,[0 600]);grid(ax,'on');
ylabel(ax,'Aporte c30 [RPM/s]');
title(ax,'Un aporte estimado por corrida, solo como diagnostico');
for k=1:height(resumen)
    text(ax,k,resumen.c30_diagnostico_rpm_s(k)+16, ...
        sprintf('%.1f RPM/s',resumen.c30_diagnostico_rpm_s(k)), ...
        'HorizontalAlignment','center','FontSize',11);
end
axError=axes(figura,'Position',[0.10 0.25 0.85 0.21]);
colores=[0 0.55 0.48;0.88 0.34 0.13;0.55 0.25 0.72];
hold(axError,'on');
for k=1:numel(diagnosticos)
    D=diagnosticos{k};usar=D.usado_en_metricas;
    plot(axError,D.centro_intervalo_s(usar),D.error_individual_rpm(usar),'o-', ...
        'Color',colores(mod(k-1,3)+1,:),'LineWidth',1.3,'MarkerSize',4, ...
        'DisplayName',sprintf('Corrida %d',k));
end
yline(axError,0,':','HandleVisibility','off');grid(axError,'on');
xlabel(axError,'Centro del intervalo medido desde el inicio del ensayo [s]');
ylabel(axError,'Error individual [RPM]');
legend(axError,'Location','southwest');
annotation(figura,'textbox',[0.10 0.025 0.85 0.15], ...
    'String',sprintf(['El modelo comun c30 = %.1f RPM/s se conserva intacto.\n' ...
    'La estimacion individual de la tercera corrida es un diagnostico posterior, no validacion independiente.\n' ...
    'Las tres conservan una curvatura residual parecida. La ecuacion constante sigue siendo aproximada.\n' ...
    'No se identifica la causa mecanica ni se demuestra que el freno cambie solo con la velocidad.'],cComun), ...
    'EdgeColor','none','FontSize',10,'Color',[0.12 0.16 0.20],'Interpreter','none');
estilo_figura(figura);
salida=fullfile(intervalos.salida,'diagnostico_repeticiones');
if ~isfolder(salida),mkdir(salida);end
writetable(resumen,fullfile(salida,'resumen.csv'));
for k=1:numel(diagnosticos)
    writetable(diagnosticos{k},fullfile(salida,['diagnostico_' char(resumen.captura(k)) '.csv']));
end
print(figura,fullfile(salida,'diagnostico.png'),'-dpng','-r160');
savefig(figura,fullfile(salida,'diagnostico.fig'));
resultado=struct('cComun',cComun,'resumen',resumen,'diagnosticos',{diagnosticos},'salida',salida);
save(fullfile(salida,'diagnostico.mat'),'resultado');
disp(resumen);
fprintf('Los ajustes individuales son descriptivos y usan todos los puntos de su propia corrida.\n');
fprintf('No sustituyen los parametros ni las metricas de la comprobacion reservada anterior.\n');
fprintf('Resultados guardados en %s\n',salida);
end
