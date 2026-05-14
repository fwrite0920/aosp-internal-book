# 附录 A：关键文件参考

本附录提供 AOSP 中最重要源码文件的快速参考表，按子系统组织，并交叉引用到讨论这些文件的章节。路径均相对于 AOSP 根目录（`$AOSP/`）。

---

## 构建系统（第 2 章）

| 文件路径 | 用途 |
|-----------|---------|
| `build/make/core/main.mk` | 顶层构建入口；包含所有其他 makefile |
| `build/make/core/Makefile` | 镜像、OTA 和打包的旧式构建规则 |
| `build/make/core/definitions.mk` | 整个构建系统共用的宏定义 |
| `build/make/core/envsetup.mk` | 构建配置的环境变量设置 |
| `build/make/core/product.mk` | product 级构建变量定义 |
| `build/make/core/product_config.mk` | product 配置加载与校验 |
| `build/make/core/board_config.mk` | board 级硬件配置 |
| `build/make/core/binary.mk` | native 二进制构建的共享规则 |
| `build/make/core/tasks/berberis_test.mk` | native bridge 测试的构建配置 |
| `build/make/envsetup.sh` | shell 环境设置；定义 `lunch`、`m`、`mm`、`mmm` |
| `build/soong/cmd/soong_build/main.go` | Soong 构建系统入口 |
| `build/soong/android/module.go` | Soong 基础模块类型定义 |
| `build/soong/android/androidmk.go` | Android.mk 到 Soong 的转换逻辑 |
| `build/soong/cc/cc.go` | Soong 中 C/C++ 模块构建规则 |
| `build/soong/cc/library.go` | 共享库和静态库构建规则 |
| `build/soong/cc/binary.go` | native 二进制构建规则 |
| `build/soong/cc/config/riscv64_device.go` | RISC-V 64-bit 设备配置 |
| `build/soong/java/java.go` | Soong 中 Java 模块构建规则 |
| `build/soong/java/app.go` | Android 应用构建规则 |
| `build/soong/apex/apex.go` | APEX 模块构建规则 |
| `build/blueprint/context.go` | Blueprint 核心上下文与依赖解析 |
| `build/blueprint/module_ctx.go` | Blueprint 模块上下文接口 |
| `device/generic/goldfish/board/BoardConfigCommon.mk` | 模拟器通用 board 配置 |
| `device/google/cuttlefish/vsoc_x86_64/BoardConfig.mk` | Cuttlefish x86_64 虚拟设备 board 配置 |

## 启动与 Init（第 4 章）

| 文件路径 | 用途 |
|-----------|---------|
| `system/core/init/init.cpp` | PID 1 init 进程主入口 |
| `system/core/init/service.cpp` | 服务生命周期管理，包含 start/stop/restart |
| `system/core/init/service_parser.cpp` | `.rc` 文件中 service 定义的解析 |
| `system/core/init/action.cpp` | action 与 trigger 执行引擎 |
| `system/core/init/action_parser.cpp` | `.rc` 文件中 action 块的解析 |
| `system/core/init/property_service.cpp` | 系统属性守护进程与持久化 |
| `system/core/init/first_stage_init.cpp` | 挂载分区前的 first-stage init |
| `system/core/init/first_stage_mount.cpp` | 早期分区挂载逻辑 |
| `system/core/init/selinux.cpp` | init 期间的 SELinux policy 加载 |
| `system/core/init/ueventd.cpp` | 设备节点创建守护进程 |
| `system/core/init/reboot.cpp` | 关机和重启序列 |
| `system/core/rootdir/init.rc` | 根 init 脚本；定义核心服务与 trigger |
| `system/core/rootdir/init.zygote64_32.rc` | Zygote 启动配置（64+32 位） |
| `system/core/fastboot/fastboot.cpp` | Fastboot 协议 host 侧实现 |
| `bootable/recovery/recovery.cpp` | Recovery 模式主入口 |

## 内核（第 5 章）

| 文件路径 | 用途 |
|-----------|---------|
| `kernel/common/Makefile` | 顶层内核 Makefile |
| `kernel/common/arch/arm64/configs/gki_defconfig` | GKI 默认内核配置 |
| `kernel/common/drivers/android/binder.c` | Binder 内核驱动实现 |
| `kernel/common/drivers/android/binder_alloc.c` | Binder 内存分配 |
| `kernel/common/drivers/staging/android/ion/` | ION 内存分配器（旧） |
| `kernel/common/drivers/dma-buf/` | DMA-BUF buffer 共享框架 |
| `kernel/common/drivers/gpu/drm/` | DRM/KMS 图形驱动框架 |
| `kernel/common/include/uapi/linux/android/binder.h` | Binder UAPI 头文件 |
| `kernel/common/fs/fuse/dev.c` | FUSE 设备实现，用于 scoped storage |
| `kernel/build/build.sh` | 内核构建包装脚本 |
| `kernel/build/kleaf/` | Kleaf（基于 Bazel）内核构建系统 |

