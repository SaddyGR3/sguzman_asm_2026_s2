% Tarea 2, puntos extra: comparación del giro libre y el frenado con g40.
% Ejecutar desde MATLAB: run('proyecto2/tarea2/analisis/analizar_capturas.m')
% Requiere MATLAB básico; la figura de impulso requiere Control System Toolbox.

clear; clc; close all;
carpeta = fileparts(mfilename('fullpath'));
capturas = fullfile(carpeta, '..', 'capturas');
salida = fullfile(carpeta, 'resultados');
if ~exist(salida, 'dir'), mkdir(salida); end

idsLibres = {'20261122_022222_989250', '20261122_022329_134136', ...
             '20261122_022428_691694'};
idsFrenadas = {'20261122_021346_890235', '20261122_021527_884972'};
libres = struct([]);
frenadas = struct([]);

for i = 1:numel(idsLibres)
    [D, E] = cargar(capturas, idsLibres{i});
    assert(all(D.servo_cmd_grados == 90), 'El servo cambió en una corrida libre.');
    apagado = tiempoEvento(E, 'MOTOR_OFF_MANUAL');
    % Elegir el primer instante posterior al apagado dentro de la banda
    % comparable a la velocidad al ordenar g40 (aprox. 1300 RPM).
    idx = find(D.tiempo_ms >= apagado & D.rpm >= 1250 & D.rpm <= 1350, 1);
    assert(~isempty(idx), 'No se encontró una referencia cercana a 1300 RPM.');
    tRef = D.tiempo_ms(idx);
    idx500 = find(D.tiempo_ms >= tRef & D.rpm < 500, 1);
    idxCero = find(D.tiempo_ms >= tRef & D.rpm == 0, 1);
    assert(~isempty(idx500) && ~isempty(idxCero), 'Corrida libre incompleta.');
    x = (D.tiempo_ms(idx:idx500) - tRef) / 1000;
    y = D.rpm(idx:idx500);
    p = polyfit(x, log(y), 1); % Ajuste local: omega(t) = omega0*exp(-k*t).
    libres(i).id = idsLibres{i};
    libres(i).D = D;
    libres(i).tRef = tRef;
    libres(i).rpmRef = D.rpm(idx);
    libres(i).t500 = (D.tiempo_ms(idx500) - tRef) / 1000;
    libres(i).tCero = (D.tiempo_ms(idxCero) - tRef) / 1000;
    libres(i).k = -p(1);
end

