function resultado = analizar_ensayo(archivoCSV, referencia, opciones)
% Analiza CSV de frenado: protocolo con motor apagado o ejemplo con
% alimentacion constante. En el primero, referencia es eventos_*.csv;
% en el segundo, referencia es t0_ms. Requiere MATLAB R2020a o posterior.
% El ajuste usa fminsearch, incluido en MATLAB, sin Optimization Toolbox.

if nargin < 3, opciones = struct(); end
if isfield(opciones, 'protocolo') && strcmp(opciones.protocolo, 'motor_apagado')
    resultado = analizar_motor_apagado(archivoCSV, referencia, opciones);
    return
end
t0_ms = referencia;
if ~isfield(opciones, 'tipo_datos')
    error('Declare opciones.tipo_datos como experimental o simulado.');
end
if ~any(strcmp(opciones.tipo_datos, {'experimental', 'simulado'}))
    error('tipo_datos debe ser experimental o simulado.');
end
if ~isscalar(t0_ms) || ~isfinite(t0_ms)
    error('Indique t0_ms con el mismo reloj del CSV.');
end
opciones = valor_defecto(opciones, 'ajustar_modelo', false);
opciones = valor_defecto(opciones, 'intervalo_inicial_s', [-2 -0.2]);
opciones = valor_defecto(opciones, 'intervalo_final_s', []);
opciones = valor_defecto(opciones, 'retardo_s', 0);
opciones = valor_defecto(opciones, 'salida', ...
    fullfile(fileparts(archivoCSV), ['analisis_' opciones.tipo_datos]));
if ~isscalar(opciones.retardo_s) || ~isfinite(opciones.retardo_s) || opciones.retardo_s < 0
    error('retardo_s debe ser finito y no negativo.');
end
[~, ms, rpm, u] = leer_datos_ensayo(archivoCSV);
t = (ms - t0_ms) / 1000;
w = 2*pi*rpm/60;
if ~any(t < 0) || ~any(t >= 0)
    error('La captura debe incluir muestras antes y despues de t0_ms.');
end
if isempty(opciones.intervalo_final_s)
    opciones.intervalo_final_s = [0.8*max(t) max(t)];
end
ini = ventana(t, opciones.intervalo_inicial_s);
fin = ventana(t, opciones.intervalo_final_s);
pos = t >= 0;
if nnz(ini) < 5 || nnz(fin) < 5 || nnz(pos) < 10
    error('Faltan muestras en las ventanas. Amplie la captura o ajuste los intervalos.');
end
if any(t(ini) >= 0) || any(t(fin) <= opciones.retardo_s)
    error('La ventana inicial debe preceder al escalon y la final al retardo.');
end
u0 = median(u(ini)); u1 = median(u(fin)); du = u1-u0;
w0 = mean(w(ini)); wf = mean(w(fin)); dw = wf-w0;
resultado = struct('tipo_datos', opciones.tipo_datos, 't0_ms', t0_ms, ...
    'opciones', opciones, 'u_inicial_deg', u0, 'u_final_deg', u1, ...
    'omega_inicial', w0, 'omega_final', wf, ...
    'intervalo_registro_mediano_s', median(diff(t)), ...
    'modelo_estimado', false, 'motivo', 'Ajuste no solicitado');

if ~isfolder(opciones.salida), mkdir(opciones.salida); end
etiqueta = upper(opciones.tipo_datos);
f = figure('Name', ['Ensayo ' etiqueta], 'Color', 'w');
subplot(2,1,1);
stairs(t, u, 'LineWidth', 1.3); grid on; hold on;
xline(0, '--k', 'Orden de frenado');
ylabel('Orden del servo (grados)');
title(['Entrada y velocidad - ' etiqueta]);
subplot(2,1,2);
plot(t, w, '.-', 'LineWidth', 1); grid on; hold on;
xline(0, '--k'); yline(w0, ':'); yline(wf, ':');
xlabel('Tiempo desde la orden (s)'); ylabel('Velocidad (rad/s)');
estilo_figura(f);
exportgraphics(f, fullfile(opciones.salida, 'entrada_y_velocidad.png'));
writetable(table(t,u,rpm,w, 'VariableNames', ...
    {'tiempo_relativo_s','servo_cmd_deg','rpm','omega_rad_s'}), ...
    fullfile(opciones.salida, 'datos_convertidos.csv'));

