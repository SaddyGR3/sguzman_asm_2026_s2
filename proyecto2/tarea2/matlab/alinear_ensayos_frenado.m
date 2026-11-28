function resultado = alinear_ensayos_frenado(configuracion, salida)
% Alinea capturas completas sin ajustar un modelo ni alterar las velocidades.
% Cada elemento de configuracion necesita carpeta, nombre y angulo.
% Permite agregar repeticiones sin cambiar el analizador.
carpetaScripts = fileparts(mfilename('fullpath'));
if nargin < 1 || isempty(configuracion)
    raiz = fullfile(carpetaScripts, '..', 'capturas', 'escritorio', 'reales');
    ids = {'20261127_200435_402416', '20261127_200152_802180', '20261127_200642_850954'};
    nombres = {'Giro libre a 45 grados', 'Freno a 30 grados - corrida 1', 'Freno a 30 grados - corrida 2'};
    angulos = [45 30 30];
    configuracion = struct('carpeta', {}, 'nombre', {}, 'angulo', {});
    for k = 1:numel(ids)
        configuracion(k) = struct('carpeta', fullfile(raiz, ids{k}), ...
            'nombre', nombres{k}, 'angulo', angulos(k));
    end
end
if nargin < 2
    salida = fullfile(carpetaScripts, 'resultados_reales', 'alineacion_montaje_reorganizado');
end
assert(~isempty(configuracion), 'Seleccione al menos una captura');
ensayos = cell(numel(configuracion), 1);
resumen = table();
for k = 1:numel(configuracion)
    ensayos{k} = leer_ensayo(configuracion(k));
    e = ensayos{k};
    fila = table(string(e.nombre), string(e.id), e.angulo, e.inicioMs / 1000, ...
        e.rpmInicial, e.duracion, height(e.datos), nnz(isfinite(e.datos.rpm_grafica)), ...
        max(abs(e.datos.t_alineado_s - e.datos.t_ensayo_s)), ...
        'VariableNames', {'condicion', 'captura', 'servo_grados', 'inicio_original_s', ...
        'rpm_inicial', 'duracion_s', 'registros', 'registros_validos', 'desfase_maximo_campos_s'});
    resumen = [resumen; fila]; %#ok<AGROW>
end

figura = figure('Name', 'Curvas alineadas del montaje reorganizado', ...
    'Color', 'w', 'Position', [100 100 1100 650]);
ax = axes(figura, 'Position', [0.09 0.21 0.87 0.68]);
hold(ax, 'on');
colores = [0 0.55 0.48; 0.88 0.34 0.13; 0.55 0.25 0.72];
estilos = {'-', '-', '-.'};
for k = 1:numel(ensayos)
    e = ensayos{k};
    plot(ax, e.datos.t_alineado_s, e.datos.rpm_grafica, ...
        'Color', colores(mod(k-1, size(colores, 1))+1, :), ...
        'LineStyle', estilos{mod(k-1, numel(estilos))+1}, 'LineWidth', 2, ...
        'DisplayName', e.nombre);
end
% Una sola referencia para orientar la lectura. No se reescala ninguna medida.
% Se conserva la velocidad inicial real de cada corrida en el resumen.
referencia = find([configuracion.angulo] < 45, 1);
if isempty(referencia), referencia = 1; end
e = ensayos{referencia};
plot(ax, [0 e.duracion], [e.rpmInicial 0], '--', 'Color', [0.20 0.40 0.90], ...
    'LineWidth', 1.5, 'DisplayName', ['Referencia de ' e.nombre]);
grid(ax, 'on');
xlim(ax, [0 max(resumen.duracion_s)]);
ylim(ax, [0 1.1 * max(resumen.rpm_inicial)]);
xlabel(ax, 'Tiempo desde el inicio de cada ensayo [s]');
ylabel(ax, 'Velocidad medida [RPM]');
title(ax, 'Mismo origen temporal para giro libre y dos frenadas');
legend(ax, 'Location', 'northeast', 'Interpreter', 'none');
annotation(figura, 'textbox', [0.09 0.03 0.87 0.12], ...
    'String', sprintf(['Tiempo alineado = tiempo original - inicio de cada ensayo. Las RPM no se desplazan.\n' ...
    'Los huecos conservan mediciones invalidas. El final de una linea no confirma la parada.\n' ...
    'Giro libre y dos frenadas del montaje reorganizado. Sin ajuste de modelo.']), ...
    'EdgeColor', 'none', 'Color', [0.12 0.16 0.20], 'FontSize', 10, 'Interpreter', 'none');
estilo_figura(figura);

if ~isfolder(salida), mkdir(salida); end
for k = 1:numel(ensayos)
    e = ensayos{k};
    writetable(e.datos, fullfile(salida, ['alineada_' e.id '.csv']));
