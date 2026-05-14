# 附录 B：术语表

本附录按字母顺序列出 AOSP 和本书中使用的关键术语、缩写和子系统名称。

---

**ABI**（Application Binary Interface）
: 编译后代码与操作系统之间的低层接口契约，规定给定架构（例如 arm64、x86_64、riscv64）的调用约定、数据布局和系统调用编号。

**ADB**（Android Debug Bridge）
: 通过 USB 或 TCP 与 Android 设备通信的命令行工具和守护进程。它提供 shell 访问、文件传输、应用安装和调试能力。

**AIDL**（Android Interface Definition Language）
: 用于定义进程间 IPC 契约的接口描述语言。从 Android 12+ 开始，现代 AIDL 在 HAL 接口中替代 HIDL，并支持 Java 和 C++ 后端。

**AMS**（ActivityManagerService）
: 负责管理应用进程、执行权限检查，并与 ATMS 协调 Activity 生命周期的系统服务。运行在 `system_server` 中。

**ANR**（Application Not Responding）
: 当应用主线程阻塞过久时触发的系统对话框；输入事件通常为 5 秒，广播接收器通常为 10 秒。AMS 负责监控并执行 ANR 超时。

**AOT**（Ahead-Of-Time compilation）
: 在执行前将 DEX 字节码编译为本机机器码，由 `dex2oat` 执行。它会生成存储在磁盘上的 OAT 文件，以缩短冷启动时间。

**APEX**（Android Pony EXpress）
: 可更新系统组件（Mainline 模块）的文件格式和安装机制。APEX 是一种类似 zip 的容器，包含文件系统镜像、manifest 和签名，由 `apexd` 管理。

**ART**（Android Runtime）
: 执行 Android 应用的托管运行时。它在 Android 5.0 中取代 Dalvik，结合 AOT 编译、JIT 编译、解释器和并发垃圾回收器。

**ATMS**（ActivityTaskManagerService）
: 管理 Activity 任务栈、返回栈导航和多窗口模式的系统服务。它在 Android 10 中从 AMS 拆分出来，将任务管理与进程管理分离。

**AVB**（Android Verified Boot）
: 使用加密签名验证每个启动分区完整性的信任链机制。也称为 `vbmeta`，由 bootloader 和 `fs_mgr` 执行。

**AVF**（Android Virtualization Framework）
: 在 Android 上启用硬件隔离虚拟机的框架。它由 virtualization service、pKVM hypervisor 和 Microdroid guest OS 组成，在 Android 13 引入。

**BHB**（BufferHub）
: 用于进程间零拷贝 buffer 共享的系统，主要服务于 VR 和低延迟显示路径。它管理 buffer 生命周期和同步。

**Binder**
: Android 的主要 IPC 机制。内核驱动（`/dev/binder`）结合用户态库，提供面向对象、同步的进程间远程过程调用，并内建引用计数和死亡通知。

**Bionic**
: Android 的定制 C 库，用于替代 glibc。它包含 `libc`、`libm`、`libdl` 和动态链接器（`linker64`），并针对体积、安全性（MTE 支持）和 Android 特定能力（系统属性）优化。

**BLAST**（Buffer Layer Accelerated SurfaceTexture）
: SurfaceFlinger 中现代 buffer 提交路径，用于替代旧 BufferQueue 模型。它将 buffer 提交与 SurfaceFlinger transaction 绑定，实现原子、同步更新。

**Blueprint**
: Soong 使用的构建描述语言。`Android.bp` 文件使用类似 JSON 的声明式语法定义模块，例如库、二进制、APK 和 APEX 包。

**BufferQueue**
: 用于进程间共享图形 buffer 的生产者-消费者队列。生产者（应用）dequeue/queue buffer；消费者（SurfaceFlinger）acquire/release buffer。它正逐步被 BLASTBufferQueue 取代。

**CDM**（CompanionDeviceManager）
: 管理 Android 设备与伴侣设备（手表、耳机等）之间关联的系统服务，提供发现、配对和权限委托。