if opciones.ajustar_modelo
    % Se comprueba la orden electrica. El servo real conserva su dinamica.
    tolerancia_u = max(0.5, 0.02*abs(du));
    pre = t < 0;
    motivo = '';
    if abs(du) < 0.5
        motivo = 'No hay un cambio suficiente en la orden del servo.';
    elseif any(abs(u(pre)-u0) > tolerancia_u) || any(abs(u(pos)-u1) > tolerancia_u)
        motivo = 'La orden no es un unico escalon sostenido. Revise rampas o cambios adicionales.';
    elseif any(w(pos) <= 0)
        motivo = 'Hay detencion o muestras cero. Revise el sensor y use otro ensayo para este modelo.';
    elseif abs(dw) < max(0.05, 3*std(w(ini)))
        motivo = 'El cambio de velocidad es pequeno frente al ruido inicial.';
    else
        % Un final que sigue variando no permite estimar bien el equilibrio.
        ci = polyfit(t(ini), w(ini), 1);
        cf = polyfit(t(fin), w(fin), 1);
        deriva_ini = abs(ci(1))*(max(t(ini))-min(t(ini)));
        deriva_fin = abs(cf(1))*(max(t(fin))-min(t(fin)));
        if max(deriva_ini, deriva_fin) > 0.10*abs(dw)
            motivo = 'Hay deriva apreciable en las ventanas. No se observa un equilibrio suficiente.';
        end
    end
    if isempty(motivo)
        L = opciones.retardo_s;
        tp = t(pos); wp = w(pos);
        K0 = dw/du;
        objetivo63 = w0 + (1-exp(-1))*dw;
        [~, idx] = min(abs(wp-objetivo63));
        tau0 = max(tp(idx)-L, median(diff(t)));
        % Se optimizan una ganancia normalizada y log(tau) para asegurar tau positivo.
        costo = @(q) sum((respuesta(tp,w0,du,K0*q(1),exp(q(2)),L)-wp).^2);
        [q,~,exitflag] = fminsearch(costo, [1 log(tau0)], ...
            optimset('Display','off','MaxFunEvals',5000,'MaxIter',2000));
        K = K0*q(1); tau = exp(q(2));
        pred = respuesta(tp,w0,du,K,tau,L);
        if exitflag <= 0 || ~isfinite(K) || ~isfinite(tau) || tau <= 0 || K*du*dw <= 0
            motivo = 'El ajuste no converge a un modelo coherente.';
        else
            resultado.modelo_estimado = true;
            resultado.motivo = 'Ajuste preliminar. Revisar las curvas y validar con otro ensayo.';
            resultado.K_rad_s_por_grado = K;
            resultado.tau_s = tau;
            resultado.retardo_s = L;
            resultado.RMSE_rad_s = sqrt(mean((wp-pred).^2));
            resultado.muestras_por_tau = tau/median(diff(t));
            resultado.tiempo_post_retardo_en_tau = (max(tp)-L)/tau;
            resultado.K_por_equilibrios = K0;
            subplot(2,1,2);
            plot(tp,pred,'LineWidth',1.6);
            legend('Medicion','Orden','Media inicial','Media final','Modelo','Location','best');
            estilo_figura(f);
            exportgraphics(f, fullfile(opciones.salida, 'entrada_y_velocidad.png'));
            fi = figure('Name',['Impulso del modelo ' etiqueta], 'Color','w');
            ti = linspace(0, L+6*tau, 1200)';
            % Expresion analitica de G(s)=K*exp(-L*s)/(tau*s+1).
            hi = zeros(size(ti)); despues = ti >= L;
            hi(despues) = (K/tau)*exp(-(ti(despues)-L)/tau);
            plot(ti, hi, 'LineWidth',1.5); grid on;
            xlabel('Tiempo (s)'); ylabel('h(t) ((rad/s)/(grado s))');
            title(['Impulso teorico del modelo ajustado - ' etiqueta]);
            estilo_figura(fi);
            exportgraphics(fi, fullfile(opciones.salida,'impulso_analitico.png'));
            % El enunciado pide impulse de MATLAB. Se ejecuta si esta instalado.
            resultado.impulse_ejecutado = false;
            if exist('tf','file') == 2 && exist('impulse','file') == 2
                try
                    G = tf(K, [tau 1], 'InputDelay', L);
                    fm = figure('Name','impulse de MATLAB','Color','w');
                    impulse(G, ti); grid on;
                    title(['impulse del modelo - ' etiqueta]);
                    estilo_figura(fm);
                    exportgraphics(fm, fullfile(opciones.salida,'impulse_matlab.png'));
                    resultado.impulse_ejecutado = true;
                catch err
                    warning('No se pudo ejecutar impulse. %s', err.message);
                end
            end
            if ~resultado.impulse_ejecutado
                warning('Falta ejecutar impulse con Control System Toolbox para completar esa parte.');
            end
            if resultado.muestras_por_tau < 5
                warning('Menos de 5 registros por constante de tiempo. Revise resolucion del ensayo.');
            end
            if resultado.tiempo_post_retardo_en_tau < 4
                warning('La captura posterior al retardo cubre menos de 4 constantes de tiempo.');
            end
        end
    end
    if ~isempty(motivo)
        resultado.motivo = motivo;
        warning('No se ajusto el modelo. %s', motivo);
    end
