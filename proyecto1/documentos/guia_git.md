# Guía de Git — Proyecto Grupal 1

Repositorio: `SaddyGR3/sguzman_asm_2026_s2`. Rama principal: `main`. Rama de desarrollo: `development`.

Si no se cumple el flujo de Git, la parte funcional del proyecto vale cero. El profesor revisa las estadísticas: avance incremental todas las semanas y trabajo de todo el equipo.

---

## Configuración (una vez por persona)

```bash
git config --global user.name "Nombre Apellido"
git config --global user.email "correo-de-su-cuenta-de-github"
gh auth login
```

Si el correo no coincide con el de la cuenta de GitHub, los commits no se cuentan en las estadísticas.

## Estructura del repositorio

```
proyecto1/
  tarea1/        ← entrega de la Tarea 1
  avance_s12/    ← entrega del avance de la semana 12
  firmware/      ← nodo1, nodo2, nodo3, comun (protocolo.h)
  simulacion/    ← simulación del sistema completo en Python
  documentos/    ← plan, contrato, guías, enunciados, paper
```

## Creación inicial (ya hecha o por hacer una sola vez)

```bash
git checkout main
git pull
git checkout -b development
git push -u origin development

git checkout -b estructura-proyecto1
mkdir -p proyecto1/tarea1 proyecto1/avance_s12 proyecto1/firmware proyecto1/simulacion proyecto1/documentos
git mv seccion_2_1 seccion_2_2 seccion_2_3 seccion_2_4 seccion_2_5 entrega informe revision proyecto1/tarea1/
git mv ASM_Proyecto_Grupal1_v7.pdf Tareas_ASM_Tarea1_v7.pdf proyecto1/documentos/
touch proyecto1/avance_s12/.gitkeep proyecto1/firmware/.gitkeep proyecto1/simulacion/.gitkeep
git add -A
git commit -m "chore: estructura de proyecto1, mueve tarea1 y agrega plan y contrato"
git push -u origin estructura-proyecto1
gh pr create --base development --head estructura-proyecto1 --title "Estructura de proyecto1" --body "Mueve tarea1 a proyecto1/ y agrega documentos"
gh pr merge --merge
```

## Flujo para cada tarea

```bash
git checkout development
git pull
git checkout -b nombre-de-la-tarea
# ... trabajar, con commits pequeños y frecuentes ...
git add -A
git commit -m "feat: descripción corta"
git push -u origin nombre-de-la-tarea
gh pr create --base development --title "Título" --body "Qué hace"
gh pr merge --merge
git checkout development
git pull
```

- Siempre hacia `development`, nunca directo a `main`.
- Usar `--merge` (no `--squash`) para conservar cada commit con su autor.
- Nombres de rama sin tildes ni espacios: `nodo1-emisor`, `simulacion-sistema`, `plan-frecuencias`.
- Mensajes con prefijo: `feat:` (función nueva), `fix:` (corrección), `test:` (pruebas), `docs:` (documentos), `chore:` (estructura o configuración).

## Cerrar una entrega

```bash
gh pr create --base main --head development --title "Avance semana 12" --body "Integra el avance"
gh pr merge --merge
git checkout main
git pull
git tag avance_s12
git push origin avance_s12
```

Tags previstos: `avance_s12` (30 oct) y `proyecto1` (6 nov). Ya existe `tarea1_prototipo`.

## Reglas de trabajo

- Commits cada semana y de todos los integrantes; no subir todo en un solo commit al final.
- Cada integrante debe poder explicar el código que sube.
