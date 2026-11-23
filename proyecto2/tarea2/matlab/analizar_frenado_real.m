function resultado = analizar_frenado_real(carpetaCapturas, opciones)
% Analiza pares datos_*.csv/eventos_*.csv del banco ESP32, KY-033 y SG90.
% El motor se apaga antes de ordenar g40; ninguna corrida tiene equilibrio
% final positivo. El modelo es local, solo antes de bajar de 500 RPM.
% Cada corrida se importa y valida con analizar_ensayo.m, adaptado del
% analizador original; aqui se comparan y ajustan las corridas juntas.

if nargin < 2, opciones = struct(); end
if ~isfolder(carpetaCapturas)
    error('No existe la carpeta de capturas: %s', carpetaCapturas);
end
opciones = defecto(opciones, 'banda_rpm', [1250 1400]);
opciones = defecto(opciones, 'banda_referencia_libre_rpm', [1250 1350]);
opciones = defecto(opciones, 'umbral_rpm', 500);
opciones = defecto(opciones, 'angulo_libre', 90);
opciones = defecto(opciones, 'angulo_freno', 40);
opciones = defecto(opciones, 'ids', {}); % Vacio: analizar todos los pares validos.
opciones = defecto(opciones, 'salida', fullfile(fileparts(mfilename('fullpath')), 'resultados_reales'));
assert(numel(opciones.banda_rpm) == 2 && opciones.banda_rpm(1) < opciones.banda_rpm(2), ...
    'banda_rpm debe ser [minimo maximo].');
assert(numel(opciones.banda_referencia_libre_rpm) == 2 && ...
    opciones.banda_referencia_libre_rpm(1) < opciones.banda_referencia_libre_rpm(2), ...
    'banda_referencia_libre_rpm debe ser [minimo maximo].');
if ~isfolder(opciones.salida), mkdir(opciones.salida); end

archivos = dir(fullfile(carpetaCapturas, 'datos_*.csv'));
if isempty(archivos)
    error('No hay datos_*.csv en %s. Copie tambien los eventos_*.csv.', carpetaCapturas);
end
vacio = struct('id', {}, 'tipo', {}, 'D', {}, 'tOff', {}, 'tRef', {}, ...
    'rpmRef', {}, 't500', {}, 'tCero', {}, 'reboteCero', {}, ...
    'k', {}, 'c', {}, 'r2', {}, 'xAjuste', {}, 'yAjuste', {}, 'pred', {});
libres = vacio; frenadas = vacio;
fprintf('Leyendo %d archivos de datos en %s\n', numel(archivos), carpetaCapturas);

for i = 1:numel(archivos)
    nombre = archivos(i).name;
    id = nombre(7:end-4); % Quitar datos_ y .csv.
    if ~isempty(opciones.ids) && ~any(strcmp(id, opciones.ids))
        continue
    end
    rutaEventos = fullfile(carpetaCapturas, ['eventos_' id '.csv']);
    if ~isfile(rutaEventos)
        fprintf('Omitida %s: falta eventos_%s.csv\n', id, id);
        continue
    end
    try
        opcionesEnsayo = opciones;
        opcionesEnsayo.protocolo = 'motor_apagado';
        opcionesEnsayo.id = id;
        c = analizar_ensayo(fullfile(carpetaCapturas, nombre), rutaEventos, opcionesEnsayo);
        if strcmp(c.tipo, 'libre')
            libres(end+1) = c; %#ok<AGROW>
        else
            frenadas(end+1) = c; %#ok<AGROW>
        end
        fprintf('Incluida %s (%s): %.0f RPM; a <%.0f RPM en %.3f s\n', ...
            id, c.tipo, c.rpmRef, opciones.umbral_rpm, c.t500);
    catch err
        fprintf('Omitida %s: %s\n', id, err.message);
    end
end

if isempty(libres) || isempty(frenadas)
    error('Se necesita al menos una corrida libre y una frenada comparables. Revise los mensajes de omision.');
end

% Resumen directamente medido. RPM=0 es la indicacion del firmware, no
% necesariamente el instante mecanico exacto de detencion.
todas = [libres frenadas]; n = numel(todas);
tipo = strings(n,1); captura = strings(n,1);
rpm_referencia = zeros(n,1); tiempo_500_s = zeros(n,1);
tiempo_cero_indicado_s = NaN(n,1); rpm_despues_del_primer_cero = false(n,1);
apagado_a_orden_s = NaN(n,1);
for i = 1:n
    tipo(i) = string(todas(i).tipo); captura(i) = string(todas(i).id);
    rpm_referencia(i) = todas(i).rpmRef; tiempo_500_s(i) = todas(i).t500;
    tiempo_cero_indicado_s(i) = todas(i).tCero;
    rpm_despues_del_primer_cero(i) = todas(i).reboteCero;
    if strcmp(todas(i).tipo, 'frenada')
        apagado_a_orden_s(i) = (todas(i).tRef - todas(i).tOff)/1000;
    end
