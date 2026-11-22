% EJEMPLO SIMULADO. No corresponde a la maqueta ni a resultados de laboratorio.
carpeta = fileparts(mfilename('fullpath'));
salida = fullfile(carpeta, 'ejemplo_SIMULADO');
if ~isfolder(salida), mkdir(salida); end
rng(42);
tiempo_ms = (0:50:10000)';
t0_ms = 3000;
t = (tiempo_ms-t0_ms)/1000;
servo_cmd_deg = 90*ones(size(t));
servo_cmd_deg(t >= 0) = 70;
% Valores inventados para comprobar el flujo y las unidades.
K = 0.6; tau = 0.7; L = 0.15; w0 = 25;
omega = w0 + K*(-20)*(1-exp(-max(t-L,0)/tau));
omega = omega + 0.03*randn(size(t));
rpm = omega*60/(2*pi);
archivo = fullfile(salida,'datos_SIMULADOS.csv');
writetable(table(tiempo_ms,rpm,servo_cmd_deg),archivo);
opciones = struct('tipo_datos','simulado','ajustar_modelo',true, ...
    'intervalo_inicial_s',[-2 -0.2],'intervalo_final_s',[5 7], ...
    'retardo_s',L,'salida',fullfile(salida,'analisis_SIMULADO'));
resultado = analizar_ensayo(archivo,t0_ms,opciones);
assert(resultado.modelo_estimado, 'No se obtuvo el modelo del ejemplo.');
assert(abs(resultado.K_rad_s_por_grado-K) < 0.03, 'Revisar ganancia.');
assert(abs(resultado.tau_s-tau) < 0.08, 'Revisar constante de tiempo.');
assert(resultado.RMSE_rad_s < 0.10, 'Revisar error del ejemplo.');
fprintf('Comprobacion SIMULADA completada. Falta validar con mediciones reales.\n');