end
save(fullfile(opciones.salida,'resultado.mat'), 'resultado');
fid = fopen(fullfile(opciones.salida,'resumen.txt'),'w');
if fid == -1, error('No se pudo escribir resumen.txt.'); end
cerrar = onCleanup(@() fclose(fid));
fprintf(fid,'Datos %s\nArchivo %s\nt0_ms %.6g\n', etiqueta, archivoCSV, t0_ms);
fprintf(fid,'Orden inicial %.6g grados\nOrden final %.6g grados\n',u0,u1);
fprintf(fid,'Velocidad inicial %.6g rad/s\nVelocidad final %.6g rad/s\n',w0,wf);
fprintf(fid,'Estado %s\n',resultado.motivo);
if resultado.modelo_estimado
    fprintf(fid,'K %.9g (rad/s)/grado\ntau %.9g s\nRetardo fijado %.9g s\n',K,tau,L);
    fprintf(fid,'RMSE de ajuste %.9g rad/s\nRegistros por tau %.6g\n', ...
        resultado.RMSE_rad_s,resultado.muestras_por_tau);
    fprintf(fid,'Validacion independiente PENDIENTE\n');
    fprintf(fid,'impulse de MATLAB ejecutado %d\n',resultado.impulse_ejecutado);
end
fprintf(fid,'El angulo es una orden, no torque ni posicion medida.\n');
fprintf(fid,'La respuesta al impulso es calculada del modelo, no medida fisicamente.\n');
disp(resultado);
end

function opciones = valor_defecto(opciones, nombre, valor)
if ~isfield(opciones,nombre), opciones.(nombre) = valor; end
end

function mascara = ventana(t, limites)
if numel(limites) ~= 2 || any(~isfinite(limites)) || limites(1) >= limites(2)
    error('Cada intervalo debe tener dos limites finitos en orden creciente.');
end
mascara = t >= limites(1) & t <= limites(2);
end

function y = respuesta(t,y0,du,K,tau,L)
y = y0 + K*du*(1-exp(-max(t-L,0)/tau));
end

function [T, ms, rpm, u] = leer_datos_ensayo(archivoCSV)
% Importacion y controles compartidos por las simulaciones y CSV reales.
if ~isfile(archivoCSV), error('No existe el archivo CSV indicado.'); end
T = readtable(archivoCSV, 'VariableNamingRule', 'preserve');
nombres = T.Properties.VariableNames;
if ~all(ismember({'tiempo_ms', 'rpm'}, nombres))
    error('El CSV debe incluir tiempo_ms y rpm.');
end
if ismember('servo_cmd_grados', nombres)
    u = T.('servo_cmd_grados');
elseif ismember('servo_cmd_deg', nombres)
    u = T.('servo_cmd_deg');
elseif ismember('servo_grados', nombres)
    u = T.('servo_grados');
else
    error('Falta servo_cmd_grados, servo_cmd_deg o servo_grados.');
end
ms = T.('tiempo_ms'); rpm = T.('rpm');
if ~isnumeric(ms) || ~isnumeric(rpm) || ~isnumeric(u)
    error('Las tres columnas deben ser numericas. Quite mensajes de depuracion.');
end
if numel(ms) < 15 || any(~isfinite([ms; rpm; u]))
    error('Se requieren al menos 15 filas numericas, sin NaN ni Inf.');
end
if any(diff(ms) <= 0)
    error('El tiempo debe crecer estrictamente. Revise reinicios y duplicados.');
end
if any(rpm < 0) || any(u < 0 | u > 180)
    error('Revise RPM negativas o comandos fuera del intervalo 0 a 180 grados.');
