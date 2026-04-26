<div style="text-align: center; padding: 2rem 0;">
  <object data="cover.svg" type="image/svg+xml" style="max-width: 100%; max-height: 80vh;">
    AOSP Internals — Android Open Source Project 开发者指南
  </object>
</div>

---

## 许可证

本书采用 [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.html) 许可证发布。你可以按照 GPL-3.0 的条款自由分享和改编本作品。详情请参见 [LICENSE](https://github.com/anthropics/aosp-dev-book/blob/main/LICENSE) 文件。

本书基于对 [Android Open Source Project](https://source.android.com/) 的分析编写，而 AOSP 本身采用 Apache License 2.0 许可证。

## 如何阅读

请使用侧边栏按章节浏览内容。全书按照 Android 架构自底向上的顺序组织，每一章都可以单独阅读，但连续阅读会更容易建立完整的系统理解。

## 架构总览

```mermaid
graph TB
    subgraph "Part I-III: Foundation"
        BUILD["构建系统"] --> BOOT["启动 / Init"]
        BOOT --> KERNEL["内核"]
        KERNEL --> BIONIC["Bionic / Linker"]
        BIONIC --> BINDER["Binder IPC"]
        BINDER --> HAL["HAL"]
    end
    subgraph "Part IV-V: Services & Runtime"
        HAL --> NATIVE["Native Services"]
        NATIVE --> ART["ART Runtime"]
    end
    subgraph "Part VI-VII: Framework"
        ART --> SYSTEM["system_server"]
        SYSTEM --> WMS["窗口 / 显示"]
        SYSTEM --> PMS["Package Manager"]
        SYSTEM --> SERVICES["Framework Services"]
    end
    subgraph "Part VIII-XII: Features"
        SERVICES --> CONNECTIVITY["连接能力"]
        SERVICES --> SECURITY["安全"]
        SERVICES --> UI["UI Framework"]
        SERVICES --> APPS["系统应用"]
        SERVICES --> AI["AI / ML"]
    end
    subgraph "Part XIII-XV: Platform"
        APPS --> INFRA["基础设施"]
        INFRA --> DEVICES["设备支持"]
        DEVICES --> ROM["Custom ROM"]
    end
```
