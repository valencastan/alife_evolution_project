# 🌌 IpaVerse — Simulador de Vida Artificial y Evolución Darwiniana

<p align="center">
  <strong>Un ecosistema artificial infinito donde redes neuronales evolucionan en tiempo real mediante NEAT, compitiendo por sobrevivir en un mundo de depredadores, presas y selección natural implacable.</strong>
</p>

---

## 📖 Descripción

IpaVerse es un simulador de **vida artificial (Alife)** que combina neuroevolución, cascadas tróficas y dinámica de ecosistemas en una experiencia visual inmersiva. Cada organismo posee un cerebro neuronal recurrente que evoluciona generación tras generación mediante el algoritmo **NEAT** (NeuroEvolution of Augmenting Topologies).

La simulación es **infinita y continua**: no hay reinicios por generación. Los organismos nacen, cazan, se reproducen y mueren. Cuando un agente muere, su espacio es ocupado por un cerebro de la nueva generación genética (Dead Queue), manteniendo la continuidad del ecosistema sin cortes.

Cada ejecución crea un **Mundo con nombre propio**, cuya historia evolutiva se registra automáticamente en archivos JSON navegables desde el menú principal.

---

## 🚀 Inicio Rápido

### Requisitos
```
Python 3.10+
pygame-ce
neat-python
numpy
pandas
```

### Instalación
```bash
git clone https://github.com/tu-usuario/alife_evolution_project.git
cd alife_evolution_project
pip install -r requirements.txt
```

### Ejecución
```bash
python main.py
```

Al iniciar:
1. Se muestra el **Menú Principal**
2. Hacer click en **INICIAR SIMULACIÓN**
3. Ingresar el **nombre del mundo** (ej: "Pangea", "Edén")
4. La simulación infinita comienza

---

## 🎮 Controles

| Tecla | Acción |
|---|---|
| `ESC` | Volver al Menú Principal |
| `ESPACIO` | **Big Crunch** — Colapso gravitatorio que reinicia la geografía |
| `M` | Meteorito en la posición del cursor (mata agentes en radio) |
| `F` | Inundación — Regenera toda la comida del mapa |
| `R` | Radiación — Elimina el 50% de los agentes al azar |
| `Click Izq.` | Mini meteorito en el punto clickeado |
| `Scroll` | Zoom manual |

---

## 🧬 Arquitectura del Cerebro Neural

Cada organismo posee una red neuronal recurrente con **memoria temporal persistente** (las activaciones ocultas se retienen entre ticks, simulando memoria a corto plazo).

### Entradas Sensoriales (13)
| # | Entrada | Descripción |
|---|---|---|
| 0-2 | `Distancia a Pared` | Rayos en 3 sectores (izq, centro, der) |
| 3-5 | `Distancia a Comida` | Rayos hacia flora pasiva |
| 6-8 | `Distancia a Agentes` | Rayos hacia otros organismos |
| 9 | `Energía Propia` | Nivel de vida normalizado [0, 1] |
| 10 | `Señal Recibida` | Comunicación radial de otros agentes |
| 11 | `Olor a Sangre` | Energía máxima de vecinos cercanos |
| 12 | `Velocidad del Objetivo` | Velocidad del agente más cercano |

### Salidas Neuronales (7)
| # | Salida | Descripción | Visual en Radar |
|---|---|---|---|
| 0 | **Girar** | Timón de rotación angular | Girar |
| 1 | **Acelerar** | Propulsión motriz | Acelerar |
| 2 | **Señal** | Emisión de comunicación radial | Señal |
| 3 | **Morder** | Ataque — convierte en carnívoro permanente | Morder |
| 4 | **Camuflaje** | Desaparece de radares enemigos | Camuflaje |
| 5 | **Pulso Q** | Onda expansiva anti-depredadores (−30 energía) | Pulso Q |
| 6 | **Sobremarcha** | Velocidad 1.5x ignorando límites físicos | Sobremarcha |

---

## 🔺 Arquetipos Morfológicos

Los organismos mutan de forma visible según su comportamiento, creando una taxonomía visual emergente:

### 🟢 La Presa Pura — Círculo
- Forma base de todo organismo
- Se alimenta de flora pasiva (comida verde, +40 energía)
- Sin penalizadores metabólicos
- Color: Verde

### 🔴 El Depredador — Triángulo (Rojo Oscuro)
- Se activa irreversiblemente al morder (`Bite > 0.5`)
- **No puede** comer flora pasiva — solo carne
- Metabolismo 1.08x más costoso (balance aerodinámico)
- Roba el 100% de energía por presa consumida (mínimo 40)
- Puede comer a otros depredadores (canibalismo con herencia de kills)
- La punta afilada apunta siempre hacia la dirección de navegación