## C 库 Bionic 与动态链接器（第 7 章）

| 文件路径 | 用途 |
|-----------|---------|
| `bionic/libc/bionic/malloc_common.cpp` | malloc dispatch，选择 jemalloc/scudo |
| `bionic/libc/bionic/pthread_create.cpp` | POSIX 线程创建 |
| `bionic/libc/bionic/libc_init_dynamic.cpp` | 动态链接进程启动 |
| `bionic/libc/bionic/libc_init_static.cpp` | 静态链接进程启动 |
| `bionic/libc/bionic/system_property_api.cpp` | 系统属性客户端 API |
| `bionic/libc/arch-arm64/` | ARM64 架构专属代码 |
| `bionic/libc/include/` | 公共 C 库头文件 |
| `bionic/linker/linker.cpp` | 动态链接器主逻辑 |
| `bionic/linker/linker_phdr.cpp` | ELF program header 解析与加载 |
| `bionic/linker/linker_namespaces.cpp` | Linker namespace 实现 |
| `bionic/linker/linker_soinfo.cpp` | 共享对象信息管理 |
| `bionic/linker/linker_config.cpp` | Linker 配置文件解析 |
| `system/core/rootdir/etc/ld.config.txt` | 默认 linker namespace 配置 |
| `bionic/libm/` | 数学库实现 |
| `bionic/libdl/libdl.cpp` | `dlopen`/`dlsym` 实现 |

## Binder 进程间通信（第 9 章）

| 文件路径 | 用途 |
|-----------|---------|
| `frameworks/native/libs/binder/IPCThreadState.cpp` | 每线程 Binder transaction 处理 |
| `frameworks/native/libs/binder/ProcessState.cpp` | 每进程 Binder 驱动状态 |
| `frameworks/native/libs/binder/Binder.cpp` | `BBinder` 本地基类 |
| `frameworks/native/libs/binder/BpBinder.cpp` | `BpBinder` proxy 基类 |
| `frameworks/native/libs/binder/Parcel.cpp` | Binder transaction 数据序列化 |
| `frameworks/native/libs/binder/IServiceManager.cpp` | Service manager 客户端接口 |
| `frameworks/native/cmds/servicemanager/ServiceManager.cpp` | Service manager 守护进程 |
| `frameworks/native/cmds/servicemanager/main.cpp` | Service manager 入口 |
| `frameworks/base/core/java/android/os/Binder.java` | Java 侧 Binder 基类 |
| `frameworks/base/core/java/android/os/BinderProxy.java` | Java 侧 Binder proxy |
| `frameworks/base/core/java/android/os/Parcel.java` | Java 侧 Parcel |
| `frameworks/base/core/java/android/os/ServiceManager.java` | Java service manager 客户端 |
| `frameworks/base/core/jni/android_util_Binder.cpp` | Binder JNI 桥接 |

## 硬件抽象层（HAL，第 10 章）

| 文件路径 | 用途 |
|-----------|---------|
| `hardware/interfaces/` | 顶层 HIDL/AIDL HAL 接口目录 |
| `hardware/interfaces/audio/aidl/` | Audio HAL AIDL 接口定义 |
| `hardware/interfaces/camera/provider/aidl/` | Camera provider HAL 接口 |
| `hardware/interfaces/graphics/composer/aidl/` | HWC（Hardware Composer）HAL 接口 |
| `hardware/interfaces/graphics/allocator/aidl/` | Gralloc allocator HAL 接口 |
| `hardware/interfaces/graphics/mapper/stable-c/` | Gralloc mapper stable-C HAL 接口 |
| `hardware/interfaces/health/aidl/` | Battery/health HAL 接口 |
| `hardware/interfaces/sensors/aidl/` | Sensors HAL 接口 |
| `hardware/interfaces/neuralnetworks/aidl/` | NNAPI HAL 接口 |
| `hardware/interfaces/power/aidl/` | Power HAL 接口 |
| `hardware/interfaces/thermal/aidl/` | Thermal HAL 接口 |
| `hardware/interfaces/bluetooth/aidl/` | Bluetooth HAL 接口 |
| `hardware/interfaces/wifi/aidl/` | Wi-Fi HAL 接口 |
| `hardware/interfaces/vibrator/aidl/` | Vibrator HAL 接口 |
| `hardware/libhardware/include/hardware/hardware.h` | 旧 HAL 模块接口（`hw_module_t`） |
| `system/libhidl/transport/HidlTransportSupport.cpp` | HIDL transport 初始化 |
| `system/tools/hidl/` | HIDL 编译器（`hidl-gen`） |
| `system/tools/aidl/` | HAL 接口 AIDL 编译器 |

