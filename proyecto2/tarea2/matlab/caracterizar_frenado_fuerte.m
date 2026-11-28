function resultado = caracterizar_frenado_fuerte
% Estimaciones exploratorias de tramos previos a fallos de medicion.
% No convierte los finales en paradas medidas ni valida el ensayo completo.
carpeta=fileparts(mfilename('fullpath'));
raiz=fullfile(carpeta,'..','capturas','escritorio','reales');
angulos=[25 26 27];
ids={ ...
    {'20261127_235851_459064'}, ...
    {'20261127_235944_106032','20261128_000037_647391'}, ...
    {'20261128_000124_438590'}};
grupos=struct('angulo',{},'capturas',{});
for k=1:numel(angulos)
    rutas=cellfun(@(id) fullfile(raiz,id),ids{k},'UniformOutput',false);
    grupos(k)=struct('angulo',angulos(k),'capturas',{rutas});
end
opciones=struct('permitirParciales',true,'permitirExploratorios',true, ...
    'salida',fullfile(carpeta,'resultados_reales','frenado_fuerte_25_26_27'));
resultado=caracterizar_angulos_freno(grupos,opciones);
fprintf('Todos son tramos de ensayos con FALLO_MEDICION. No hay comprobacion reservada.\n');
fprintf('El rango de trabajo comunicado es de 45 a 25 grados. 26 es frenado fuerte.\n');
fprintf('Las estimaciones no fijan el tiempo de parada ni sustituyen pruebas completas.\n');
end
