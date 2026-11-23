% Punto extra de Tarea 2: motor apagado, giro libre frente a g40.
% Copiar pares datos_*.csv y eventos_*.csv a ../capturas/ y ejecutar este
% archivo desde MATLAB. Basta una corrida libre y una frenada comparables.
carpetaScripts = fileparts(mfilename('fullpath'));
carpetaCapturas = fullfile(carpetaScripts, '..', 'capturas');
if ~isfolder(carpetaCapturas)
    carpetaCapturas = uigetdir(pwd, 'Seleccione la carpeta con los pares de CSV');
    if isequal(carpetaCapturas, 0)
        error('No se selecciono una carpeta de capturas.');
    end
end
opciones = struct();
opciones.banda_rpm = [1250 1400]; % Aceptar ordenes g40 cerca de 1300 RPM.
opciones.banda_referencia_libre_rpm = [1250 1350]; % Alinear una RPM libre comparable.
opciones.umbral_rpm = 500;
opciones.angulo_libre = 90;
opciones.angulo_freno = 40;
opciones.ids = {}; % Vacio: todos los pares. El ID es el numero tras datos_/eventos_.
opciones.salida = fullfile(carpetaScripts, 'resultados_reales');
resultado = analizar_frenado_real(carpetaCapturas, opciones);
