# Checklist para dejar tu GitHub profesional

Todo esto son cosas que **tenés que hacer vos** desde la web de GitHub (yo no tengo
permiso para cambiar visibilidad de repos, editar metadata ni crear el repo de perfil).
Son ~15 minutos. Ordenado por impacto.

---

## 1. README de perfil  ⭐ (máximo impacto)

1. Creá un repo **nuevo, público**, con el nombre EXACTO de tu usuario: **`lucianonunnez`**.
   (New repository → Repository name: `lucianonunnez` → Public → Add a README).
   GitHub te va a mostrar el cartelito "You found a secret!" — es la señal de que está bien.
2. Pegá el contenido de `PERFIL_README.md` en el `README.md` de ese repo.
3. Reemplazá los `[[placeholders]]` (email, LinkedIn) y sacá los badges de tecnologías que no uses.

---

## 2. Privacidad: dejar SOLO `ZA` público

En cada uno de estos repos: **Settings → General → abajo de todo "Danger Zone" →
Change repository visibility → Make private**.

Repos a pasar a **privado** (todos menos ZA y el de perfil):

```
app_residencia_m-dica      enzoIA-IT              simulador_app
conciliaci-n_v2            bases_de_datos         dashboard-ACCA
dowloand_outlook           my_website             proyecto_pablo_an-lisis
charo_agentes              gestor-clientes        test-albrecht
alan_albrecht              dante                  1811_comision1
Dante-main                 Melier---bot           Gabys2026
Gabysrepo26                danteswork             dante-s-proyects
dante-proyects             sm-auditoria           clase-23_12_Flask
2312-c2                    caro_proyecto          asistente_saludable
gaby2011                   1811_comision2
```

> **Importante:** después de privatizar, andá a
> **Settings (tu cuenta) → Profile → activá "Include private contributions on my profile"**.
> Así tu gráfico de contribuciones (los cuadraditos verdes) sigue lleno aunque los repos
> estén privados. Sin esto, el perfil se ve vacío justo por haber ordenado.

### Opcional: borrar duplicados en vez de privatizar
Tenés 5 variantes del mismo proyecto: `dante`, `Dante-main`, `danteswork`,
`dante-s-proyects`, `dante-proyects`. Si son basura/duplicados, conviene **borrarlos**
(Settings → Delete repository) en lugar de solo privatizarlos. Menos ruido = mejor.
Lo mismo con `test-albrecht`, `Gabysrepo26`, `dante-proyects` si están vacíos.

---

## 3. `ZA` — el único repo público, tu vidriera

1. Pegá `ZA_README.md` como `README.md` en el repo ZA y completá los `[[placeholders]]`.
2. **Revisá que no filtre datos de la empresa** (nombres de clientes, credenciales,
   rutas internas, endpoints). Es lo único que va a ver un reclutador.
3. En el repo ZA → engranaje "About" (arriba a la derecha) → agregá:
   - **Description:** [[una línea de qué hace]]
   - **Topics:** `python`, `automation`, `data-analysis` (ajustá a lo que sea)

---

## 4. Descripciones + Topics (para los que dejes visibles)

Cada repo → botón "About" (engranaje, arriba a la derecha) → Description + Topics.
Los **topics** son lo que hace que tu perfil "parezca multi-tecnología" de un vistazo.
Aunque los pases a privado, tener esto prolijo ayuda si algún día compartís el link directo:

| Repo | Descripción sugerida | Topics |
|------|----------------------|--------|
| ZA | [[completar]] | python, automation |
| sm-auditoria | Sistema de auditoría de prestaciones médicas con detección de anomalías | python, data-analysis, anomaly-detection |
| dante | Pipeline TRIBE v2: predicción de actividad cerebral desde video | python, machine-learning, jupyter, neuroscience |
| dashboard-ACCA | Dashboard interactivo de gestión | javascript, dashboard, frontend |
| gestor-clientes | Gestor de clientes / CRM ligero | javascript, crm, web |
| simulador_app | Simulador [[completar]] | python |
| conciliaci-n_v2 | Automatización de conciliación de datos | python, automation, etl |
| dowloand_outlook | Automatización de descarga de adjuntos de Outlook | python, automation, outlook |
| charo_agentes | Agentes de IA para [[completar]] | python, ai, agents |
| asistente_saludable | Asistente de hábitos saludables (notebook) | python, jupyter, ml |
| my_website | Sitio personal | html, css, portfolio |

> Renombrá los que tienen acentos rotos: `conciliaci-n_v2` → `conciliacion-v2`,
> `app_residencia_m-dica` → `app-residencia-medica`, `proyecto_pablo_an-lisis` →
> `proyecto-analisis`. (Settings → Repository name → Rename.)

---

## 5. Repos fijados (Pinned)

En tu perfil → **"Customize your pins"**. Solo podés fijar hasta 6.
Como solo ZA queda público, un visitante externo solo verá ZA fijado — está perfecto:
que el único pin sea tu mejor trabajo. Fijá:

1. **ZA**

(Si más adelante hacés público alguno más — ej. `dante` o `sm-auditoria` limpiando
datos sensibles — sumalos como pins 2 y 3.)

---

## 6. Completar el perfil (Settings → Public profile)

- **Name:** Luciano Nuñez
- **Bio:** `Data & Automation Developer · Python · SQL · JS · Buenos Aires`
- **Location:** Buenos Aires, Argentina
- **Foto** de perfil profesional (evitá el avatar por defecto)
- **Website / LinkedIn** en el campo de links

---

## 7. Detalle técnico: tus commits no cuentan

Los commits del repo `dante` estaban autoreados por `Claude <noreply@anthropic.com>`,
que **no cuenta en tu gráfico de contribuciones**. Para que tus commits futuros sí cuenten,
configurá tu identidad de git (una sola vez, en tu compu):

```bash
git config --global user.name "Luciano Nuñez"
git config --global user.email "lucianonunnez@gmail.com"
```

Usá el **mismo email que tenés verificado en GitHub** (Settings → Emails).
