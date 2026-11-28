function resultado = comparar_giro_y_freno(carpetaLibre, carpetaFreno)
% Compara dos ensayos automaticos con datos originales, sin rellenar huecos.
% Ejecutar comparar_giro_y_freno para usar las capturas del 27 de noviembre.
% Se pueden pasar otras dos carpetas, primero libre y despues frenada.
% No necesita Control System Toolbox. No identifica un modelo de la planta.

carpetaScripts = fileparts(mfilename('fullpath'));
raiz = fullfile(carpetaScripts, '..', 'capturas', 'escritorio', 'reales');
if nargin < 1
    carpetaLibre = fullfile(raiz, '20261127_190400_799594');
end
if nargin < 2
    carpetaFreno = fullfile(raiz, '20261127_185956_618751');
end
libre = leer_captura(carpetaLibre, 'Libre', 45);
freno = leer_captura(carpetaFreno, 'Freno fijo', 30);
ventana = [0.5 2.5]; % La misma ventana para las dos pendientes medias.
resumen = [resumir(libre, ventana); resumir(freno, ventana)];

figura = figure('Name', 'Giro libre y frenado fijo', 'Color', 'w', ...
    'Position', [100 100 1050 640]);
ax = axes(figura, 'Position', [0.10 0.22 0.85 0.68]);
hold(ax, 'on');
plot(ax, libre.t, libre.rpm, 'Color', [0 0.55 0.48], 'LineWidth', 2, ...
    'DisplayName', 'Libre a 45 grados');
plot(ax, freno.t, freno.rpm, 'Color', [0.88 0.34 0.13], 'LineWidth', 2, ...
    'DisplayName', 'Freno fijo a 30 grados');
% La referencia mostrada corresponde al ensayo frenado. Su valor inicial es
% ligeramente distinto del ensayo libre. Ambas RPM se conservan en la tabla.
plot(ax, [0 freno.duracion], [freno.rpmInicial 0], '--', ...
    'Color', [0.20 0.40 0.90], 'LineWidth', 1.8, ...
    'DisplayName', 'Referencia del ensayo frenado');
if isfinite(freno.tPosibleParada)
    xline(ax, freno.tPosibleParada, ':', 'Posible parada sin pulsos', ...
        'Color', [0.55 0.32 0.16], 'HandleVisibility', 'off', ...
        'LabelHorizontalAlignment', 'left');
end
grid(ax, 'on');
xlim(ax, [0 max(libre.duracion, freno.duracion)]);
ylim(ax, [0 1.10 * max(libre.rpmInicial, freno.rpmInicial)]);
xlabel(ax, 'Tiempo desde el inicio de cada ensayo [s]');
ylabel(ax, 'Velocidad medida [RPM]');
title(ax, 'Giro libre frente a frenado fijo desde aproximadamente 1300 RPM');
legend(ax, 'Location', 'northeast');
anotacion = sprintf(['Las RPM invalidas se conservan como huecos. No se dibuja un cero medido.\n' ...
    'Pendiente media entre %.1f y %.1f s   libre %.1f RPM/s   freno %.1f RPM/s\n' ...
    'Una corrida por condicion. Comparacion exploratoria, sin modelo identificado.'], ...
    ventana(1), ventana(2), resumen.pendiente_rpm_s(1), resumen.pendiente_rpm_s(2));
annotation(figura, 'textbox', [0.10 0.03 0.85 0.12], 'String', anotacion, ...
    'EdgeColor', 'none', 'FontSize', 10, 'Interpreter', 'none', ...
    'Color', [0.12 0.16 0.20]);
estilo_figura(figura);

[~, idLibre] = fileparts(carpetaLibre);
[~, idFreno] = fileparts(carpetaFreno);
salida = fullfile(carpetaScripts, 'resultados_reales', ...
    ['comparacion_' idLibre '_' idFreno]);
if ~isfolder(salida), mkdir(salida); end
writetable(resumen, fullfile(salida, 'resumen.csv'));
print(figura, fullfile(salida, 'comparacion.png'), '-dpng', '-r160');
savefig(figura, fullfile(salida, 'comparacion.fig'));
resultado = struct('libre', libre, 'freno', freno, 'ventanaPendiente', ventana, ...
    'resumen', resumen, 'salida', salida);
save(fullfile(salida, 'comparacion.mat'), 'resultado');
disp(resumen);
fprintf('La pendiente negativa indica desaceleracion. No es una ganancia del servo.\n');
fprintf('No alcanzar 500 RPM dentro del ensayo se informa como NaN, no como cero.\n');
fprintf('La posible parada no confirma el instante fisico de detencion.\n');
fprintf('Resultados guardados en %s\n', salida);
end