## 原生开发工具包（NDK，第 11 章）

| 文件路径 | 用途 |
|-----------|---------|
| `frameworks/native/include/android/` | 公共 NDK native 头文件 |
| `frameworks/native/libs/nativewindow/include/android/native_window.h` | `ANativeWindow` API |
| `frameworks/native/include/android/native_activity.h` | `NativeActivity` API |
| `frameworks/native/include/android/sensor.h` | Sensor NDK API |
| `frameworks/native/include/android/asset_manager.h` | Asset manager NDK API |
| `frameworks/av/media/ndk/` | Media NDK 实现，例如 `AMediaCodec` |
| `packages/modules/NeuralNetworks/runtime/` | NNAPI runtime 实现 |
| `frameworks/native/libs/nativewindow/` | `ANativeWindow` 实现 |

## 原生服务（第 12 章）

| 文件路径 | 用途 |
|-----------|---------|
| `frameworks/native/services/inputflinger/InputDispatcher.cpp` | 将输入事件分发给窗口 |
| `frameworks/native/services/inputflinger/InputReader.cpp` | 输入设备事件读取 |
| `frameworks/native/services/inputflinger/InputManager.cpp` | 输入子系统协调器 |
| `frameworks/native/services/sensorservice/SensorService.cpp` | 传感器事件多路复用 |
| `frameworks/native/services/surfaceflinger/main_surfaceflinger.cpp` | SurfaceFlinger 进程入口 |
| `system/logging/logd/SerializedLogBuffer.cpp` | 系统日志环形缓冲区 |
| `system/memory/lmkd/lmkd.cpp` | Low memory killer daemon |
| `system/memory/lmkd/` | 现代 LMKD 实现 |
| `system/core/healthd/` | Battery/health 守护进程 |
| `system/netd/server/NetdNativeService.cpp` | 网络守护进程 native 服务 |

## 图形与渲染管线（第 13 章）

| 文件路径 | 用途 |
|-----------|---------|
| `frameworks/native/services/surfaceflinger/SurfaceFlinger.cpp` | 合成器主类 |
| `frameworks/native/services/surfaceflinger/SurfaceFlinger.h` | SurfaceFlinger 声明 |
| `frameworks/native/services/surfaceflinger/Scheduler/Scheduler.cpp` | VSYNC 调度与帧节奏 |
| `frameworks/native/services/surfaceflinger/Scheduler/VsyncController.cpp` | VSYNC 信号生成 |
| `frameworks/native/services/surfaceflinger/CompositionEngine/` | 合成策略引擎 |
| `frameworks/native/services/surfaceflinger/DisplayHardware/HWComposer.cpp` | HWC 抽象层 |
| `frameworks/native/services/surfaceflinger/DisplayHardware/PowerAdvisor.cpp` | Power hint 集成 |
| `frameworks/native/services/surfaceflinger/Layer.cpp` | 单个 surface/layer 管理 |
| `frameworks/native/services/surfaceflinger/BufferLayer.cpp` | 基于 buffer 的 layer 实现 |
| `frameworks/native/services/surfaceflinger/FrontEnd/LayerLifecycleManager.cpp` | Layer 生命周期跟踪 |
| `frameworks/native/services/surfaceflinger/Tracing/TransactionTracing.cpp` | Transaction trace 捕获 |
| `frameworks/native/libs/gui/Surface.cpp` | 客户端 Surface 实现 |
| `frameworks/native/libs/gui/BufferQueue.cpp` | 生产者-消费者 buffer queue |
| `frameworks/native/libs/gui/BufferQueueProducer.cpp` | Buffer queue 生产者侧 |
| `frameworks/native/libs/gui/BufferQueueConsumer.cpp` | Buffer queue 消费者侧 |
| `frameworks/native/libs/gui/SurfaceComposerClient.cpp` | SurfaceFlinger 客户端接口 |
| `frameworks/native/libs/gui/BLASTBufferQueue.cpp` | BLAST buffer queue 现代路径 |
| `frameworks/native/libs/renderengine/skia/SkiaGLRenderEngine.cpp` | 基于 Skia 的 GPU 合成 |
| `frameworks/native/libs/renderengine/skia/SkiaVkRenderEngine.cpp` | Skia Vulkan render engine |
| `frameworks/native/opengl/libs/EGL/eglApi.cpp` | EGL API 入口 |
| `frameworks/native/opengl/libs/EGL/Loader.cpp` | EGL 驱动加载器 |
| `frameworks/native/vulkan/libvulkan/driver.cpp` | Vulkan loader/driver 接口 |
| `frameworks/native/vulkan/libvulkan/api.cpp` | Vulkan API dispatch |
| `external/skia/src/gpu/ganesh/GrDirectContext.cpp` | Skia GPU context |
| `external/skia/src/gpu/graphite/` | Skia Graphite，下一代 GPU backend |
| `frameworks/base/libs/hwui/renderthread/RenderThread.cpp` | HWUI render thread |
| `frameworks/base/libs/hwui/renderthread/CanvasContext.cpp` | 每窗口 render context |
| `frameworks/base/libs/hwui/pipeline/skia/SkiaOpenGLPipeline.cpp` | Skia GL 渲染管线 |
| `frameworks/base/libs/hwui/pipeline/skia/SkiaVulkanPipeline.cpp` | Skia Vulkan 渲染管线 |
| `frameworks/base/libs/hwui/RenderNode.cpp` | Display list render node |
| `frameworks/base/libs/hwui/RecordingCanvas.cpp` | Display list recording canvas |
| `frameworks/base/libs/hwui/DamageAccumulator.cpp` | 脏区域跟踪 |
| `frameworks/base/libs/hwui/JankTracker.cpp` | 帧卡顿检测与上报 |
| `frameworks/base/graphics/java/android/graphics/Canvas.java` | Java Canvas API |
| `frameworks/base/graphics/java/android/graphics/RenderNode.java` | Java RenderNode API |
| `frameworks/base/core/java/android/view/Choreographer.java` | 基于 VSYNC 的 callback 调度器 |
| `frameworks/base/core/java/android/view/ViewRootImpl.java` | View 层级根节点；驱动 measure/layout/draw |
| `frameworks/base/core/java/android/view/ThreadedRenderer.java` | 到 HWUI RenderThread 的 Java 桥 |

