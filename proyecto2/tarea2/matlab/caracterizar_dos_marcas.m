function resultado = caracterizar_dos_marcas
% Primeras tres condiciones con dos marcas, una corrida por angulo.
% Mantiene el modelo libre anterior para comparar, sin reidentificarlo.
carpeta=fileparts(mfilename('fullpath'));
raiz=fullfile(carpeta,'..','capturas','escritorio','reales');
angulos=[26 27 28];
ids={'20261128_010110_023010','20261128_010024_258929','20261128_005740_418983'};
grupos=struct('angulo',{},'capturas',{});
for k=1:numel(angulos)
    grupos(k)=struct('angulo',angulos(k),'capturas',{{fullfile(raiz,ids{k})}});
end
opciones=struct('permitirParciales',false,'permitirExploratorios',true, ...
    'marcasPorVuelta',2,'salida', ...
    fullfile(carpeta,'resultados_reales','primeras_pruebas_dos_marcas'));
resultado=caracterizar_angulos_freno(grupos,opciones);
fprintf('Son tres condiciones con una corrida cada una, no tres repeticiones por condicion.\n');
fprintf('El modelo libre procede de una marca y sigue siendo una referencia anterior.\n');
fprintf('Final por duracion y posible parada sin pulsos no fijan el instante de detencion.\n');
end
