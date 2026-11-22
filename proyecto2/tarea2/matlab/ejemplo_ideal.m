% EJEMPLO IDEAL SIMULADO. Todos los parametros son hipoteticos.
% El motor permanece alimentado. El servo cambia de 90 a 70 grados.
% Se supone que ese cambio aumenta el frenado. Verificarlo en la maqueta.
carpeta = fileparts(mfilename('fullpath'));
salida = fullfile(carpeta,'ejemplo_IDEAL');
if ~isfolder(salida), mkdir(salida); end
K = 0.6; % (rad/s)/grado, supuesto.
tau = 0.7; % segundos, supuesto.
w0 = 25; u0 = 90; u1 = 70;
t0_ms = 3000;
tiempo_ms = (0:50:10000)';
t = (tiempo_ms-t0_ms)/1000;
servo_cmd_deg = u0*ones(size(t));
servo_cmd_deg(t >= 0) = u1;
omega = w0 + K*(u1-u0)*(1-exp(-max(t,0)/tau));
rpm = omega*60/(2*pi);
archivo = fullfile(salida,'datos_IDEALES_SIMULADOS.csv');
writetable(table(tiempo_ms,rpm,servo_cmd_deg),archivo);
opciones = struct('tipo_datos','simulado','ajustar_modelo',true, ...
    'intervalo_inicial_s',[-2 -0.2],'intervalo_final_s',[5 7], ...
    'retardo_s',0,'salida',fullfile(salida,'analisis_SIMULADO'));
resultado = analizar_ensayo(archivo,t0_ms,opciones);
assert(resultado.modelo_estimado,'Fallo el ajuste ideal.');
assert(abs(resultado.K_rad_s_por_grado-K)<0.01,'Revisar ganancia.');
assert(abs(resultado.tau_s-tau)<0.02,'Revisar constante de tiempo.');
% La respuesta impulsiva corresponde a cambios de la orden del servo.
ti = linspace(0,7,1000)';
h = K/tau*exp(-ti/tau);
f = figure('Name','Ejemplo ideal SIMULADO','Color','w', ...
    'Position',[80 80 1100 820]);
layout = tiledlayout(f,3,1,'TileSpacing','compact','Padding','compact');
title(layout,'Ejemplo ideal de frenado - DATOS SIMULADOS', ...
    'Color',[0.12 0.16 0.20],'FontSize',16,'FontWeight','bold');
nexttile;
stairs(t,servo_cmd_deg,'Color',[0.13 0.40 0.66],'LineWidth',2.2);
grid on; xline(0,'--','Color',[0.45 0.45 0.45]);
ylabel('Orden del servo (grados)'); ylim([66 94]); xlim([-3 7]);
title('1. Orden de frenado, de 90 a 70 grados');
nexttile;
plot(t,omega,'Color',[0.09 0.48 0.34],'LineWidth',2.2);
grid on; xline(0,'--','Color',[0.45 0.45 0.45]);
yline(w0+K*(u1-u0),':','Color',[0.45 0.45 0.45]);
ylabel('Velocidad (rad/s)'); ylim([11 27]); xlim([-3 7]);
xlabel('Tiempo desde la orden (s)');
title('2. La velocidad baja de 25 a 13 rad/s');
nexttile;
plot(ti,h,'Color',[0.53 0.32 0.65],'LineWidth',2.2); grid on;
xlabel('Tiempo desde el impulso ideal (s)');
ylabel('h(t) [(rad/s)/(grado s)]'); xlim([0 7]);
title('3. Respuesta al impulso calculada del modelo');
estilo_figura(f);
exportgraphics(f,fullfile(salida,'resumen_ideal_matlab.png'),'Resolution',180);
fprintf('Modelo supuesto G(s) = 0.6 / (0.7 s + 1)\n');
fprintf('Velocidad final ideal 13 rad/s. Tau 0.7 s.\n');
fprintf('Estos valores sirven para aprender el procedimiento, no para describir la maqueta.\n');