## 动画系统（第 14 章）

| 文件路径 | 用途 |
|-----------|---------|
| `frameworks/base/core/java/android/animation/ValueAnimator.java` | 核心属性动画引擎 |
| `frameworks/base/core/java/android/animation/ObjectAnimator.java` | 面向属性目标的动画 |
| `frameworks/base/core/java/android/animation/AnimatorSet.java` | 协调多个动画的顺序与组合 |
| `frameworks/base/core/java/android/view/animation/Animation.java` | 旧 View 动画基类 |
| `frameworks/base/core/java/android/transition/TransitionManager.java` | Scene transition 框架 |
| `frameworks/base/core/java/android/window/TransitionInfo.java` | Shell transition 元数据 |
| `frameworks/libs/systemui/animationlib/src/` | SystemUI 共享动画库 |

## 音频系统（第 15 章）

| 文件路径 | 用途 |
|-----------|---------|
| `frameworks/av/services/audioflinger/AudioFlinger.cpp` | 音频混音守护进程主类 |
| `frameworks/av/services/audioflinger/Threads.cpp` | 播放与录音线程实现 |
| `frameworks/av/services/audioflinger/Tracks.cpp` | 音频 track 管理 |
| `frameworks/av/services/audioflinger/Effects.cpp` | 音频效果链处理 |
| `frameworks/av/services/audiopolicy/managerdefault/AudioPolicyManager.cpp` | 音频路由策略 |
| `frameworks/av/services/audiopolicy/common/managerdefinitions/src/AudioPort.cpp` | 音频端口抽象 |
| `frameworks/av/media/libaudioclient/AudioTrack.cpp` | 客户端音频播放 |
| `frameworks/av/media/libaudioclient/AudioRecord.cpp` | 客户端音频录制 |
| `frameworks/av/media/libaudioclient/AudioSystem.cpp` | 音频系统客户端接口 |
| `frameworks/av/media/libaudiohal/impl/DeviceHalAidl.cpp` | Audio device HAL AIDL 适配器 |
| `frameworks/base/media/java/android/media/AudioTrack.java` | Java 音频播放 API |
| `frameworks/base/services/core/java/com/android/server/audio/AudioService.java` | 音频服务，负责音量和路由 |

## 媒体与视频管线（第 16 章）