function ensayo = leer_captura(carpeta, nombre, anguloEsperado)
rutaD = fullfile(carpeta, 'diagnostico_1.csv');
rutaE = fullfile(carpeta, 'eventos_1.csv');
assert(isfile(rutaD) && isfile(rutaE), ...
    'Falta diagnostico_1.csv o eventos_1.csv en %s', carpeta);
D = readtable(rutaD, 'TextType', 'string');
E = readtable(rutaE, 'TextType', 'string');
inicio = find(E.tipo == "ENSAYO_FIJO_INICIO");
assert(numel(inicio) == 1, ...
    'Se necesita exactamente un ensayo fijo por captura en %s', carpeta);
fin = find(startsWith(E.tipo, "ENSAYO_FIN_DURACION") & ...
    E.tiempo_ms > E.tiempo_ms(inicio));
assert(numel(fin) == 1 && ~any(startsWith(E.tipo, "FALLO_")), ...
    'La captura debe contener un ensayo completado sin fallos en %s', carpeta);
t0 = E.tiempo_ms(inicio);
t1 = E.tiempo_ms(fin);
activos = E.tiempo_ms >= t0 & E.tiempo_ms < t1;
ordenes = E.valor(activos & E.tipo == "SERVO_CMD");
assert(~isempty(ordenes) && all(ordenes == anguloEsperado), ...
    'La orden del servo no coincide con %g grados en %s', anguloEsperado, carpeta);
rpmInicial = E.valor(activos & E.tipo == "RPM_INICIAL_X100") / 100;
duracion = E.valor(activos & E.tipo == "ENSAYO_DURACION_MS") / 1000;
assert(isscalar(rpmInicial) && isscalar(duracion) && duracion > 0, ...
    'Faltan metadatos unicos del ensayo en %s', carpeta);
filas = D.modo == "FIJO" & D.tiempo_ms >= t0 & D.tiempo_ms < t1;
t = D.tiempo_ensayo_ms(filas) / 1000;
rpm = D.rpm_validada(filas);
valida = D.estado_medicion(filas) == "RECIENTE" & isfinite(rpm);
rpm(~valida) = NaN;
assert(numel(t) >= 3 && all(diff(t) > 0), ...
    'No hay suficientes tiempos ordenados en %s', carpeta);
assert(all(D.motor_encendido(filas) == 0), ...
    'El motor debe estar apagado durante el ensayo en %s', carpeta);
assert(all(t >= 0 & t <= duracion), 'Tiempos fuera de la duracion del ensayo');
assert(all(D.perdidos_cola(filas) == 0), 'La captura tiene perdida de pulsos en cola');
posible = E.tiempo_ms(activos & E.tipo == "FIJO_POSIBLE_PARADA_SIN_PULSOS");
tPosible = NaN;
if ~isempty(posible), tPosible = (posible(1) - t0) / 1000; end
ensayo = struct('nombre', nombre, 'carpeta', carpeta, 'angulo', anguloEsperado, ...
    'rpmInicial', rpmInicial, 'duracion', duracion, 't', t, 'rpm', rpm, ...
    'tPosibleParada', tPosible, 'eventoFinal', E.tipo(fin));
end

function fila = resumir(ensayo, ventana)
valida = find(isfinite(ensayo.rpm));
assert(~isempty(valida), 'El ensayo no contiene velocidades validas');
ultima = valida(end);
bajo500 = find(ensayo.rpm < 500, 1);
t500 = NaN;
if ~isempty(bajo500), t500 = ensayo.t(bajo500); end
tramo = ensayo.t >= ventana(1) & ensayo.t <= ventana(2);
assert(nnz(tramo) >= 3 && all(isfinite(ensayo.rpm(tramo))), ...
    'La ventana de pendiente debe contener al menos tres medidas y ningun hueco');
assert(~any(diff(ensayo.t(tramo)) > 0.15), ...
    'La ventana de pendiente contiene un salto temporal superior a 150 ms');
p = polyfit(ensayo.t(tramo), ensayo.rpm(tramo), 1);
% Regresion de velocidad frente a tiempo, sin derivar escalones muestra a muestra.
fila = table(string(ensayo.nombre), ensayo.angulo, ensayo.rpmInicial, ...
    ensayo.rpm(ultima), ensayo.t(ultima), t500, p(1), p(1)*2*pi/60, ...
    'VariableNames', {'condicion', 'servo_grados', 'rpm_inicial', ...
    'ultima_rpm_valida', 'tiempo_ultima_valida_s', 'tiempo_bajo500_s', ...
    'pendiente_rpm_s', 'aceleracion_rad_s2'});
end
