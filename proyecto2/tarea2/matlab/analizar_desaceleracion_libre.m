function resultado = analizar_desaceleracion_libre(carpeta, ventanas)
% Explora si la pendiente del giro libre cambia con la velocidad.
% Incluye registro posterior al fin del ensayo solo si mantiene motor apagado
% y servo liberado. No estima un modelo ni certifica la parada.
carpetaScripts = fileparts(mfilename('fullpath'));
if nargin < 1
    carpeta = fullfile(carpetaScripts, '..', 'capturas', 'escritorio', 'reales', ...
        '20261127_200435_402416');
end
if nargin < 2, ventanas = [0.5 2.5; 8.5 10.5; 15.5 17.5]; end
assert(size(ventanas, 2) == 2 && all(isfinite(ventanas(:))) && ...
    all(ventanas(:, 1) >= 0 & ventanas(:, 2) > ventanas(:, 1)), 'Ventanas no validas');
D = readtable(fullfile(carpeta, 'diagnostico_1.csv'), 'TextType', 'string');
E = readtable(fullfile(carpeta, 'eventos_1.csv'), 'TextType', 'string');
inicio = find(E.tipo == "ENSAYO_FIJO_INICIO");
assert(isscalar(inicio), 'Se requiere un unico ensayo fijo por captura');
t0 = E.tiempo_ms(inicio);
limite = max(ventanas(:, 2));
eventos = E.tiempo_ms >= t0 & E.tiempo_ms <= t0 + 1000*limite;
servo = E.valor(eventos & E.tipo == "SERVO_CMD");
assert(~isempty(servo) && all(servo == 45), 'Se requiere servo liberado a 45 grados');
assert(~any(E.tipo(eventos) == "MOTOR_CMD" & E.valor(eventos) ~= 0), ...
    'El motor se encendio en el tramo analizado');
assert(~any(startsWith(E.tipo(eventos), "FALLO_")), 'Se encontraron eventos de fallo');
filas = D.tiempo_ms >= t0 & D.tiempo_ms <= t0 + 1000*limite;
D = D(filas, :);
assert(height(D) >= 3 && all(diff(D.tiempo_ms) > 0), 'Registro insuficiente o desordenado');
assert(all(D.motor_encendido == 0) && all(D.perdidos_cola == 0), ...
    'El motor debe estar apagado y sin perdidas de cola');
assert(all(D.modo == "FIJO" | D.modo == "FINALIZADO"), 'Hay modos incompatibles con giro libre');
t = (D.tiempo_ms - t0)/1000;
rpm = D.rpm_validada;
rpm(D.estado_medicion ~= "RECIENTE" | ~isfinite(rpm)) = NaN;
assert(all(diff(t) <= 0.15), 'Faltan filas de registro en el tramo analizado');
resumen = table();
ajustes = cell(size(ventanas, 1), 1);
for k = 1:size(ventanas, 1)
    seleccion = t >= ventanas(k, 1) & t <= ventanas(k, 2);
    ts = t(seleccion); vs = rpm(seleccion);
    assert(numel(ts) >= 5 && all(isfinite(vs)), ...
        'La ventana %g a %g necesita cinco registros validos sin huecos', ventanas(k, :));
    assert(ts(1)-ventanas(k, 1) <= 0.15 && ventanas(k, 2)-ts(end) <= 0.15, ...
        'La ventana no esta suficientemente cubierta');
    coef = polyfit(ts, vs, 1);
    ajustes{k} = struct('t', ts, 'rpm', vs, 'recta_rpm', polyval(coef, ts));
    fila = table(k, ventanas(k, 1), ventanas(k, 2), ts(1), ts(end), numel(ts), ...
        mean(vs), min(vs), max(vs), coef(1), coef(1)*2*pi/60, ...
        sqrt(mean((vs-polyval(coef, ts)).^2)), ...
        'VariableNames', {'tramo', 'ventana_inicio_s', 'ventana_fin_s', ...
        'primera_muestra_s', 'ultima_muestra_s', 'registros', 'rpm_media', ...
        'rpm_minima', 'rpm_maxima', 'pendiente_rpm_s', 'aceleracion_rad_s2', 'error_recta_rpm'});
    resumen = [resumen; fila]; %#ok<AGROW>