| 文件路径 | 用途 |
|-----------|---------|
| `frameworks/av/media/libmediaplayerservice/MediaPlayerService.cpp` | 媒体播放器守护进程 |
| `frameworks/av/media/codec2/sfplugin/CCodec.cpp` | Codec2 framework 插件 |
| `frameworks/av/media/codec2/sfplugin/CCodecBufferChannel.cpp` | Codec2 buffer 管理 |
| `frameworks/av/media/codec2/components/` | 软件 codec 实现 |
| `frameworks/av/media/libstagefright/MediaCodec.cpp` | MediaCodec native 实现 |
| `frameworks/av/media/libstagefright/ACodec.cpp` | 旧 OMX codec 适配器 |
| `frameworks/av/media/libstagefright/NuPlayer/NuPlayer.cpp` | 媒体播放引擎 |
| `frameworks/av/media/module/extractors/` | 媒体文件格式 extractor，例如 MP4、MKV |
| `frameworks/av/services/camera/libcameraservice/CameraService.cpp` | Camera service 守护进程 |
| `frameworks/av/drm/mediadrm/plugins/clearkey/` | ClearKey DRM 参考实现 |
| `frameworks/base/media/java/android/media/MediaCodec.java` | Java MediaCodec API |
| `frameworks/base/media/java/android/media/MediaPlayer.java` | Java MediaPlayer API |

## Android 运行时（ART，第 18 章）

| 文件路径 | 用途 |
|-----------|---------|
| `art/runtime/runtime.cc` | ART runtime 初始化 |
| `art/runtime/class_linker.cc` | 类加载与链接 |
| `art/runtime/interpreter/interpreter.cc` | 字节码解释器入口 |
| `art/runtime/jit/jit.cc` | JIT 编译器协调器 |
| `art/runtime/jit/jit_code_cache.cc` | JIT 编译代码缓存 |
| `art/runtime/gc/heap.cc` | 垃圾回收堆管理 |
| `art/runtime/gc/collector/concurrent_copying.cc` | Concurrent copying GC |
| `art/runtime/thread.cc` | 线程管理 |
| `art/runtime/oat/oat_file.cc` | OAT 文件格式处理 |
| `art/runtime/mirror/object.h` | managed heap 根对象类型 |
| `art/runtime/mirror/class.h` | 类元数据表示 |
| `art/compiler/optimizing/optimizing_compiler.cc` | AOT/JIT optimizing compiler |
| `art/compiler/optimizing/code_generator_arm64.cc` | ARM64 代码生成后端 |
| `art/compiler/optimizing/register_allocator_linear_scan.cc` | 寄存器分配 |
| `art/dex2oat/dex2oat.cc` | Ahead-of-time 编译工具 |
| `art/dex2oat/dex2oat_options.cc` | DEX 到 OAT 编译选项 |
| `art/libdexfile/dex/dex_file.h` | DEX 文件格式定义 |
| `art/runtime/native_bridge_art_interface.cc` | ART 侧 native bridge 集成 |

## 原生桥接与二进制翻译（Native Bridge，第 19 章）

| 文件路径 | 用途 |
|-----------|---------|
| `frameworks/libs/binary_translation/native_bridge/native_bridge.h` | `NativeBridgeCallbacks` 接口（v3-v8） |
| `frameworks/libs/binary_translation/native_bridge/native_bridge.cc` | Native bridge framework 实现 |
| `frameworks/libs/binary_translation/guest_loader/` | guest 库加载与链接 |
| `frameworks/libs/binary_translation/guest_abi/` | host 与 guest 之间的 ABI 转换 |
| `frameworks/libs/binary_translation/guest_state/` | guest CPU 状态抽象 |
| `frameworks/libs/binary_translation/jni/` | JNI trampoline 生成 |
| `frameworks/libs/binary_translation/interpreter/` | guest 指令解释器 |
| `frameworks/libs/binary_translation/decoder/` | guest 指令解码器 |
| `frameworks/libs/binary_translation/backend/` | host 代码生成后端 |
| `frameworks/libs/binary_translation/assembler/` | host 指令汇编器 |
| `frameworks/libs/binary_translation/android_api/` | Android framework proxy stub |
| `frameworks/libs/native_bridge_support/native_bridge_support.mk` | bridge support 的构建同步 |
| `art/libnativebridge/native_bridge.cc` | 系统侧 native bridge 加载 |

## 系统服务进程（system_server，第 20 章）

| 文件路径 | 用途 |
|-----------|---------|
| `frameworks/base/services/java/com/android/server/SystemServer.java` | `system_server` 启动序列 |
| `frameworks/base/services/core/java/com/android/server/SystemServiceManager.java` | 服务生命周期管理器 |
| `frameworks/base/services/core/java/com/android/server/am/ActivityManagerService.java` | Activity Manager Service |
| `frameworks/base/services/core/java/com/android/server/wm/WindowManagerService.java` | Window Manager Service |
| `frameworks/base/services/core/java/com/android/server/wm/ActivityTaskManagerService.java` | Activity Task Manager Service |
| `frameworks/base/services/core/java/com/android/server/pm/PackageManagerService.java` | Package Manager Service |
| `frameworks/base/services/core/java/com/android/server/power/PowerManagerService.java` | 电源管理 |
| `frameworks/base/services/core/java/com/android/server/display/DisplayManagerService.java` | 显示管理 |
| `frameworks/base/services/core/java/com/android/server/input/InputManagerService.java` | 输入管理桥接 |
| `frameworks/base/core/java/com/android/internal/os/ZygoteInit.java` | Zygote 进程初始化 |
| `frameworks/base/core/java/com/android/internal/os/ZygoteConnection.java` | Zygote fork 请求处理 |
| `frameworks/base/core/java/com/android/internal/os/Zygote.java` | Zygote fork 机制 |
| `frameworks/base/core/java/com/android/internal/os/RuntimeInit.java` | 应用进程 runtime 初始化 |