**Choreographer**
: Java 侧协调器，用于按照显示 VSYNC 信号调度绘制、动画和输入回调。它是 Android UI 渲染循环的节拍器。

**CTS**（Compatibility Test Suite）
: 设备制造商必须通过的大型测试套件，用于认证 Android 兼容性。测试覆盖 API 行为、权限、安全和平台功能。

**Cuttlefish**
: Google 的可配置 Android 虚拟设备，面向云端测试和开发。它运行在带 KVM 的 Linux 上，比传统模拟器更接近真实设备。

**DEX**（Dalvik Executable）
: Android 应用的字节码格式。`.dex` 文件包含由 Java/Kotlin 编译而来的寄存器式指令集，针对内存受限设备优化。

**DisplayContent**
: WMS 中表示单个逻辑显示全部窗口状态的容器。它持有显示专属的窗口层级、策略和配置。

**DMA-BUF**
: Linux 内核中用于在设备和用户空间之间共享 buffer 的框架。Android 图形栈大量使用它在 GPU、显示、相机和视频硬件之间实现零拷贝共享。

**DRM/KMS**（Direct Rendering Manager / Kernel Mode Setting）
: Linux 内核图形子系统。KMS 负责显示模式设置和 page flipping；DRM 管理 GPU 命令提交。HWC HAL 通常封装 DRM/KMS。

**EGL**
: OpenGL ES 与原生窗口系统之间的接口。它管理 display 连接、渲染上下文和 surface。Android 的 EGL 实现位于 `libEGL.so`。

**Fastboot**
: 用于向 Android 设备刷写固件镜像的协议和工具。它在 OS 启动前运行于 bootloader 中，提供对分区的低层访问。

**GKI**（Generic Kernel Image）
: Google 维护的内核二进制，向 vendor 内核模块提供稳定 ABI（KMI）。它是 Project Treble 内核模块化的一部分。

**Goldfish**
: 传统 Android 模拟器虚拟设备平台，名称来自早期基于 QEMU 的虚拟硬件。它正逐步被 Cuttlefish 用于云端测试场景。

**Gralloc**（Graphics Allocator）
: 负责在设备内存中分配图形 buffer 的 HAL。它拆分为 `allocator`（分配）和 `mapper`（CPU 映射）接口。

**GTS**（Google Test Suite）
: Google 用于验证认证设备上 GMS（Google Mobile Services）集成的专有测试套件。它不同于开源 CTS。

**HAL**（Hardware Abstraction Layer）
: Android framework 与硬件专属驱动代码之间的标准化接口。HAL 将 vendor 实现隔离在稳定接口（AIDL 或旧 HIDL）之后。

**HIDL**（HAL Interface Definition Language）
: Project Treble（Android 8.0）引入的 HAL 接口定义语言。从 Android 12+ 开始，HAL 正逐步改用 AIDL。

**HWC**（Hardware Composer）
: 驱动显示合成的 HAL。SurfaceFlinger 将 layer 合成交给 HWC，由它决定使用专用硬件 overlay plane，或回退到 GPU 合成。

**HWUI**
: Android 的硬件加速 2D 渲染库。它通过基于 Skia 的 DisplayList 架构，将 `Canvas` 绘制命令转换为 GPU 操作，并运行在专用 `RenderThread` 上。

**IME**（Input Method Editor）
: 软件键盘和文本输入框架。IME 是一种特殊服务，提供用于文本输入的窗口，由 `InputMethodManagerService` 管理。

**InputFlinger**
: 负责从内核（`/dev/input/`）读取输入事件、处理事件，并通过 `InputDispatcher` 将事件分发给正确窗口的 native 服务。

**Intent**
: Android 用于请求组件执行动作的消息传递对象。Intent 可以启动 Activity、Service 或发送广播，并由 `PackageManagerService` 根据已注册 intent filter 解析。

**ION**
: 旧版 Android 专用内存分配器，用于在硬件组件之间共享 buffer。现代内核中它已被 upstream DMA-BUF heaps 框架取代。