end
resumen = table(tipo, captura, rpm_referencia, tiempo_500_s, ...
    tiempo_cero_indicado_s, rpm_despues_del_primer_cero, apagado_a_orden_s);
writetable(resumen, fullfile(opciones.salida, 'resumen_comparacion.csv'));
disp(resumen);
fprintf('Promedio hasta <%.0f RPM: libre %.3f s; frenada %.3f s.\n', ...
    opciones.umbral_rpm, mean([libres.t500]), mean([frenadas.t500]));

f = figure('Name', 'Comparacion de corridas reales', 'Color', 'w'); hold on;
colores = lines(n);
for i = 1:n
    c = todas(i); D = c.D;
    estilo = '-'; if strcmp(c.tipo, 'libre'), estilo = '--'; end
    plot((D.tiempo_ms-c.tRef)/1000, D.rpm, estilo, 'Color', colores(i,:), ...
        'LineWidth', 1.2, 'DisplayName', sprintf('%s %s', c.tipo, c.id));
end
leyenda = legend('Location','northeast');
leyenda.AutoUpdate = 'off'; % Las líneas de referencia no son ensayos.
xline(0, ':k', 'Referencia / g40'); yline(opciones.umbral_rpm, ':k');
tiemposVisibles = [[todas.tCero] [todas.t500]];
tiemposVisibles = tiemposVisibles(isfinite(tiemposVisibles));
xlim([-1 max(tiemposVisibles)+1]);
ylim([0 max(opciones.banda_rpm(2)+200, max(cellfun(@(d) max(d.rpm), {todas.D})))]);
xlabel('Tiempo desde ~1300 RPM o desde g40 (s)'); ylabel('RPM');
title('Giro libre y frenado: mediciones sin filtro adicional'); grid on;
estilo_figura(f);
saveas(f, fullfile(opciones.salida, 'comparacion_real.png'));

% Mostrar explícitamente la entrada escalón y la salida física medida.
% t=0 es la orden g40; el contacto físico de la zapata puede ocurrir después.
f = figure('Name','Respuesta real al escalon de freno','Color','w');
axRpm = subplot(2,1,1); hold(axRpm,'on');
for i = 1:numel(frenadas)
    c = frenadas(i); D = c.D;
    plot(axRpm, (D.tiempo_ms-c.tRef)/1000, D.rpm, ...
        'Color', colores(numel(libres)+i,:), 'LineWidth',1.3, ...
        'DisplayName',sprintf('Frenada %s',c.id));
end
leyenda = legend(axRpm,'Location','northeast');
leyenda.AutoUpdate = 'off';
xline(axRpm,0,':k','Orden g40');
yline(axRpm,opciones.umbral_rpm,':k');
xlim(axRpm,[-0.5 3.5]); ylim(axRpm,[0 opciones.banda_rpm(2)+200]);
ylabel(axRpm,'RPM medidas');
title(axRpm,'Salida: velocidad del disco tras ordenar el freno');
grid(axRpm,'on');
axOrden = subplot(2,1,2);
stairs(axOrden,[-0.5 0 3.5],[0 1 1], ...
    'Color',[0.15 0.35 0.75],'LineWidth',1.5);
xlim(axOrden,[-0.5 3.5]); ylim(axOrden,[-0.1 1.1]);
yticks(axOrden,[0 1]);
yticklabels(axOrden,{'90 grados: libre','40 grados: freno'});
xlabel(axOrden,'Tiempo desde la orden g40 (s)');
title(axOrden,'Entrada: orden al servo (escalon idealizado)');
grid(axOrden,'on');
estilo_figura(f);
saveas(f,fullfile(opciones.salida,'respuesta_escalon_real.png'));

% Modelo local: caida libre k y desaceleracion adicional c con g40.
% No usar RPM=0 ni velocidades inferiores al umbral en el ajuste.
for i = 1:numel(libres)
    c = libres(i); D = c.D;
    idx = find(D.tiempo_ms >= c.tRef & D.tiempo_ms < c.tRef+1000*c.t500 & D.rpm > 0);
    if numel(idx) < 5, continue; end
    x = (D.tiempo_ms(idx)-c.tRef)/1000; y = D.rpm(idx);
    p = polyfit(x, log(y), 1);
    libres(i).k = -p(1);
end
kValidos = [libres.k]; kValidos = kValidos(isfinite(kValidos) & kValidos > 0);
resultado = struct('carpeta_capturas', carpetaCapturas, 'opciones', opciones, ...
    'resumen', resumen, 'modelo_estimado', false, 'impulse_ejecutado', false);
if isempty(kValidos)
    warning('No se obtuvo una caida libre exponencial positiva; se guardo solo la comparacion.');
    save(fullfile(opciones.salida, 'resultado.mat'), 'resultado');
    return
