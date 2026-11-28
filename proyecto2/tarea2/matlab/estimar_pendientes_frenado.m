function resultado = estimar_pendientes_frenado(alineacion, ventana)
% Ajusta velocidad = pendiente * tiempo + intercepto en una ventana comun.
% Usa datos alineados y conserva las mediciones originales.
% No obtiene torque, una ganancia del servo ni un modelo completo.
carpetaScripts = fileparts(mfilename('fullpath'));
if nargin < 1 || isempty(alineacion)
    ruta = fullfile(carpetaScripts, 'resultados_reales', ...
        'alineacion_montaje_reorganizado', 'alineacion.mat');
    assert(isfile(ruta), 'Ejecute primero alinear_ensayos_frenado');
    archivo = load(ruta, 'resultado');
    alineacion = archivo.resultado;
end
if nargin < 2, ventana = [0.5 1.5]; end
assert(numel(ventana) == 2 && all(isfinite(ventana)) && ventana(1) < ventana(2), ...
    'La ventana debe contener inicio y final en segundos');
ensayos = alineacion.ensayos;
resumen = table();
ajustes = cell(numel(ensayos), 1);
for k = 1:numel(ensayos)
    e = ensayos{k};
    seleccion = e.datos.t_alineado_s >= ventana(1) & e.datos.t_alineado_s <= ventana(2);
    t = e.datos.t_alineado_s(seleccion);
    rpm = e.datos.rpm_grafica(seleccion);
    assert(numel(t) >= 5 && all(isfinite(rpm)), ...
        'Se requieren cinco registros validos sin huecos en la ventana de %s', e.nombre);
    assert(all(diff(t) > 0 & diff(t) <= 0.15), 'Tiempos incompatibles con registro a 10 Hz');
    assert(t(1) - ventana(1) <= 0.15 && ventana(2) - t(end) <= 0.15, ...
        'Las medidas no cubren suficientemente la ventana de %s', e.nombre);
    % polyfit con grado uno elige la recta que minimiza la suma de errores
    % verticales al cuadrado. No se derivan los escalones punto a punto.
    coef = polyfit(t, rpm, 1);
    prediccion = polyval(coef, t);
    ajustes{k} = struct('t', t, 'rpm', rpm, 'recta_rpm', prediccion, ...
        'pendiente', coef(1), 'intercepto', coef(2));
    fila = table(string(e.nombre), string(e.id), e.angulo, ventana(1), ventana(2), ...
        t(1), t(end), numel(t), coef(1), coef(1)*2*pi/60, ...
        sqrt(mean((rpm - prediccion).^2)), ...
        'VariableNames', {'condicion', 'captura', 'servo_grados', 'ventana_inicio_s', ...
        'ventana_fin_s', 'primera_muestra_s', 'ultima_muestra_s', 'registros', ...
        'pendiente_rpm_s', 'aceleracion_rad_s2', 'error_recta_rpm'});
    resumen = [resumen; fila]; %#ok<AGROW>
end
libres = resumen.servo_grados == 45;
assert(any(libres), 'Se requiere una corrida libre a 45 grados para comparar');
pendienteLibre = mean(resumen.pendiente_rpm_s(libres));
resumen.perdida_adicional_rpm_s = pendienteLibre - resumen.pendiente_rpm_s;
resumen.perdida_adicional_rpm_s(libres) = NaN;

figura = figure('Name', 'Pendientes del giro libre y frenado', 'Color', 'w', ...
    'Position', [100 100 1250 610]);
colores = [0 0.55 0.48; 0.88 0.34 0.13; 0.55 0.25 0.72];
limitesRPM = vertcat(ajustes{:});
valores = vertcat(limitesRPM.rpm);
minimo = max(0, 100 * floor(min(valores)/100));
maximo = 100 * ceil(max(valores)/100);
nColumnas = min(3, numel(ensayos));
nFilas = ceil(numel(ensayos)/nColumnas);
for k = 1:numel(ensayos)
    a = ajustes{k};
    ax = subplot(nFilas, nColumnas, k, 'Parent', figura);
    plot(ax, a.t, a.rpm, 'o', 'Color', colores(mod(k-1, 3)+1, :), ...
        'MarkerSize', 6, 'LineWidth', 1.3, 'DisplayName', 'Registros de velocidad');
    hold(ax, 'on');
    plot(ax, a.t, a.recta_rpm, '--', 'Color', [0.18 0.22 0.27], ...
        'LineWidth', 1.8, 'DisplayName', 'Recta ajustada');
    grid(ax, 'on');
    xlim(ax, ventana);
    ylim(ax, [minimo maximo]);
    xlabel(ax, 'Tiempo de ensayo [s]');
    ylabel(ax, 'Velocidad [RPM]');
    title(ax, {ensayos{k}.nombre, sprintf('Pendiente %.1f RPM/s', a.pendiente)}, ...
        'Interpreter', 'none');
    if k == 1, legend(ax, 'Location', 'southwest'); end
    % Reservar espacio para la explicacion inferior sin alterar las escalas.
    posicion = ax.Position;
    posicion(2) = 0.23 + (posicion(2)-0.11)*0.85;
    posicion(4) = posicion(4)*0.78;
    ax.Position = posicion;
end
annotation(figura, 'textbox', [0.08 0.03 0.86 0.13], ...
    'String', sprintf(['Misma ventana de %.1f a %.1f segundos y misma escala vertical. Los puntos son los registros originales.\n' ...
    'La pendiente negativa indica perdida de RPM por segundo. La recta solo describe este tramo.\n' ...
    'Los registros pueden repetir una estimacion entre marcas. No son medidas independientes ni un modelo completo.'], ...
    ventana(1), ventana(2)), 'EdgeColor', 'none', 'Color', [0.12 0.16 0.20], ...
    'FontSize', 10, 'Interpreter', 'none');
estilo_figura(figura);
salida = fullfile(alineacion.salida, sprintf('pendientes_%g_%g_s', ventana(1), ventana(2)));
if ~isfolder(salida), mkdir(salida); end
writetable(resumen, fullfile(salida, 'pendientes.csv'));
print(figura, fullfile(salida, 'pendientes.png'), '-dpng', '-r160');
savefig(figura, fullfile(salida, 'pendientes.fig'));
resultado = struct('resumen', resumen, 'ajustes', {ajustes}, ...
    'ventana', ventana, 'pendienteLibre', pendienteLibre, 'salida', salida);
save(fullfile(salida, 'pendientes.mat'), 'resultado');
disp(resumen(:, {'condicion', 'pendiente_rpm_s', 'aceleracion_rad_s2', 'perdida_adicional_rpm_s'}));
fprintf('La perdida adicional compara pendientes en el mismo tramo temporal.\n');
fprintf('Las velocidades recorridas son distintas. No aisla un torque constante del freno.\n');
fprintf('Resultados guardados en %s\n', salida);
end