**JIT**（Just-In-Time compilation）
: 运行时将频繁执行的 DEX 字节码编译为本机机器码。ART 的 JIT 编译器使用 profiling 数据识别热点方法，在启动速度和峰值性能之间取得平衡。

**JNI**（Java Native Interface）
: Java/Kotlin 托管代码与原生 C/C++ 代码之间互相调用的标准接口。ART 对 JNI 实现了 fast-path 优化，并管理托管栈与原生栈之间的转换。

**Kleaf**
: 基于 Bazel 的内核构建系统，用于替代旧 shell 脚本构建。它提供 hermetic build、缓存和更好的 AOSP 构建系统集成。

**KMI**（Kernel Module Interface）
: GKI 内核与 vendor 提供的内核模块之间的稳定 ABI。它允许内核和 vendor 模块独立更新，同时保持兼容。

**LLNDK**（LL-NDK）
: 平台分区和 vendor 分区均可使用的一组低层 NDK 库，包括 `libc`、`libm`、`liblog`、`libbinder_ndk` 等。它们在 Android 版本之间保持稳定。

**LMKD**（Low Memory Killer Daemon）
: 监控内存压力（通过 PSI）并杀死后台进程以避免 OOM 的用户态守护进程。它取代了旧的内核 lowmemorykiller。

**Looper**
: `Handler` 和 `MessageQueue` 底层的 native 事件循环机制。`Looper` 轮询文件描述符（包括 Binder）并分发消息。每个带 `Handler` 的线程都有一个 `Looper`。

**Mainline**
: Google 通过 Google Play 以 APEX 或 APK 模块形式交付核心 OS 组件更新的计划，独立于完整 OTA。它覆盖 30 多个模块，包括 Wi-Fi、Bluetooth、Media、DNS 等。

**Microdroid**
: pKVM 虚拟机中使用的最小 Android guest OS。它包含精简内核、init 和 payload runtime，用于在 AVF 中运行隔离工作负载。

**MTE**（Memory Tagging Extension）
: ARM 硬件特性，通过为内存分配打标签来检测 use-after-free 和 buffer overflow。Bionic 和内核在兼容硬件上支持 MTE。

**NDK**（Native Development Kit）
: 允许开发者用 C/C++ 编写部分 Android 应用的工具、头文件和库集合。NDK 提供跨 Android 版本保证稳定的 API 表面。

**NNAPI**（Neural Networks API）
: Android 面向机器学习推理的硬件抽象 API。它通过 `neuralnetworks` HAL 将计算委托给加速器（GPU、DSP、NPU）。

**OAT**
: `dex2oat` 生成的文件格式，包含 AOT 编译后的本机代码以及原始 DEX 字节码。OAT 文件是 ART 在运行时加载的 ELF 二进制。

**OTA**（Over-The-Air update）
: 无线交付系统更新的机制。Android 支持 A/B（无缝）和带 dm-snapshot 压缩的 Virtual A/B 更新策略。

**Parcel**
: Binder 用于跨进程序列化数据的容器。它支持原始类型、`IBinder` 引用、文件描述符和 `Parcelable` 对象。

**pKVM**（Protected Kernel-based Virtual Machine）
: 集成到 Android 内核中的 hypervisor，提供硬件隔离虚拟机。它是 AVF 的基础，在 ARM64 上运行于 EL2 以强制内存隔离。

**PMS**（PackageManagerService）
: 负责安装、卸载和查询包的系统服务。它维护包数据库、解析 intent，并管理权限。

**PSI**（Pressure Stall Information）
: Linux 内核机制，用于报告任务等待 CPU、内存或 I/O 资源而停滞的时间比例。LMKD 使用 PSI 做出 kill 决策。

**RenderEngine**
: SurfaceFlinger 的 GPU 合成后端。它使用 Skia（GL 或 Vulkan）合成 HWC 无法用硬件处理的 layer，并取代旧 GLES RenderEngine。

**RenderThread**
: 每个 Android 进程中的专用线程，负责执行 GPU 绘制命令。它将 GPU 工作从主线程（UI 线程）解耦，使 UI 线程能在 GPU 完成当前帧时开始下一帧。

