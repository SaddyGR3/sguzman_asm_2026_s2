function resultado = modelar_giro_libre(carpetasAjuste, carpetaValidacion, ventana)
% Modelo exploratorio de giro libre con una corrida reservada para comprobarlo.
% n en RPM y t en segundos. Modelo mixto dn/dt = -a - b*n.
% No modela el servo ni estima una funcion de transferencia del freno.
carpetaScripts = fileparts(mfilename('fullpath'));
raiz = fullfile(carpetaScripts, '..', 'capturas', 'escritorio', 'reales');
if nargin < 1
    carpetasAjuste = {fullfile(raiz, '20261127_200435_402416'), ...
        fullfile(raiz, '20261127_200805_778882')};
end
if nargin < 2, carpetaValidacion = fullfile(raiz, '20261127_210612_886523'); end
if nargin < 3, ventana = [0.5 17.5]; end
assert(numel(ventana) == 2 && all(isfinite(ventana)) && ventana(1) >= 0 && ...
    ventana(2) > ventana(1), 'Ventana no valida');
carpetasAjuste = cellstr(string(carpetasAjuste));
assert(numel(carpetasAjuste) >= 2, 'Use al menos dos capturas para ajustar');
ajuste = cell(numel(carpetasAjuste), 1);
for k = 1:numel(ajuste), ajuste{k} = leer_libre(carpetasAjuste{k}, ventana); end
validacion = leer_libre(carpetaValidacion, ventana);
ids = cellfun(@(e) string(e.id), ajuste);
assert(numel(unique(ids)) == numel(ids) && ~any(ids == string(validacion.id)), ...
    'La captura de validacion debe ser distinta de todas las de ajuste');

% Solo estas dos corridas entran en la funcion objetivo.
% Logaritmos mantienen a y b positivos. fminsearch es MATLAB base.
opciones = optimset('Display', 'off', 'TolX', 1e-10, 'TolFun', 1e-8, ...
    'MaxIter', 2000, 'MaxFunEvals', 5000);
[theta, coste, salidaOpt] = fminsearch(@(x) coste_mixto(x, ajuste), log([40 0.03]), opciones);
assert(salidaOpt > 0 && isfinite(coste), 'El ajuste no convergio');
a = exp(theta(1)); b = exp(theta(2));
% Alternativa sencilla con b igual a cero, ajustada con las mismas corridas.
numerador = 0; denominador = 0;
for k = 1:numel(ajuste)
    e = ajuste{k};
    numerador = numerador + sum(e.tModelo .* (e.rpm(1)-e.rpm));
    denominador = denominador + sum(e.tModelo.^2);
end
aConstante = max(0, numerador/denominador);

ensayos = [ajuste; {validacion}];
metricas = table();
predicciones = cell(numel(ensayos), 1);
for k = 1:numel(ensayos)
    e = ensayos{k};
    mixta = predecir(a, b, e.rpm(1), e.tModelo);
    constante = e.rpm(1) - aConstante*e.tModelo;
    assert(all(isfinite(mixta)) && all(mixta > 0), ...
        'La prediccion sale del rango positivo. No se extrapola a la parada');
    errorMixto = mixta-e.rpm;
    errorConstante = constante-e.rpm;
    evaluar = e.tModelo > 0; % Excluir el punto impuesto como condicion inicial.
    papel = "Ajuste";
    if k == numel(ensayos), papel = "Validacion reservada"; end
    fila = table(string(e.id), papel, nnz(evaluar), e.rpm(1), e.t(1), e.t(end), ...
        sqrt(mean(errorMixto(evaluar).^2)), mean(abs(errorMixto(evaluar))), ...
        max(abs(errorMixto(evaluar))), sqrt(mean(errorConstante(evaluar).^2)), ...
        'VariableNames', {'captura', 'uso', 'registros_evaluados', 'rpm_inicial_medida', ...
        'inicio_efectivo_s', 'final_efectivo_s', 'rmse_mixto_rpm', 'mae_mixto_rpm', ...
        'max_error_mixto_rpm', 'rmse_constante_rpm'});
    metricas = [metricas; fila]; %#ok<AGROW>
    predicciones{k} = table(e.t, e.tModelo, e.rpm, mixta, constante, errorMixto, evaluar, ...
        'VariableNames', {'tiempo_ensayo_s', 'tiempo_desde_condicion_inicial_s', ...
        'rpm_medida', 'rpm_modelo_mixto', 'rpm_modelo_constante', 'error_mixto_rpm', 'usado_en_metricas'});
end

figura = figure('Name', 'Modelo de giro libre en una corrida reservada', ...
    'Color', 'w', 'Position', [100 100 1100 650]);
ax = axes(figura, 'Position', [0.10 0.24 0.85 0.65]);
P = predicciones{end};
plot(ax, P.tiempo_ensayo_s, P.rpm_medida, 'Color', [0 0.55 0.48], ...
    'LineWidth', 2, 'DisplayName', 'Tercera corrida medida');
hold(ax, 'on');
plot(ax, P.tiempo_ensayo_s, P.rpm_modelo_mixto, '--', ...
    'Color', [0.68 0.25 0.65], 'LineWidth', 2, 'DisplayName', 'Modelo mixto ajustado con dos corridas');
plot(ax, P.tiempo_ensayo_s, P.rpm_modelo_constante, ':', ...
    'Color', [0.35 0.40 0.45], 'LineWidth', 2, 'DisplayName', 'Modelo de desaceleracion constante');