end
end

function c = analizar_motor_apagado(archivoCSV, archivoEventos, opciones)
% Ruta experimental: el apagado de la fuente precede la orden g40.
% Comparacion y modelo conjunto se calculan en analizar_frenado_real.m.
opciones = valor_defecto(opciones, 'banda_rpm', [1250 1400]);
opciones = valor_defecto(opciones, 'banda_referencia_libre_rpm', [1250 1350]);
opciones = valor_defecto(opciones, 'umbral_rpm', 500);
opciones = valor_defecto(opciones, 'angulo_libre', 90);
opciones = valor_defecto(opciones, 'angulo_freno', 40);
if ~isfile(archivoEventos)
    error('Falta el CSV de eventos: %s', archivoEventos);
end
[D, ~, ~, u] = leer_datos_ensayo(archivoCSV);
D.servo_cmd_grados = u;
E = readtable(archivoEventos, 'VariableNamingRule', 'preserve');
if ~all(ismember({'tiempo_ms','tipo','valor'}, E.Properties.VariableNames))
    error('Eventos: faltan tiempo_ms, tipo o valor.');
end
if ~isnumeric(E.tiempo_ms) || ~isnumeric(E.valor) || ...
        any(~isfinite(E.tiempo_ms)) || any(~isfinite(E.valor))
    error('Eventos: tiempo o valor no numerico.');
end
tipos = string(E.tipo);
off = E.tiempo_ms(tipos == "MOTOR_OFF_MANUAL");
if numel(off) ~= 1, error('Se requiere una marca MOTOR_OFF_MANUAL.'); end
off = off(1);
ordenes = find(tipos == "SERVO_CMD" & E.tiempo_ms > off);
if isfield(opciones, 'id')
    id = opciones.id;
else
    [~, nombre] = fileparts(archivoCSV);
    id = nombre(7:end);
end
c = struct('id', id, 'tipo', '', 'D', D, 'tOff', off, ...
    'tRef', NaN, 'rpmRef', NaN, 't500', NaN, 'tCero', NaN, ...
    'reboteCero', false, 'k', NaN, 'c', NaN, 'r2', NaN, ...
    'xAjuste', [], 'yAjuste', [], 'pred', []);

if isempty(ordenes)
    % Primera RPM comparable despues de apagar el motor.
    if any(D.servo_cmd_grados(D.tiempo_ms >= off) ~= opciones.angulo_libre)
        error('El servo no permanecio en el angulo libre.');
    end
    idx = find(D.tiempo_ms >= off & D.rpm >= opciones.banda_referencia_libre_rpm(1) ...
        & D.rpm <= opciones.banda_referencia_libre_rpm(2), 1);
    if isempty(idx), error('No cruza la banda de RPM despues del apagado.'); end
    c.tipo = 'libre';
    c.tRef = D.tiempo_ms(idx);
    c.rpmRef = D.rpm(idx);
else
    % Una sola orden g40, con RPM previas comparables.
    if numel(ordenes) ~= 1 || E.valor(ordenes) ~= opciones.angulo_freno
        error('Se requiere una sola orden g%d despues del apagado.', opciones.angulo_freno);
    end
    tCmd = E.tiempo_ms(ordenes);
    prev = find(D.tiempo_ms < tCmd);
    prev = prev(max(1, numel(prev)-4):end);
    if numel(prev) < 3 || any(D.servo_cmd_grados(prev) ~= opciones.angulo_libre)
        error('Faltan RPM previas con el freno libre.');
    end
    c.rpmRef = median(D.rpm(prev));
    if c.rpmRef < opciones.banda_rpm(1) || c.rpmRef > opciones.banda_rpm(2)
        error('Orden a %.0f RPM, fuera de la banda comparable.', c.rpmRef);
    end
    c.tipo = 'frenada';
    c.tRef = tCmd;
end

idx500 = find(D.tiempo_ms >= c.tRef & D.rpm < opciones.umbral_rpm, 1);
if isempty(idx500), error('No hay cruce por debajo de %.0f RPM.', opciones.umbral_rpm); end
c.t500 = (D.tiempo_ms(idx500) - c.tRef)/1000;
idxCero = find(D.tiempo_ms >= c.tRef & D.rpm == 0, 1);
if ~isempty(idxCero)
    c.tCero = (D.tiempo_ms(idxCero) - c.tRef)/1000;
    c.reboteCero = any(D.rpm(idxCero+1:end) > 0);
end
end
