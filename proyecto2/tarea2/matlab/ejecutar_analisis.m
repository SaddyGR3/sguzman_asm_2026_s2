% Cambiar estos valores cuando lleguen el CSV y los metadatos reales.
carpeta = fileparts(mfilename('fullpath'));
archivo = fullfile(carpeta, 'ensayo_01', 'datos.csv');
t0_ms = NaN; % Instante exacto de la orden en el mismo reloj del CSV.
opciones = struct();
opciones.tipo_datos = 'experimental';
opciones.intervalo_inicial_s = [-2 -0.2];
% La ventana final debe elegirse al observar un regimen estable.
opciones.intervalo_final_s = []; % Por defecto, ultimo 20 % del tiempo posterior.
opciones.retardo_s = 0; % Hipotesis inicial. No es un retardo medido.
opciones.ajustar_modelo = false; % Primero inspeccionar las curvas.
% Activar el ajuste solo para un escalon sostenido con regimenes estables.
resultado = analizar_ensayo(archivo,t0_ms,opciones);