k = median([libres.k]); % s^-1, solamente en el tramo ~1300 a 500 RPM.
for i = 1:numel(idsFrenadas)
    [D, E] = cargar(capturas, idsFrenadas{i});
    tCmd = tiempoEvento(E, 'SERVO_CMD');
    assert(any(E.valor(strcmp(E.tipo, 'SERVO_CMD')) == 40), ...
           'El escalón de esta corrida no fue a 40 grados.');
    previo = D.rpm(D.tiempo_ms < tCmd & D.tiempo_ms >= tCmd - 500);
    assert(numel(previo) >= 3, 'Faltan RPM previas al escalón.');
    rpmRef = median(previo);
    idx500 = find(D.tiempo_ms >= tCmd & D.rpm < 500, 1);
    idxCero = find(D.tiempo_ms >= tCmd & D.rpm == 0, 1);
    assert(~isempty(idx500) && ~isempty(idxCero), 'Corrida frenada incompleta.');
    usar = find(D.tiempo_ms >= tCmd & (1:height(D))' <= idx500);
    x = (D.tiempo_ms(usar) - tCmd) / 1000;
    y = D.rpm(usar);
    % Modelo local: d(omega)/dt = -k*omega - c*u, u=1 al ordenar g40.
    % c se estima por mínimos cuadrados sin asumir torque ni fuerza conocidos.
    h = (1 - exp(-k*x)) / k;
    base = rpmRef * exp(-k*x);
    c = max(0, sum(h .* (base - y)) / sum(h.^2)); % RPM/s.
    pred = base - c*h;
    r2 = 1 - sum((y - pred).^2) / sum((y - mean(y)).^2);
    frenadas(i).id = idsFrenadas{i};
    frenadas(i).D = D;
    frenadas(i).tRef = tCmd;
    frenadas(i).rpmRef = rpmRef;
    frenadas(i).t500 = (D.tiempo_ms(idx500) - tCmd) / 1000;
    frenadas(i).tCero = (D.tiempo_ms(idxCero) - tCmd) / 1000;
    frenadas(i).c = c;
    frenadas(i).r2 = r2;
    frenadas(i).xAjuste = x;
    frenadas(i).pred = pred;
end

tipo = [repmat("libre", 3, 1); repmat("frenada", 2, 1)];
captura = string([{libres.id}, {frenadas.id}])';
rpm_referencia = [[libres.rpmRef], [frenadas.rpmRef]]';
tiempo_500_s = [[libres.t500], [frenadas.t500]]';
tiempo_cero_indicado_s = [[libres.tCero], [frenadas.tCero]]';
resumen = table(tipo, captura, rpm_referencia, tiempo_500_s, ...
                tiempo_cero_indicado_s);
disp(resumen);
writetable(resumen, fullfile(salida, 'resumen_comparacion.csv'));
fprintf('k libre mediano = %.4f 1/s\n', k);
fprintf('c frenado = %.1f y %.1f RPM/s; R2 local = %.3f y %.3f\n', ...
        [frenadas.c], [frenadas.r2]);

figure('Color', 'w'); hold on;
coloresLibres = [0.15 0.45 0.75; 0.20 0.60 0.70; 0.35 0.60 0.85];
for i = 1:numel(libres)
    D = libres(i).D;
    plot((D.tiempo_ms - libres(i).tRef)/1000, D.rpm, '--', ...
         'LineWidth', 1.2, 'Color', coloresLibres(i,:), ...
         'DisplayName', sprintf('Libre %d', i));
end
coloresFreno = [0.85 0.25 0.15; 0.65 0.10 0.25];
for i = 1:numel(frenadas)
    D = frenadas(i).D;
    plot((D.tiempo_ms - frenadas(i).tRef)/1000, D.rpm, '-', ...
         'LineWidth', 1.8, 'Color', coloresFreno(i,:), ...
         'DisplayName', sprintf('Frenada %d, g40', i));
end
xlim([-0.5 21]); ylim([0 1700]); grid on;
xlabel('Tiempo desde ~1300 RPM o desde g40 (s)'); ylabel('Velocidad (RPM)');
title('Giro libre y frenado: corridas reales'); legend('Location', 'northeast');
saveas(gcf, fullfile(salida, 'comparacion_real.png'));

figure('Color', 'w'); hold on;
for i = 1:numel(frenadas)
    D = frenadas(i).D;
    usar = D.tiempo_ms >= frenadas(i).tRef & ...
           D.tiempo_ms <= frenadas(i).tRef + 1300;
    plot((D.tiempo_ms(usar) - frenadas(i).tRef)/1000, D.rpm(usar), ...
         '.', 'Color', coloresFreno(i,:), 'DisplayName', sprintf('Medido %d', i));
    plot(frenadas(i).xAjuste, frenadas(i).pred, '-', ...
         'Color', coloresFreno(i,:), 'LineWidth', 1.5, ...
         'DisplayName', sprintf('Modelo local %d', i));
end
grid on; xlabel('Tiempo desde g40 (s)'); ylabel('Velocidad (RPM)');
title('Ajuste local antes de bajar de 500 RPM'); legend('Location', 'northeast');
saveas(gcf, fullfile(salida, 'ajuste_local.png'));

% Función de transferencia local desde freno normalizado u a delta omega.
% Válida cerca del tramo estudiado, antes de detenerse. El impulso de
% MATLAB es matemático; no se aplicó un impulso mecánico al disco.
if exist('tf', 'file') == 2 && exist('impulse', 'file') == 2
    cRad = median([frenadas.c]) * 2*pi/60;
    G = tf(-cRad, [1 k]);
    t = linspace(0, 4, 300);
    [hImpulso, tImpulso] = impulse(G, t);
    figure('Color', 'w');
    plot(tImpulso, squeeze(hImpulso), 'LineWidth', 1.5); grid on;
    xlabel('Tiempo (s)'); ylabel('Respuesta de velocidad angular');
    title('Respuesta al impulso del modelo local (no medida físicamente)');
    saveas(gcf, fullfile(salida, 'impulso_modelo_local.png'));
    fprintf('Modelo local: G(s) = %.3f/(s + %.4f), entrada freno normalizado.\n', ...
            -cRad, k);
else
    fprintf('Para generar el impulso se necesita Control System Toolbox.\n');
end

function [D, E] = cargar(capturas, id)
    D = readtable(fullfile(capturas, ['datos_' id '.csv']));
    E = readtable(fullfile(capturas, ['eventos_' id '.csv']));
end

function t = tiempoEvento(E, nombre)
    idx = find(strcmp(E.tipo, nombre), 1);
    assert(~isempty(idx), ['Falta el evento ' nombre]);
    t = E.tiempo_ms(idx);
end