## Activity 与窗口管理（第 22 章）

| 文件路径 | 用途 |
|-----------|---------|
| `frameworks/base/services/core/java/com/android/server/wm/Task.java` | Task（back stack）容器 |
| `frameworks/base/services/core/java/com/android/server/wm/ActivityRecord.java` | 单个 Activity 状态跟踪 |
| `frameworks/base/services/core/java/com/android/server/wm/ActivityStarter.java` | Intent 解析与 Activity 启动 |
| `frameworks/base/services/core/java/com/android/server/wm/ActivityClientController.java` | Activity 生命周期 IPC 处理器 |
| `frameworks/base/services/core/java/com/android/server/wm/RootWindowContainer.java` | 窗口层级根节点 |
| `frameworks/base/services/core/java/com/android/server/wm/TaskFragment.java` | Activity embedding 容器 |
| `frameworks/base/core/java/android/app/Activity.java` | 应用侧 Activity 基类 |
| `frameworks/base/core/java/android/app/ActivityThread.java` | 每个 Android 应用的主线程 |
| `frameworks/base/core/java/android/app/Instrumentation.java` | Activity 生命周期 instrumentation hook |

## 窗口系统（第 23 章）

| 文件路径 | 用途 |
|-----------|---------|
| `frameworks/base/services/core/java/com/android/server/wm/WindowState.java` | 单窗口服务端状态 |
| `frameworks/base/services/core/java/com/android/server/wm/WindowToken.java` | 窗口分组 token |
| `frameworks/base/services/core/java/com/android/server/wm/Session.java` | 每应用 WMS session |
| `frameworks/base/services/core/java/com/android/server/wm/WindowSurfaceController.java` | Window 到 Surface 的桥 |
| `frameworks/base/services/core/java/com/android/server/wm/WindowAnimator.java` | 窗口动画协调器 |
| `frameworks/base/services/core/java/com/android/server/wm/InsetsStateController.java` | 系统 insets 管理 |
| `frameworks/base/services/core/java/com/android/server/wm/InsetsPolicy.java` | Insets 可见性策略 |
| `frameworks/base/core/java/android/view/WindowManager.java` | 客户端 window manager 接口 |
| `frameworks/base/core/java/android/view/WindowManagerImpl.java` | Window manager 实现 |
| `frameworks/base/core/java/android/view/View.java` | 基础 UI 组件，负责 measure/layout/draw |
| `frameworks/base/core/java/android/view/ViewGroup.java` | 子 View 容器 |
| `frameworks/base/core/java/android/view/SurfaceView.java` | 独立 surface 的 View 组件 |

## 显示系统（第 24 章）

| 文件路径 | 用途 |
|-----------|---------|
| `frameworks/base/services/core/java/com/android/server/wm/DisplayContent.java` | 每显示的 window container |
| `frameworks/base/services/core/java/com/android/server/wm/DisplayPolicy.java` | 每显示的窗口策略，包含 bar 和 cutout |
| `frameworks/base/services/core/java/com/android/server/wm/DisplayRotation.java` | 显示旋转处理 |
| `frameworks/base/services/core/java/com/android/server/display/LogicalDisplay.java` | 逻辑显示抽象 |
| `frameworks/base/services/core/java/com/android/server/display/DisplayDeviceInfo.java` | 物理显示属性 |
| `frameworks/base/services/core/java/com/android/server/display/LocalDisplayAdapter.java` | 内建显示适配器 |

## 包管理服务（PackageManagerService，第 26 章）

| 文件路径 | 用途 |
|-----------|---------|
| `frameworks/base/services/core/java/com/android/server/pm/PackageManagerService.java` | 包管理核心 |
| `frameworks/base/services/core/java/com/android/server/pm/Settings.java` | 包设置持久化 |
| `frameworks/base/services/core/java/com/android/server/pm/InstallPackageHelper.java` | 包安装逻辑 |
| `frameworks/base/services/core/java/com/android/server/pm/PackageInstallerService.java` | 安装器 session 管理 |
| `frameworks/base/services/core/java/com/android/server/pm/permission/PermissionManagerService.java` | 运行时权限管理 |
| `frameworks/base/services/core/java/com/android/server/pm/pkg/parsing/ParsingPackageUtils.java` | APK manifest 解析 |
| `frameworks/base/services/core/java/com/android/server/pm/resolution/ComponentResolver.java` | Intent filter 解析 |
| `frameworks/base/services/core/java/com/android/server/pm/dex/DexManager.java` | DEX 文件优化跟踪 |
| `frameworks/base/core/java/android/content/pm/PackageManager.java` | 公共 PackageManager API |