grid(ax, 'on');
xlabel(ax, 'Tiempo desde el inicio del ensayo [s]');
ylabel(ax, 'Velocidad [RPM]');
xlim(ax, ventana); ylim(ax, [0 1400]);
title(ax, 'Prediccion del giro libre en una captura no usada para ajustar');
legend(ax, 'Location', 'northeast');
annotation(figura, 'textbox', [0.10 0.03 0.85 0.16], ...
    'String', sprintf(['dn/dt = -%.3f - %.5f n   con n en RPM y t en segundos.\n' ...
    'Error RMS en la corrida reservada   mixto %.2f RPM   constante %.2f RPM.\n' ...
    'La primera medida del tramo fija la condicion inicial y no se incluye en el error.\n' ...
    'Solo giro libre con motor apagado y servo a 45 grados. No extrapolar a parada ni a otro montaje.'], ...
    a, b, metricas.rmse_mixto_rpm(end), metricas.rmse_constante_rpm(end)), ...
    'EdgeColor', 'none', 'Color', [0.12 0.16 0.20], 'FontSize', 10, 'Interpreter', 'none');
estilo_figura(figura);

salida = fullfile(carpetaScripts, 'resultados_reales', ['modelo_libre_' validacion.id]);
if ~isfolder(salida), mkdir(salida); end
parametros = table(a, b, a*2*pi/60, aConstante, ventana(1), ventana(2), ...
    'VariableNames', {'a_rpm_s', 'b_inverso_s', 'a_rad_s2', 'a_constante_rpm_s', ...
    'ventana_inicio_s', 'ventana_fin_s'});
writetable(parametros, fullfile(salida, 'parametros.csv'));
writetable(metricas, fullfile(salida, 'metricas.csv'));
for k = 1:numel(ensayos)
    writetable(predicciones{k}, fullfile(salida, ['prediccion_' ensayos{k}.id '.csv']));
end
print(figura, fullfile(salida, 'validacion.png'), '-dpng', '-r160');
savefig(figura, fullfile(salida, 'validacion.fig'));
resultado = struct('a', a, 'b', b, 'aConstante', aConstante, 'ventana', ventana, ...
    'ajuste', {ajuste}, 'validacion', validacion, 'metricas', metricas, ...
    'predicciones', {predicciones}, 'parametros', parametros, 'salida', salida);
save(fullfile(salida, 'modelo.mat'), 'resultado');
disp(parametros); disp(metricas);
fprintf('La tercera captura no se uso para ajustar parametros ni elegir la ventana.\n');
fprintf('La prediccion usa su primera medida como condicion inicial, sin correcciones posteriores.\n');
fprintf('No se identificaron inercia, torque, efecto del servo ni un PID.\n');
fprintf('Resultados guardados en %s\n', salida);
end

function valor = coste_mixto(theta, ensayos)
p = exp(theta);
if any(~isfinite(p)) || any(p <= 0), valor = realmax; return; end
valor = 0;
for k = 1:numel(ensayos)
    e = ensayos{k};
    estimada = predecir(p(1), p(2), e.rpm(1), e.tModelo);
    if any(~isfinite(estimada)), valor = realmax; return; end
    valor = valor + sum((estimada-e.rpm).^2);
end
end

function n = predecir(a, b, n0, t)
% Solucion de dn/dt = -a-b*n. expm1 mejora la precision para b*t pequeno.
n = n0*exp(-b*t) + a*expm1(-b*t)/b;
end

function e = leer_libre(carpeta, ventana)
D = readtable(fullfile(carpeta, 'diagnostico_1.csv'), 'TextType', 'string');
E = readtable(fullfile(carpeta, 'eventos_1.csv'), 'TextType', 'string');
inicio = find(E.tipo == "ENSAYO_FIJO_INICIO");
assert(isscalar(inicio), 'Se requiere un unico ensayo completo por captura');
t0 = E.tiempo_ms(inicio);
limite = t0 + 1000*ventana(2);
eventos = E.tiempo_ms >= t0 & E.tiempo_ms <= limite;
servo = E.valor(eventos & E.tipo == "SERVO_CMD");
assert(~isempty(servo) && all(servo == 45), 'La captura debe ser libre a 45 grados');
assert(~any(E.tipo(eventos) == "MOTOR_CMD" & E.valor(eventos) ~= 0), 'Motor encendido');
assert(~any(startsWith(E.tipo(eventos), "FALLO_")), 'La captura contiene fallos');
assert(nnz(startsWith(E.tipo, "ENSAYO_FIN_DURACION") & E.tiempo_ms > t0) == 1, ...
    'El ensayo no se completo');
filas = D.tiempo_ms >= t0 & D.tiempo_ms <= limite;
D = D(filas, :);
assert(all(D.motor_encendido == 0) && all(D.perdidos_cola == 0) && ...
    all(D.modo == "FIJO" | D.modo == "FINALIZADO"), 'Condiciones incompatibles con giro libre');
t = (D.tiempo_ms-t0)/1000;
seleccion = t >= ventana(1);
t = t(seleccion); D = D(seleccion, :);
assert(numel(t) >= 50 && all(diff(t) > 0 & diff(t) <= 0.15), 'Registro insuficiente o con huecos');
assert(all(D.estado_medicion == "RECIENTE" & isfinite(D.rpm_validada)), ...
    'La ventana contiene mediciones invalidas. No se rellenan');
assert(t(1)-ventana(1) <= 0.15 && ventana(2)-t(end) <= 0.15, 'Ventana no cubierta');
[~, id] = fileparts(carpeta);
e = struct('id', id, 'carpeta', carpeta, 't', t, 'tModelo', t-t(1), 'rpm', D.rpm_validada);
end