**RRO**（Runtime Resource Overlay）
: 在运行时覆盖已有包资源（layout、string、drawable）的机制，无需修改原始 APK。它用于主题化和 OEM 定制。

**SELinux**（Security-Enhanced Linux）
: Android 强制执行的 mandatory access control（MAC）系统。每个进程和文件都有安全上下文，`sepolicy` 规则定义允许的交互。Android 以 enforcing 模式使用 SELinux。

**Skia**
: Android 全栈使用的 2D 图形库。它提供 `Canvas` 绘制操作、文本渲染、图片解码和 PDF 生成。后端包括 OpenGL、Vulkan（Ganesh）和下一代 Graphite。

**Soong**
: Android 构建系统，处理 `Android.bp` 文件（Blueprint 语法）并生成 Ninja 构建规则。它取代了大多数模块使用的旧 Make 构建。

**SurfaceFlinger**
: Android 的系统合成器。它接收来自应用和 SystemUI 的 buffer，通过 HWC 和/或 GPU 合成，并将最终帧呈现到显示器。

**SystemUI**
: Android 中常驻运行的系统应用，提供状态栏、通知栏、快速设置、锁屏、导航栏、音量对话框等系统界面。

**TEE**（Trusted Execution Environment）
: 与主 OS 隔离的安全处理环境。Android 使用 TEE（通常为 ARM TrustZone）处理 Keymaster/Keymint、Gatekeeper 和生物识别模板存储。

**Tombstone**
: native 进程崩溃时生成的崩溃转储文件。它包含寄存器状态、回溯、内存映射和其他诊断信息，存储在 `/data/tombstones/`。

**TradeFed**（Trade Federation）
: Android 用于运行 CTS、VTS 和其他测试套件的测试框架。它管理设备分配、测试执行、结果收集和报告。

**Treble**
: Google 在 Android 8.0+ 推出的架构计划，将平台 framework 与 vendor 专属 HAL 实现分离。它通过解耦 vendor 分区来加快 OS 更新。

**Trusty**
: Google 的开源 TEE 操作系统。它与 Android 并行运行在安全世界中，承载密钥管理、DRM 和安全 UI 的可信应用。

**VDEX**
: 一种文件格式，用于在 OAT 文件旁存储原始 DEX 字节码和验证元数据。它允许 ART 在没有原始 APK 的情况下重新验证并重新优化 DEX 代码。

**VDM**（VirtualDeviceManager）
: 创建和管理虚拟设备的系统服务，这些设备拥有自己的显示、输入、传感器和音频。它用于多设备体验和流式传输。

**VINTF**（Vendor Interface）
: 描述 vendor 分区与 platform 分区之间接口的兼容性框架。`VINTF` manifest 声明设备提供哪些 HAL，以及 framework 需要哪些 HAL。

**VNDK**（Vendor NDK）
: vendor HAL 实现可用的一组 framework 共享库。VNDK snapshot 确保 vendor 代码运行在已知库版本集合之上。

**VSYNC**（Vertical Synchronization）
: 用于同步整个图形管线渲染的显示刷新信号。Choreographer、SurfaceFlinger 和 HWC 都围绕 VSYNC 事件协作。

**VTS**（Vendor Test Suite）
: 验证 vendor HAL 实现是否符合接口契约的测试套件。它确保 platform 分区与 vendor 分区之间的 Treble 兼容性。

**Vulkan**
: 低开销、跨平台 3D 图形 API。Android 支持 Vulkan 作为 OpenGL ES 的替代方案，提供对 GPU 资源、command buffer 和同步的显式控制。

**WMS**（WindowManagerService）
: 管理窗口位置、Z 顺序、过渡和输入焦点的系统服务。它与 SurfaceFlinger 紧密协作，控制屏幕上可见内容。

**Zygote**
: 所有 Android 应用进程的父进程。它预加载常用类和资源，使新应用进程可以通过 copy-on-write 内存共享快速启动。

---

> **交叉引用**：各术语会在其主要主题对应章节中详细讨论。关键源码文件位置另见**附录 A**。