## 安全（第 40 章）

| 文件路径 | 用途 |
|-----------|---------|
| `system/sepolicy/public/` | 公共 SELinux policy 定义 |
| `system/sepolicy/private/` | 私有 platform SELinux policy |
| `system/sepolicy/vendor/` | Vendor SELinux policy |
| `system/security/keystore2/` | Keystore2 服务（Rust） |
| `system/security/identity/` | Identity credential 服务 |
| `external/selinux/` | SELinux 用户态工具 |
| `system/extras/verity/` | dm-verity 工具 |
| `system/core/fs_mgr/libfs_avb/` | AVB（Android Verified Boot）集成 |
| `frameworks/base/services/core/java/com/android/server/biometrics/` | 生物识别认证 |
| `frameworks/base/keystore/java/android/security/keystore2/` | Keystore Java API |

## 系统界面（SystemUI，第 47 章）

| 文件路径 | 用途 |
|-----------|---------|
| `frameworks/base/packages/SystemUI/src/com/android/systemui/SystemUIApplication.java` | SystemUI 应用入口 |
| `frameworks/base/packages/SystemUI/src/com/android/systemui/statusbar/phone/CentralSurfacesImpl.java` | 状态栏与通知栏 |
| `frameworks/base/packages/SystemUI/src/com/android/systemui/qs/QSPanelController.java` | Quick Settings 面板控制器 |
| `frameworks/base/packages/SystemUI/src/com/android/systemui/recents/OverviewProxyService.java` | 到 Launcher 的 Recents/overview proxy |
| `frameworks/base/packages/SystemUI/src/com/android/systemui/keyguard/KeyguardViewMediator.java` | 锁屏协调器 |
| `frameworks/base/packages/SystemUI/src/com/android/systemui/navigationbar/NavigationBar.java` | 导航栏 |
| `frameworks/base/packages/SystemUI/src/com/android/systemui/volume/VolumeDialogControllerImpl.java` | 音量对话框逻辑 |
| `frameworks/base/packages/SystemUI/src/com/android/systemui/shade/NotificationPanelViewController.java` | 通知面板控制器 |

## 启动器（Launcher3，第 48 章）

| 文件路径 | 用途 |
|-----------|---------|
| `packages/apps/Launcher3/src/com/android/launcher3/Launcher.java` | Launcher 主 Activity |
| `packages/apps/Launcher3/src/com/android/launcher3/Workspace.java` | 主屏 workspace |
| `packages/apps/Launcher3/src/com/android/launcher3/allapps/AllAppsContainerView.java` | All-apps 抽屉 |
| `packages/apps/Launcher3/src/com/android/launcher3/model/LoaderTask.java` | 应用列表加载 |
| `packages/apps/Launcher3/src/com/android/launcher3/dragndrop/DragController.java` | 拖放协调器 |
| `packages/apps/Launcher3/quickstep/src/com/android/quickstep/RecentsActivity.java` | Recents（overview）Activity |
| `packages/apps/Launcher3/quickstep/src/com/android/quickstep/TouchInteractionService.java` | 手势导航服务 |

## 设置应用（Settings，第 49 章）

| 文件路径 | 用途 |
|-----------|---------|
| `packages/apps/Settings/src/com/android/settings/Settings.java` | Settings 主 Activity |
| `packages/apps/Settings/src/com/android/settings/dashboard/DashboardFragment.java` | Preference dashboard 基类 |
| `packages/apps/Settings/src/com/android/settings/search/SearchFeatureProvider.java` | Settings 搜索 |
| `packages/apps/Settings/src/com/android/settings/biometrics/` | 生物识别录入 |

## 伴随设备管理器与虚拟设备（CompanionDeviceManager，第 51 章）

| 文件路径 | 用途 |
|-----------|---------|
| `frameworks/base/services/companion/java/com/android/server/companion/CompanionDeviceManagerService.java` | CDM 服务 |
| `frameworks/base/services/companion/java/com/android/server/companion/virtual/VirtualDeviceManagerService.java` | VDM 服务 |

## Mainline 模块（第 52 章）