### 🟣 El Rastreador — Triángulo (Magenta / Púrpura)
- Probabilidad de mutación del 15% al convertirse en Depredador
- Posee **Olfato Completo**: Localiza e ignora por completo el estado de Camuflaje (`Oculto`) de las presas en su radio visual.
- Enemigo natural imperdonable de los agentes camperos.

### 🟡 El Sabio — Circulo Brillo (Blanco / Dorado)
- Asignado a organismos veteranos cuya edad supere los 13,000 milisegundos biológicos o posean alta complejidad conectiva.
- Mayor capacidad de decisión y adaptación empírica.

### 🔵 El Explorador — Rombo
- Se desbloquea al mantener velocidad > máxima durante 60+ frames consecutivos
- Especialista en navegación rápida del mapa
- Color: Azul

### 🟣 El Titán Legendario — Triángulo con corona
- Depredador que alcanza 7+ kills
- Obtiene +5% de velocidad base permanente
- Renderiza un **Shadow Trail** (estela oscura gruesa de 4px)
- Flecha púrpura con ★{kills} sobre su cabeza
- Al comer otro depredador, hereda sus kills (escalamiento exponencial)

---

## 🌍 Mecánicas del Mundo

### Cascadas Tróficas
```
Flora Pasiva (Comida Verde)
     ↓ alimenta
Herbívoros (Círculos Verdes)
     ↓ son cazados por
Depredadores (Triángulos Rojos)
     ↓ se cazan entre sí
Titanes Legendarios (★7+ kills)
```

### Refugios y Camuflaje
- **Arbustos (Thickets)**: Zonas circulares orgánicas translucidas. Otorgan camuflaje pasivo total a quien se adentre en ellas.
- **Madrigueras (Burrows)**: Pozos con inmunidad absoluta a ataques, pero con agresivo costo metabólico x2 y fatiga gravitatoria tras 150 frames.
- **Camuflaje Biológico (Oculto)**: El agente emplea energía neural (+0.20 metabólico) en engañar al sistema visual. **Atención**: La invisibilidad solo se sostiene mientras la velocidad actual sea inferior al 50%. Correr rompe orgánicamente el sigilo a nivel físico y lumínico.

### Anti-Camping de Paredes
- Radio de detección: 50px del borde
- Fuerza de repulsión: 6.0 (empuja hacia el centro)
- Penalización metabólica: 5.0x (mortal a corto plazo)

### Materialización Aleatoria
- Los agentes que mueren reaparecen en posiciones **aleatorias** del mapa
- **Ventaja posicional**: +100 energía si aparecen cerca de comida (<80px), 80 energía si lejos
- Animación de spawn: anillo dorado expansivo de 30 frames
- 100 frames de invulnerabilidad post-spawn

### Mitosis
- Agentes con ≥90 energía se dividen en dos (padre e hijo reciben 45 energía cada uno)
- El hijo hereda el cerebro y la clase del padre

---

## 🧪 Deriva Genética (Evolución en Segundo Plano)

La evolución de NEAT ocurre **silenciosamente cada 600 ticks** (~20 segundos):

1. Se evalúa el fitness de todos los agentes (`edad + energía × 0.1`)
2. NEAT ejecuta selección natural, reproducción y mutación
3. Los nuevos genomas se compilan en un **Pool de Cerebros** (Dead Queue)
4. Cuando un agente muere y reaparece, recibe un cerebro del pool evolucionado
5. Los agentes vivos **nunca** pierden su cerebro actual — la evolución es orgánica

El HUD muestra `Deriva Genética: ACTIVA` durante los 3 segundos posteriores a cada ciclo evolutivo.

---

## 📊 El Oráculo — Sistema de Historia

Cada 1200 ticks, el Oráculo captura un snapshot del estado del ecosistema:

```json
{
    "world_name": "Pangea",
    "timestamp_readable": "2026-04-01 20:50:00",
    "era_name": "Era de Los Depredadores Agresivos",
    "peak_fitness": 847.0,
    "alpha_id": 23,
    "alpha_complexity": 45,
    "blood_spilled": 12,
    "tick": 2400,
    "generation": 4,
    "population": 50,
    "avg_age": 234
}
```

