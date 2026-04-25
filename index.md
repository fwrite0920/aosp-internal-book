## License

This book is licensed under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0), matching the license of the [Android Open Source Project](https://source.android.com/) it analyzes. See the [LICENSE](https://github.com/aospbooks/aosp-internal-book/blob/main/LICENSE) file for details.

## How to Navigate

Use the sidebar to browse chapters organized bottom-to-top through the Android architecture. Each chapter is self-contained but builds on previous ones.

## Architecture Overview

```mermaid
graph TB
    subgraph "Part I-III: Foundation"
        BUILD[Build System] --> BOOT[Boot/Init]
        BOOT --> KERNEL[Kernel]
        KERNEL --> BIONIC[Bionic/Linker]
        BIONIC --> BINDER[Binder IPC]
        BINDER --> HAL[HAL]
    end
    subgraph "Part IV-V: Services & Runtime"
        HAL --> NATIVE[Native Services]
        NATIVE --> ART[ART Runtime]
    end
    subgraph "Part VI-VII: Framework"
        ART --> SYSTEM[system_server]
        SYSTEM --> WMS[Window/Display]
        SYSTEM --> PMS[Package Manager]
        SYSTEM --> SERVICES[Framework Services]
    end
    subgraph "Part VIII-XII: Features"
        SERVICES --> CONNECTIVITY[Connectivity]
        SERVICES --> SECURITY[Security]
        SERVICES --> UI[UI Framework]
        SERVICES --> APPS[System Apps]
        SERVICES --> AI[AI/ML]
    end
    subgraph "Part XIII-XV: Platform"
        APPS --> INFRA[Infrastructure]
        INFRA --> DEVICES[Device Support]
        DEVICES --> ROM[Custom ROM]
    end
```
