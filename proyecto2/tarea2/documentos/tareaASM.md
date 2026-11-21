DIAGRAMA ARQUITECTURA PROPUESTA

flowchart LR
    A["Referencia de velocidad"] --> B["Comparador"]
    B --> C["Controlador PID digital"]
    C --> D["Etapa de accionamiento del freno"]
    D --> E["Actuador de frenado"]
    E --> F["Disco o rueda"]

    M["Alimentación del motor"] --> G["Motor DC"]
    G --> F

    F --> H["Sensor de velocidad"]
    H --> I["Acondicionamiento / adquisición"]
    I --> J["Microcontrolador ESP32"]
    J --> K["Registro y visualización"]

    J -. "Realimentación" .-> B

    L["Orden manual de prueba<br/>(lazo abierto)"] --> D

    style C fill:#dceeff,stroke:#2563eb,color:#000
    style J fill:#dceeff,stroke:#2563eb,color:#000
    style F fill:#dcfce7,stroke:#16a34a,color:#000
    style L fill:#fef3c7,stroke:#d97706,color:#000


    diagrama_electrico

    flowchart TD
    A["Computadora / USB"]
    B["ESP32 Dev Module"]
    C["Driver de motor DC"]
    D["Motor DC de 12 V"]
    E["Fuente de 12 V"]
    F["Fuente de 5–6 V"]
    G["Servomotor"]
    H["Mecanismo de frenado"]
    I["Sensor óptico de velocidad"]
    J["Disco encoder"]
    K["Tierra común (GND)"]

    A -->|"USB: programación y datos"| B

    B -->|"PWM / control"| C
    E -->|"Alimentación 12 V"| C
    C -->|"Potencia"| D

    B -->|"Señal de control"| G
    F -->|"Alimentación 5–6 V"| G
    G --> H

    J -->|"Pulsos de giro"| I
    I -->|"Señal digital 3.3 V"| B

    B -.-> K
    C -.-> K
    F -.-> K
    I -.-> K

    classDef control fill:#DBEAFE,stroke:#2563EB,color:#000;
    classDef potencia fill:#FEF3C7,stroke:#D97706,color:#000;
    classDef mecanico fill:#DCFCE7,stroke:#16A34A,color:#000;
    classDef tierra fill:#F3F4F6,stroke:#6B7280,color:#000;

    class A,B,I control;
    class C,E,F potencia;
    class D,G,H,J mecanico;
    class K tierra;