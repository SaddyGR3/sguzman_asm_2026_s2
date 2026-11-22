function estilo_figura(figura)
% Colores explicitos para evitar mezclar el tema oscuro con fondo claro.
set(figura,'Color','w');
ejes = findall(figura,'Type','axes');
for k = 1:numel(ejes)
    ax = ejes(k);
    set(ax,'Color','w','XColor',[0.18 0.22 0.27], ...
        'YColor',[0.18 0.22 0.27],'ZColor',[0.18 0.22 0.27], ...
        'FontName','Helvetica','FontSize',11,'LineWidth',0.8, ...
        'GridColor',[0.55 0.60 0.65],'GridAlpha',0.20,'Box','off');
    set(ax.Title,'Color',[0.12 0.16 0.20],'FontSize',12);
    set(ax.XLabel,'Color',[0.18 0.22 0.27]);
    set(ax.YLabel,'Color',[0.18 0.22 0.27]);
end
textos = findall(figura,'Type','text');
set(textos,'Color',[0.12 0.16 0.20]);
leyendas = findall(figura,'Type','legend');
set(leyendas,'Color','w','TextColor',[0.18 0.22 0.27], ...
    'EdgeColor',[0.8 0.82 0.85]);
drawnow;
end
