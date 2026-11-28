function resultado = modelar_frenado_30(libre, carpetasAjuste, carpetaValidacion, ventana)
% Prueba dn/dt = -a-b*n-c30, manteniendo a y b del giro libre.
% Un unico c30 se ajusta con dos frenadas. La tercera queda reservada.
% Solo orden fija de 30 grados y el tramo seleccionado, sin modelar parada.
carpetaScripts = fileparts(mfilename('fullpath'));
raiz = fullfile(carpetaScripts, '..', 'capturas', 'escritorio', 'reales');
if nargin < 1 || isempty(libre)
    ruta = fullfile(carpetaScripts, 'resultados_reales', ...
        'modelo_libre_20261127_210612_886523', 'modelo.mat');
    assert(isfile(ruta), 'Ejecute primero modelar_giro_libre');
    archivo = load(ruta, 'resultado'); libre = archivo.resultado;
end
if nargin < 2
    carpetasAjuste = {fullfile(raiz, '20261127_211944_350811'), ...
        fullfile(raiz, '20261127_212026_949598')};
end
if nargin < 3, carpetaValidacion = fullfile(raiz, '20261127_212109_143576'); end
if nargin < 4, ventana = [0.5 2.0]; end
assert(numel(ventana) == 2 && all(isfinite(ventana)) && ...
    ventana(1) >= 0 && ventana(2) > ventana(1), 'Ventana no valida');
a = libre.a; b = libre.b;
assert(isfinite(a) && a >= 0 && isfinite(b) && b > 0, 'Modelo libre no valido');
carpetasAjuste = cellstr(string(carpetasAjuste));
assert(numel(carpetasAjuste) >= 2, 'Se necesitan dos capturas de ajuste');
ajuste = cell(numel(carpetasAjuste), 1);
for k = 1:numel(ajuste), ajuste{k} = leer_frenada(carpetasAjuste{k}, ventana); end
validacion = leer_frenada(carpetaValidacion, ventana);
ids = cellfun(@(e) string(e.id), ajuste);
assert(numel(unique(ids)) == numel(ids) && ~any(ids == string(validacion.id)), ...
    'La captura reservada no puede usarse tambien para ajustar');
% La solucion temporal es lineal en c30. Su minimo de errores cuadrados
% puede calcularse sin optimizador ni derivar los escalones de la medicion.
numerador = 0; denominador = 0;
for k = 1:numel(ajuste)
    e = ajuste{k};
    q = -expm1(-b*e.tModelo)/b;
    predLibre = e.rpm(1)*exp(-b*e.tModelo)-a*q;
    numerador = numerador + sum(q.*(predLibre-e.rpm));
    denominador = denominador + sum(q.^2);
end
assert(denominador > 0, 'No hay suficiente intervalo para ajustar');
c30 = numerador/denominador;
assert(isfinite(c30) && c30 >= 0, 'La hipotesis requiere una contribucion de freno no negativa');
ensayos = [ajuste; {validacion}];
metricas = table(); predicciones = cell(numel(ensayos), 1);
for k = 1:numel(ensayos)
    e = ensayos{k};
    q = -expm1(-b*e.tModelo)/b;
    sinFreno = e.rpm(1)*exp(-b*e.tModelo)-a*q;
    pred = sinFreno-c30*q;
    assert(all(isfinite(pred)) && all(pred > 0), 'La prediccion sale del rango positivo');
    error = pred-e.rpm;
    evaluar = e.tModelo > 0;
    uso = "Ajuste";
    if k == numel(ensayos), uso = "Validacion reservada"; end
    fila = table(string(e.id), uso, nnz(evaluar), e.rpm(1), e.t(1), e.t(end), ...
        sqrt(mean(error(evaluar).^2)), mean(abs(error(evaluar))), max(abs(error(evaluar))), ...
        mean(error(evaluar)), ...
        'VariableNames', {'captura', 'uso', 'registros_evaluados', 'rpm_inicial_del_tramo', ...
        'primera_muestra_s', 'ultima_muestra_s', 'rmse_rpm', 'mae_rpm', 'max_error_rpm', 'error_medio_rpm'});
    metricas = [metricas; fila]; %#ok<AGROW>
    predicciones{k} = table(e.t, e.tModelo, e.rpm, pred, sinFreno, error, evaluar, ...
        'VariableNames', {'tiempo_ensayo_s', 'tiempo_desde_condicion_inicial_s', ...
        'rpm_medida', 'rpm_modelo_30', 'rpm_modelo_libre', 'error_rpm', 'usado_en_metricas'});
end
figura = figure('Name', 'Comprobacion del modelo de freno fijo a 30 grados', ...
    'Color', 'w', 'Position', [100 100 1100 720]);
P = predicciones{end};
ax = axes(figura, 'Position', [0.10 0.48 0.85 0.42]);
plot(ax, P.tiempo_ensayo_s, P.rpm_medida, 'o-', 'Color', [0 0.55 0.48], ...
    'LineWidth', 1.5, 'MarkerSize', 5, 'DisplayName', 'Tercera frenada medida');
hold(ax, 'on');
plot(ax, P.tiempo_ensayo_s, P.rpm_modelo_30, '--', 'Color', [0.88 0.34 0.13], ...
    'LineWidth', 2, 'DisplayName', 'Prediccion con c30 constante');