| 文件路径 | 用途 |
|-----------|---------|
| `packages/modules/Wifi/` | Wi-Fi Mainline 模块 |
| `packages/modules/Bluetooth/` | Bluetooth Mainline 模块 |
| `packages/modules/NetworkStack/` | Network stack Mainline 模块 |
| `packages/modules/Permission/` | Permission controller 模块 |
| `packages/modules/MediaProvider/` | Media storage provider 模块 |
| `packages/modules/adb/` | ADB Mainline 模块 |
| `packages/modules/common/` | 共享 Mainline 模块基础设施 |
| `system/apex/apexd/` | APEX daemon，模块安装器 |
| `system/apex/apexd/apexd.cpp` | APEX 安装与激活 |
| `system/apex/libs/libapexutil/` | APEX utility 库 |

## 虚拟化框架（第 54 章）

| 文件路径 | 用途 |
|-----------|---------|
| `packages/modules/Virtualization/` | Android Virtualization Framework 顶层目录 |
| `packages/modules/Virtualization/android/virtualizationservice/` | VM 生命周期管理 |
| `packages/modules/Virtualization/build/microdroid/` | 最小 guest OS（Microdroid）构建文件 |
| `packages/modules/Virtualization/guest/pvmfw/` | Protected VM firmware |
| `packages/modules/Virtualization/libs/libvm_payload/` | Guest payload 接口 |

## 测试（第 55 章）

| 文件路径 | 用途 |
|-----------|---------|
| `test/vts/` | Vendor Test Suite 顶层目录 |
| `cts/tests/` | Compatibility Test Suite 测试 |
| `tools/tradefederation/core/` | Trade Federation 测试框架核心 |
| `tools/tradefederation/core/src/com/android/tradefed/` | TradeFed 框架类 |
| `platform_testing/tests/` | 平台集成测试 |
| `frameworks/base/core/tests/` | Framework core 单元测试 |
| `frameworks/base/test-runner/` | Android test runner 框架 |

## 架构支持（第 57 章）

| 文件路径 | 用途 |
|-----------|---------|
| `build/soong/cc/config/arm64_device.go` | ARM64 工具链：arch variant、CPU 调优、PAC/BTI |
| `build/soong/cc/config/arm_device.go` | ARM 32-bit 工具链：Thumb/ARM、errata workaround |
| `build/soong/cc/config/x86_device.go` | x86 32-bit 工具链：SSE、stack realignment |
| `build/soong/cc/config/x86_64_device.go` | x86_64 工具链：微架构 variant |
| `build/soong/cc/config/riscv64_device.go` | RISC-V 64-bit 工具链：ISA 扩展 |
| `build/soong/cc/config/toolchain.go` | 工具链接口与工厂注册 |
| `build/soong/cc/config/global.go` | 全架构通用编译器/链接器 flag |
| `build/soong/cc/config/bionic.go` | Bionic CRT 对象和默认共享库 |
| `build/soong/cc/config/clang.go` | Clang unknown-flags filter |
| `build/soong/android/arch.go` | Arch struct、ArchType 和 multilib 解码逻辑 |
| `bionic/libc/arch-arm64/ifuncs.cpp` | ARM64 ifunc dispatcher，选择 MTE/SVE |
| `art/runtime/arch/riscv64/instruction_set_features_riscv64.h` | ART RISC-V 特性检测 |
| `art/runtime/arch/arm64/instruction_set_features_arm64.h` | ART ARM64 特性位图和 errata |

## 模拟器（第 58 章）

| 文件路径 | 用途 |
|-----------|---------|
| `external/qemu/android/emulation/` | Emulator 核心模拟逻辑 |
| `external/qemu/android/android-emu/android/emulation/` | Emulator 硬件模拟 |
| `device/generic/goldfish/` | Goldfish 虚拟设备定义 |
| `device/google/cuttlefish/` | Cuttlefish 虚拟设备定义 |
| `device/google/cuttlefish/host/commands/run_cvd/` | Cuttlefish launcher |
| `external/crosvm/` | CrosVM 虚拟机监控器 |
| `external/qemu/android/android-grpc/` | Emulator gRPC 控制接口 |

## 车载、电视与穿戴（Automotive、TV 与 Wear，第 60 章）

| 文件路径 | 用途 |
|-----------|---------|
| `packages/services/Car/` | Android Automotive 服务层 |
| `packages/services/Car/service/src/com/android/car/CarServiceImpl.java` | Automotive car service |
| `packages/apps/Car/Launcher/` | Automotive launcher |
| `device/google/atv/` | Android TV 设备配置 |
| `packages/apps/TvSettings/` | TV settings 应用 |
| `prebuilts/sdk/opt/wear/` | Wear OS SDK prebuilts |

---

> **Note**：路径会随 AOSP 分支变化。上表面向 2026 年初的 AOSP `main`。请使用 `find` 或 `cs.android.com` 对照你检出的分支验证。