### Navegación del Historial
Desde el menú principal → **HISTORIA**:
1. Se listan todos los **mundos** creados (subcarpetas en `history/`)
2. Al seleccionar un mundo, se muestra una tabla con todas sus épocas
3. Cada fila incluye: fecha/hora, era dominante, complejidad del alfa, muertes

---

## 🖥️ Interfaz Visual (HUD)

### Panel Lateral Izquierdo
- **Nombre del Mundo** (título)
- Población total, depredadores vivos, herbívoros pasivos
- Edad y complejidad del Alfa
- Nivel de zoom actual
- Estado de Deriva Genética
- Mensajes del Oráculo (resaltados en amarillo)

### Radar Neuronal del Alfa
Gráfico radar heptagonal (7 lados = 7 salidas neuronales) que muestra en tiempo real las activaciones del cerebro del agente Alfa:
- Polígono exterior gris: referencia máxima
- Polígono interior cyan: activaciones actuales
- Nodos brillantes: activaciones > 0.5
- Etiquetas completas en español

### Indicadores Visuales
- **Flecha blanca + "A"**: Agente Alfa (más longevo)
- **Flecha púrpura + "★N"**: Depredador Legendario con N kills
- **Anillo dorado expansivo**: Spawn de nuevo agente
- **Chispas rojas**: Evento de depredación
- **Anillo gris expansivo**: Pulso cinético
- **Estela gruesa oscura**: Shadow Trail de Legendario

---

## 📁 Estructura del Proyecto

```
alife_evolution_project/
├── main.py                    # Loop infinito principal + integración NEAT
├── config-feedforward         # Configuración de NEAT (topología, mutación, etc.)
├── requirements.txt           # Dependencias Python
├── IpaVerse_Concepto.txt      # Documento conceptual original
│
├── engine/
│   ├── compute_engine.py      # Motor de inferencia neuronal vectorizado (NumPy)
│   └── neat_bridge.py         # Compilador de genomas NEAT → matrices de pesos
│
├── environment/
│   └── sandbox.py             # Física del mundo, colisiones, energía, depredación
│
├── interface/
│   ├── visualizer.py          # Renderizado Pygame, HUD, radar neuronal, partículas
│   ├── menu.py                # Menú principal, input de nombre, navegador de historia
│   ├── oracle.py              # Análisis de arquetipos y persistencia histórica JSON
│   └── god_mode.py            # API de intervención divina (meteoros, radiación, etc.)
│
├── data/
│   └── logger.py              # Logger de fitness por generación (CSV)
│
├── history/                   # Historial por mundo (subcarpetas con JSONs)
│   └── {nombre_mundo}/
│       ├── epoch_1775086859.json
│       └── ...
│
└── logs/                      # Logs de fitness por run
```

---

## ⚙️ Parámetros de Balance

| Parámetro | Valor | Descripción |
|---|---|---|
| `max_speed` | 6.0 | Velocidad máxima base |
| `vision_range` | 150.0 | Rango de visión sensorial |
| `carnivore_metabolism` | 1.5x | Multiplicador metabólico de depredadores |
| `food_energy` | +40 | Energía ganada al comer flora |
| `bite_min_gain` | 30 | Ganancia mínima garantizada por mordida |
| `camouflage_threshold` | 0.7 | Umbral de activación neuronal para camuflaje |
| `camouflage_cost` | 0.05/tick | Costo energético del camuflaje activo |
| `overdrive_threshold` | 0.7 | Umbral de activación de sobremarcha |
| `overdrive_cost` | 0.02/tick | Costo energético de sobremarcha |
| `explorer_frames` | 60 | Frames consecutivos a alta velocidad para ser Explorador |
| `legendary_kills` | 7 | Kills para alcanzar estatus Legendario |
| `legendary_speed_bonus` | +5% | Boost de velocidad permanente para Legendarios |
| `wall_detection` | 50px | Radio de detección de paredes |
| `wall_repulsion` | 6.0 | Fuerza de repulsión de paredes |
| `wall_fatigue` | 5.0x | Penalización metabólica por campear en bordes |
| `spawn_invulnerability` | 100 frames | Protección post-spawn |
| `pulse_cost` | 30 energía | Costo del pulso cinético |
| `mitosis_threshold` | 90 energía | Energía necesaria para reproducirse |
| `drift_interval` | 600 ticks | Frecuencia de evolución NEAT en segundo plano |
| `oracle_interval` | 1200 ticks | Frecuencia de snapshots históricos |

---

## 📜 Licencia

Proyecto académico de investigación en vida artificial y neuroevolución.

---

<p align="center">
  <em>"En IpaVerse, la vida no se diseña — emerge."</em>
</p>