end
k = median(kValidos);
for i = 1:numel(frenadas)
    c = frenadas(i); D = c.D;
    idx = find(D.tiempo_ms >= c.tRef & D.tiempo_ms < c.tRef+1000*c.t500);
    if numel(idx) < 5, continue; end
    x = (D.tiempo_ms(idx)-c.tRef)/1000; y = D.rpm(idx);
    h = (1-exp(-k*x))/k;
    base = c.rpmRef*exp(-k*x);
    coef = max(0, sum(h.*(base-y))/sum(h.^2)); % RPM/s; u=1 con g40.
    pred = base-coef*h;
    denominador = sum((y-mean(y)).^2);
    r2 = NaN; if denominador > 0, r2 = 1-sum((y-pred).^2)/denominador; end
    frenadas(i).c = coef; frenadas(i).r2 = r2;
    frenadas(i).xAjuste = x; frenadas(i).yAjuste = y;
    frenadas(i).pred = pred;
end
cValidos = [frenadas.c]; cValidos = cValidos(isfinite(cValidos) & cValidos > 0);
if isempty(cValidos)
    warning('No se obtuvo desaceleracion adicional positiva; se guardo solo la comparacion.');
    save(fullfile(opciones.salida, 'resultado.mat'), 'resultado');
    return
end

f = figure('Name','Ajuste local de frenado','Color','w'); hold on;
for i = 1:numel(frenadas)
    if isempty(frenadas(i).xAjuste), continue; end
    plot(frenadas(i).xAjuste, frenadas(i).yAjuste, '.', ...
        'Color', colores(numel(libres)+i,:), 'DisplayName', sprintf('Medido %s', frenadas(i).id));
    plot(frenadas(i).xAjuste, frenadas(i).pred, '-', 'LineWidth', 1.5, ...
        'Color', colores(numel(libres)+i,:), 'DisplayName', sprintf('Modelo %s', frenadas(i).id));
end
xlabel('Tiempo desde g40 (s)'); ylabel('RPM');
title('Ajuste local: solo antes de 500 RPM'); grid on;
legend('Location','northeast'); estilo_figura(f);
saveas(f, fullfile(opciones.salida,'ajuste_local.png'));

% G(s)=-c/(s+k), con entrada normalizada 0 libre / 1 g40 y salida rad/s.
% La respuesta al impulso es del MODELO, no un impulso fisico al disco.
cRad = median(cValidos)*2*pi/60;
t = linspace(0,4,400)';
f = figure('Name','Impulso del modelo local','Color','w');
plot(t, -cRad*exp(-k*t), 'LineWidth',1.5); grid on;
xlabel('Tiempo (s)'); ylabel('Respuesta del modelo');
title('Impulso matematico del modelo local (analitico)');
estilo_figura(f); saveas(f,fullfile(opciones.salida,'impulso_analitico.png'));
resultado.modelo_estimado = true;
resultado.k_por_s = k; resultado.c_rpm_por_s = median(cValidos);
resultado.G_numerador = -cRad; resultado.G_denominador = [1 k];
resultado.r2_frenadas = [frenadas.r2];
if exist('tf','file') == 2 && exist('impulse','file') == 2
    try
        G = tf(-cRad,[1 k]);
        [hImpulso,tImpulso] = impulse(G,t);
        f = figure('Name','impulse de MATLAB','Color','w');
        plot(tImpulso,squeeze(hImpulso),'LineWidth',1.5); grid on;
        xlabel('Tiempo (s)'); ylabel('Respuesta del modelo');
        title('impulse(G): modelo local, no medicion fisica');
        estilo_figura(f); saveas(f,fullfile(opciones.salida,'impulse_matlab.png'));
        resultado.impulse_ejecutado = true;
    catch err
        warning('No se pudo ejecutar impulse: %s',err.message);
    end
else
    warning('Control System Toolbox no disponible: se guardo el impulso analitico, falta impulse(G).');
end
save(fullfile(opciones.salida,'resultado.mat'),'resultado');
fid = fopen(fullfile(opciones.salida,'resumen_modelo.txt'),'w');
if fid ~= -1
    limpiar = onCleanup(@() fclose(fid)); %#ok<NASGU>
    fprintf(fid,'Modelo local, motor apagado antes de g40, ~1300 a 500 RPM\n');
    fprintf(fid,'dRPM/dt = -k*RPM - c*u; u=0 libre, u=1 orden g40\n');
    fprintf(fid,'k = %.6g 1/s; c mediana = %.6g RPM/s\n', k, median(cValidos));
    fprintf(fid,'G(s) = %.6g/(s+%.6g) en rad/s por orden normalizada\n', -cRad, k);
    fprintf(fid,'R2 de las frenadas: %s\n', mat2str([frenadas.r2],3));
    fprintf(fid,'impulse de MATLAB ejecutado: %d\n',resultado.impulse_ejecutado);
    fprintf(fid,'Revisar visualmente el ajuste. No extrapolar a cero ni inferir torque.\n');
end
fprintf('Modelo local G(s) = %.3f/(s + %.4f); R2 frenadas %s\n', ...
    -cRad, k, mat2str([frenadas.r2],3));
end

function opciones = defecto(opciones, nombre, valor)
if ~isfield(opciones,nombre), opciones.(nombre) = valor; end
end