end
writetable(resumen, fullfile(salida, 'resumen_alineacion.csv'));
print(figura, fullfile(salida, 'curvas_alineadas.png'), '-dpng', '-r160');
savefig(figura, fullfile(salida, 'curvas_alineadas.fig'));
resultado = struct('configuracion', configuracion, 'ensayos', {ensayos}, ...
    'resumen', resumen, 'salida', salida);
save(fullfile(salida, 'alineacion.mat'), 'resultado');
disp(resumen);
fprintf('Solo se cambio el origen temporal. No se interpolaron ni normalizaron las RPM.\n');
fprintf('Los CSV alineados conservan el tiempo original y el tiempo de ensayo.\n');
fprintf('Resultados guardados en %s\n', salida);
end

function ensayo = leer_ensayo(configuracion)
carpeta = configuracion.carpeta;
D = readtable(fullfile(carpeta, 'diagnostico_1.csv'), 'TextType', 'string');
E = readtable(fullfile(carpeta, 'eventos_1.csv'), 'TextType', 'string');
inicio = find(E.tipo == "ENSAYO_FIJO_INICIO");
assert(isscalar(inicio), 'Se requiere un solo ensayo fijo completo en %s', carpeta);
t0 = E.tiempo_ms(inicio);
fin = find(startsWith(E.tipo, "ENSAYO_FIN_DURACION") & E.tiempo_ms > t0);
assert(isscalar(fin), 'Falta un final unico por duracion en %s', carpeta);
t1 = E.tiempo_ms(fin);
activos = E.tiempo_ms >= t0 & E.tiempo_ms < t1;
assert(~any(startsWith(E.tipo(activos), "FALLO_")), 'El ensayo contiene fallos');
ordenes = E.valor(activos & E.tipo == "SERVO_CMD");
assert(~isempty(ordenes) && all(ordenes == configuracion.angulo), ...
    'Los angulos registrados no coinciden con la configuracion de %s', carpeta);
rpmInicial = E.valor(activos & E.tipo == "RPM_INICIAL_X100") / 100;
duracion = E.valor(activos & E.tipo == "ENSAYO_DURACION_MS") / 1000;
assert(isscalar(rpmInicial) && isfinite(rpmInicial) && rpmInicial > 0 && ...
    isscalar(duracion) && isfinite(duracion) && duracion > 0, 'Metadatos incompletos');
filas = D.modo == "FIJO" & D.tiempo_ms >= t0 & D.tiempo_ms < t1;
D = D(filas, :);
assert(height(D) >= 3 && all(diff(D.tiempo_ms) > 0), 'Registros insuficientes o desordenados');
assert(all(D.motor_encendido == 0), 'El motor no estuvo apagado durante todo el ensayo');
assert(all(D.perdidos_cola == 0), 'La captura perdio pulsos de la cola');
% Esta resta es toda la alineacion. No se usa la hora de recepcion de la PC.
tAlineado = (D.tiempo_ms - t0) / 1000;
tEnsayo = D.tiempo_ensayo_ms / 1000;
assert(all(tAlineado >= 0 & tAlineado <= duracion + 0.002), 'Tiempos fuera del ensayo');
% El tiempo de ensayo se imprime despues del tiempo de captura. En estas
% corridas difieren hasta 11 ms por lecturas separadas e impresion serial.
assert(all(abs(tAlineado - tEnsayo) <= 0.020), ...
    'Los campos de tiempo difieren mas de 20 ms. Revise el registro');
assert(abs((t1-t0)/1000 - duracion) <= 0.1, 'El final no coincide con la duracion');
rpmGrafica = D.rpm_validada;
rpmGrafica(D.estado_medicion ~= "RECIENTE" | ~isfinite(rpmGrafica)) = NaN;
assert(any(isfinite(rpmGrafica)), 'No hay velocidades validas');
% No unir filas separadas por una perdida del registro nominal de 10 Hz.
huecos = find(diff(tAlineado) > 0.15);
n = height(D);
tabla = table(D.tiempo_ms, repmat(t0, n, 1), tAlineado, tEnsayo, ...
    D.rpm_validada, rpmGrafica, D.estado_medicion, D.referencia_rpm, ...
    'VariableNames', {'tiempo_original_ms', 'inicio_ensayo_ms', 't_alineado_s', ...
    't_ensayo_s', 'rpm_validada', 'rpm_grafica', 'estado_medicion', 'referencia_rpm'});
assert(isempty(huecos), ...
    'Faltan filas de registro. Revise los huecos temporales antes de alinear %s', carpeta);
[~, id] = fileparts(carpeta);
ensayo = struct('id', id, 'nombre', configuracion.nombre, 'angulo', configuracion.angulo, ...
    'inicioMs', t0, 'rpmInicial', rpmInicial, 'duracion', duracion, 'datos', tabla);
end