grid(ax, 'on'); xlim(ax, ventana); ylim(ax, [0 1200]);
ylabel(ax, 'Velocidad [RPM]');
title(ax, 'Modelo ajustado con dos frenadas y comprobado con la tercera');
legend(ax, 'Location', 'northeast');
axError = axes(figura, 'Position', [0.10 0.23 0.85 0.17]);
plot(axError, P.tiempo_ensayo_s, P.error_rpm, 'o-', 'Color', [0.55 0.25 0.72], ...
    'LineWidth', 1.4, 'MarkerSize', 4);
yline(axError, 0, ':', 'HandleVisibility', 'off');
grid(axError, 'on'); xlim(axError, ventana);
xlabel(axError, 'Tiempo desde el inicio del ensayo [s]');
ylabel(axError, 'Prediccion - medida [RPM]');
annotation(figura, 'textbox', [0.10 0.025 0.85 0.14], ...
    'String', sprintf(['dn/dt = -%.3f - %.5f n - %.3f   con n en RPM y t en segundos.\n' ...
    'Corrida reservada   error absoluto medio %.2f RPM   error maximo %.2f RPM.\n' ...
    'El modelo libre permanece fijo. La primera medida del tramo fija la condicion inicial.\n' ...
    'Hipotesis exploratoria para 30 grados. No generaliza a otros angulos ni confirma la parada.'], ...
    a, b, c30, metricas.mae_rpm(end), metricas.max_error_rpm(end)), ...
    'EdgeColor', 'none', 'FontSize', 10, 'Interpreter', 'none', 'Color', [0.12 0.16 0.20]);
estilo_figura(figura);
salida = fullfile(carpetaScripts, 'resultados_reales', ['modelo_freno30_' validacion.id]);
if ~isfolder(salida), mkdir(salida); end
parametros = table(a, b, c30, c30*2*pi/60, ventana(1), ventana(2), ...
    'VariableNames', {'a_libre_rpm_s', 'b_libre_inverso_s', 'c30_rpm_s', 'c30_rad_s2', ...
    'ventana_inicio_s', 'ventana_fin_s'});
writetable(parametros, fullfile(salida, 'parametros.csv'));
writetable(metricas, fullfile(salida, 'metricas.csv'));
for k = 1:numel(ensayos)
    writetable(predicciones{k}, fullfile(salida, ['prediccion_' ensayos{k}.id '.csv']));
end
print(figura, fullfile(salida, 'validacion.png'), '-dpng', '-r160');
savefig(figura, fullfile(salida, 'validacion.fig'));
resultado = struct('a', a, 'b', b, 'c30', c30, 'ventana', ventana, 'ajuste', {ajuste}, ...
    'validacion', validacion, 'metricas', metricas, 'parametros', parametros, ...
    'predicciones', {predicciones}, 'salida', salida);
save(fullfile(salida, 'modelo.mat'), 'resultado');
disp(parametros); disp(metricas);
fprintf('Solo c30 se ajusto. La tercera frenada no intervino en ese calculo.\n');
fprintf('Las metricas excluyen la primera medida impuesta como condicion inicial.\n');
fprintf('Revise tambien el patron del error. Una curva visualmente cercana no valida el modelo.\n');
fprintf('Resultados guardados en %s\n', salida);
end

function e = leer_frenada(carpeta, ventana)
D = readtable(fullfile(carpeta, 'diagnostico_1.csv'), 'TextType', 'string');
E = readtable(fullfile(carpeta, 'eventos_1.csv'), 'TextType', 'string');
inicio = find(E.tipo == "ENSAYO_FIJO_INICIO");
assert(isscalar(inicio), 'Se requiere un solo ensayo fijo');
t0 = E.tiempo_ms(inicio);
fin = find(startsWith(E.tipo, "ENSAYO_FIN_DURACION") & E.tiempo_ms > t0);
assert(isscalar(fin) && (E.tiempo_ms(fin)-t0)/1000 >= ventana(2), 'Ensayo incompleto');
activos = E.tiempo_ms >= t0 & E.tiempo_ms < E.tiempo_ms(fin);
% La liberacion terminal puede imprimirse un milisegundo antes del evento
% de fin. Para el modelo se comprueba la orden hasta el final de la ventana.
enVentana = activos & E.tiempo_ms <= t0 + 1000*ventana(2);
servo = E.valor(enVentana & E.tipo == "SERVO_CMD");
assert(~isempty(servo) && all(servo == 30), 'La orden debe mantenerse en 30 grados en la ventana');
assert(~any(E.tipo(activos) == "MOTOR_CMD" & E.valor(activos) ~= 0), 'El motor debe estar apagado');
assert(~any(startsWith(E.tipo(activos), "FALLO_")), 'El ensayo contiene fallos');
filas = D.modo == "FIJO" & D.tiempo_ms >= t0 & D.tiempo_ms < E.tiempo_ms(fin);
D = D(filas, :); t = (D.tiempo_ms-t0)/1000;
assert(all(D.motor_encendido == 0) && all(D.perdidos_cola == 0), 'Motor o cola no validos');
seleccion = t >= ventana(1) & t <= ventana(2);
t = t(seleccion); D = D(seleccion, :);
assert(numel(t) >= 10 && all(diff(t) > 0 & diff(t) <= 0.15), 'Registro insuficiente o con huecos');
assert(all(D.estado_medicion == "RECIENTE" & isfinite(D.rpm_validada)), 'Hay medidas invalidas en la ventana');
assert(t(1)-ventana(1) <= 0.15 && ventana(2)-t(end) <= 0.15, 'Ventana no cubierta');
[~, id] = fileparts(carpeta);
e = struct('id', id, 'carpeta', carpeta, 't', t, 'tModelo', t-t(1), 'rpm', D.rpm_validada);
end