end
figura = figure('Name', 'Desaceleracion natural en tres tramos', 'Color', 'w', ...
    'Position', [100 100 1100 650]);
ax = axes(figura, 'Position', [0.10 0.22 0.85 0.67]);
plot(ax, t, rpm, 'Color', [0.60 0.65 0.69], 'LineWidth', 2, ...
    'DisplayName', 'Giro libre registrado');
hold(ax, 'on');
colores = [0 0.55 0.48; 0.20 0.40 0.90; 0.70 0.30 0.65];
for k = 1:numel(ajustes)
    a = ajustes{k};
    plot(ax, a.t, a.rpm, 'o', 'Color', colores(mod(k-1, 3)+1, :), 'MarkerSize', 5, ...
        'DisplayName', sprintf('Tramo %g a %g s', ventanas(k, :)));
    plot(ax, a.t, a.recta_rpm, '--', 'Color', [0.18 0.22 0.27], ...
        'LineWidth', 1.8, 'HandleVisibility', 'off');
    text(ax, mean(a.t), mean(a.rpm)+75, ...
        sprintf('%.1f RPM/s', resumen.pendiente_rpm_s(k)), ...
        'HorizontalAlignment', 'center', 'FontSize', 11);
end
fin = E.tiempo_ms(startsWith(E.tipo, "ENSAYO_FIN_DURACION") & E.tiempo_ms > t0);
assert(isscalar(fin), 'Se requiere un unico final por duracion');
xline(ax, (fin-t0)/1000, ':', 'Fin del ensayo, registro continua', ...
    'HandleVisibility', 'off', 'LabelHorizontalAlignment', 'left');
grid(ax, 'on');
xlim(ax, [0 limite]);
ylim(ax, [0 1.1*max(rpm(isfinite(rpm)))]);
xlabel(ax, 'Tiempo desde el inicio del ensayo [s]');
ylabel(ax, 'Velocidad medida [RPM]');
title(ax, 'Desaceleracion natural a distintas velocidades del mismo giro libre');
legend(ax, 'Location', 'northeast');
annotation(figura, 'textbox', [0.10 0.03 0.85 0.12], ...
    'String', sprintf(['Motor apagado y orden del servo a 45 grados durante todo el tramo analizado.\n' ...
    'Puntos coloreados y rectas discontinuas dentro de ventanas de igual duracion.\n' ...
    'Una sola corrida, sin ajuste de modelo ni conclusiones estadisticas. Las RPM son estimaciones entre marcas.']), ...
    'EdgeColor', 'none', 'FontSize', 10, 'Interpreter', 'none', 'Color', [0.12 0.16 0.20]);
estilo_figura(figura);
[~, id] = fileparts(carpeta);
salida = fullfile(carpetaScripts, 'resultados_reales', ['desaceleracion_libre_' id]);
if ~isfolder(salida), mkdir(salida); end
writetable(resumen, fullfile(salida, 'tramos.csv'));
print(figura, fullfile(salida, 'tramos.png'), '-dpng', '-r160');
savefig(figura, fullfile(salida, 'tramos.fig'));
resultado = struct('carpeta', carpeta, 'ventanas', ventanas, 't', t, 'rpm', rpm, ...
    'ajustes', {ajustes}, 'resumen', resumen, 'salida', salida);
save(fullfile(salida, 'tramos.mat'), 'resultado');
disp(resumen(:, {'ventana_inicio_s', 'ventana_fin_s', 'rpm_media', 'pendiente_rpm_s'}));
fprintf('Se incluye registro posterior al final de los seis segundos, con motor apagado y servo a 45 grados.\n');
fprintf('Los registros repetidos no son medidas independientes. No se identifica un modelo con esta tabla.\n');
fprintf('Resultados guardados en %s\n', salida);
end
