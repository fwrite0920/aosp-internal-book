# 第 18 章：ART Runtime

ART（Android Runtime）是 Android 应用执行、类加载、垃圾回收、JIT/AOT 编译、JNI 桥接和运行时调试的核心执行环境。它负责把 DEX 字节码转换为可执行机器码，协调解释器与编译器、维护对象内存表示、执行类链接与验证，并在系统启动、应用启动与运行时持续优化程序行为。本章从 AOSP 源码视角梳理 ART 的架构、DEX 格式、dex2oat、JIT、GC、类加载、JNI、odrefresh 和调试体系。

---

## 18.1 ART 架构

### 18.1.1 目录布局

ART 关键源码通常分布在以下目录：

| 路径 | 用途 |
|------|------|
| `art/runtime/` | 运行时核心、线程、对象模型、GC、类链接 |
| `art/dex2oat/` | AOT 编译器入口与驱动 |
| `art/compiler/` | 优化编译器与后端 |
| `art/libdexfile/` | DEX 解析与访问库 |
| `art/libartbase/` | 基础工具库 |
| `art/odrefresh/` | OTA 后编译产物刷新 |
| `art/tools/` | 调试与分析工具 |

### 18.1.2 运行时单例

ART 通过 `Runtime` 单例维护全局状态，包括：

- 线程列表与线程本地状态
- 类链接器与 dex 缓存
- 垃圾回收器与堆
- JIT/AOT 配置
- 信号链与异常机制
- 调试与 instrumentation 子系统

### 18.1.3 运行时启动序列

ART 启动大致经历以下阶段：

1. 解析运行时参数。
2. 创建 `Runtime` 单例。
3. 初始化堆、类链接器、线程系统和 signal chain。
4. 加载 boot image 和核心类。
5. 准备解释器/JIT/AOT entrypoints。
6. 进入 Zygote 或应用进程主流程。

### 18.1.4 Zygote 与进程模型

Android 通过 Zygote 预加载类、资源和 boot image，再 fork 应用进程。ART 需要确保 fork 后的运行时状态、JIT 策略、线程模型和 class loader 行为符合每个 app 的独立执行要求。

### 18.1.5 App Images

App image 是 ART 为应用预布局的一部分类与对象映像，可减少启动时类初始化和对象分配成本，从而提升冷启动性能。

### 18.1.6 编译管线概览

ART 编译管线包括：

- 安装时 dexopt / dex2oat
- profile-guided compilation
- 运行时 JIT
- OTA 后 odrefresh

这些路径共同构成 Android 的分层优化体系。

### 18.1.7 执行模式

ART 典型执行模式包括：

- 解释执行
- JIT 编译执行
- AOT 编译执行
- 混合模式

同一进程中的不同方法可以处于不同执行形态。

### 18.1.8 Nterp：快速解释器

Nterp 是 ART 的高性能解释器实现，目标是在不触发编译的情况下提供更快的字节码执行路径，缩小解释器与 JIT 之间的性能差距。

### 18.1.9 线程模型

ART 线程模型围绕 `Thread` 对象、suspend points、mutator state 和线程列表展开。Java 线程、GC 线程、JIT 线程和调试线程都共享这一基础设施。

### 18.1.10 锁基础设施

ART 使用互斥锁、读写锁、条件变量和专用锁等级系统维护运行时一致性，同时避免死锁和暂停时间失控。

### 18.1.11 Signal Chain Library

Signal chain 允许 ART 处理崩溃、空指针、调试和 instrumentation 相关信号，同时与应用自身 native signal handler 共存。

### 18.1.12 异常处理

异常处理涉及解释器、编译代码、栈展开、catch 查找和 JNI 边界传播，是运行时控制流的重要组成部分。

### 18.1.13 Monitor 与同步

ART 的 `monitor` 实现支撑 Java `synchronized` 语义，并处理竞争、等待/唤醒和对象锁升级。

#### Thin Locks vs Fat Locks

轻量锁适用于低竞争快速路径；在高竞争或需要 wait/notify 时会膨胀为 fat lock。

#### Monitor Pool

Monitor pool 管理膨胀后的 monitor 对象，避免频繁系统分配开销。

### 18.1.14 Intrinsics

ART 为若干核心方法提供 intrinsic 实现，使解释器、JIT 或 AOT 编译器可以直接替换为更高效指令序列。

### 18.1.15 内存表示

#### 对象布局

对象通常包含 lock word、类指针以及实例字段，是 GC、同步与类元数据访问的基础。

#### 数组布局

数组对象在头部后保存长度和元素区域，布局需兼顾对齐和访问效率。

#### 字符串布局

字符串对象的内部布局影响 hash、长度、字符存储与内存占用，是运行时高频热点之一。

### 18.1.16 关键数据结构

#### `ArtMethod`

`ArtMethod` 描述方法元数据、入口点、访问标志和与 dex/class 相关的关联信息，是 ART 的核心结构之一。

#### `ArtMethod` 入口点

入口点包括解释器入口、quick compiled code 入口、JNI 入口等，用于决定方法执行时实际跳转位置。

#### `mirror::Class`

`mirror::Class` 是 Java 类对象在 ART 中的运行时表示，包含状态、字段、方法表、接口表等信息。

#### `DexCache`

DexCache 缓存字符串、类型、字段和方法解析结果，减少重复解析成本。

#### `InternTable`

InternTable 维护 interned strings，支持字符串驻留与复用。

#### `LinearAlloc`

LinearAlloc 用于某些元数据和运行时结构的线性分配，降低碎片与复杂管理开销。

---

## 18.2 DEX 文件格式

### 18.2.1 头部结构

DEX header 包含 magic、checksum、签名、文件大小、header 大小、endianness、各类 section 偏移与大小等关键信息。

### 18.2.2 文件布局

DEX 文件通常包含 header、string/type/proto/field/method/class 索引表、data section 和 map list。

### 18.2.3 索引表

索引表为 DEX 中的字符串、类型、方法、字段和原型提供统一索引访问，是字节码解析的基础。

### 18.2.4 `ClassDef` 与类数据

ClassDef 描述类声明，类数据部分则编码字段与方法定义、访问标志和 code item 索引。

### 18.2.5 `CodeItem` —— 方法字节码

CodeItem 存放寄存器数量、输入/输出寄存器、try/catch 信息和实际 DEX 指令流。

### 18.2.6 Map Item Types

Map list 用于声明数据区中各类 section 的位置和数量，使解析器可遍历整个文件结构。

### 18.2.7 类型描述符

DEX 使用描述符表达类型，例如基本类型、对象类型、数组类型与方法原型签名。

### 18.2.8 Hidden API 数据

Android 在 DEX 或相关元数据中维护 hidden API 限制信息，用于运行时访问控制与兼容策略。

### 18.2.9 Method Handle 与 Call Site 项

这些结构支撑 `invoke-polymorphic`、`invoke-custom` 和较现代的动态调用语义。

### 18.2.10 DEX 字节码指令

#### Move Instructions

数据移动、寄存器复制与结果搬运指令。

#### Return Instructions

方法返回相关指令。

#### Const Instructions

常量加载与字面量构造。

#### 实例与静态操作

字段读写、静态字段访问与对象成员操作。

#### Invoke Instructions

虚方法、直接方法、接口方法与静态方法调用。

#### 算术与逻辑

整数、长整型、浮点和位运算指令。

#### 比较与分支

条件跳转、比较和 switch 流控制。

#### 数组操作

数组读写、长度访问与填充。

#### 对象操作

对象创建、类型判断、强转等。

### 18.2.11 MUTF-8 字符串编码

DEX 使用 Modified UTF-8 存储字符串，以兼顾 Java 语义和紧凑表示。

### 18.2.12 LEB128 编码

LEB128 用于可变长整数编码，广泛用于 class data 和 debug info 中。

### 18.2.13 注解

DEX 支持类、字段、方法、参数等多层级注解存储。

### 18.2.14 调试信息

调试信息包含行号、局部变量与位置映射，用于栈追踪、调试器和工具链分析。

### 18.2.15 DEX 文件走读

理解一个真实 DEX 文件，通常从 header 开始，沿索引表找到类定义，再深入到方法 code item 和调试信息。

### 18.2.16 Standard DEX 与 Compact DEX

Compact DEX 是更紧凑的派生格式，用于特定系统优化场景。ART 需要同时支持标准与紧凑形式的加载。

### 18.2.17 DEX 文件校验

ART 在加载 DEX 时会执行完整性与结构校验，防止损坏或恶意构造文件进入执行路径。

### 18.2.18 `DexFile` 类 API

`DexFile` 提供遍历索引、读取 class/method/code item 和辅助解析的核心 API，是 class linker 和 verifier 的基础工具。

---

## 18.3 编译：dex2oat

### 18.3.1 架构

`dex2oat` 是 ART 的 AOT 编译器前端与驱动程序，负责把 DEX 编译为 OAT/VDEX，并可生成 image 文件。

### 18.3.2 dex2oat 入口

入口函数会解析参数、准备运行时、加载输入 dex、设置编译选项并调用编译驱动执行实际工作。

### 18.3.3 编译过滤器

常见 compiler filter 包括：

- `verify`
- `quicken`
- `speed-profile`
- `speed`
- `everything` 或近似全编译模式

过滤器决定编译成本、文件大小与运行时性能的平衡。

### 18.3.4 Profile-Guided Compilation（`speed-profile`）

PGO 根据运行时 profile 只编译热点代码，兼顾启动速度、文件大小和执行性能，是 Android 常用默认策略之一。

### 18.3.5 Boot Image 编译

Boot image 编译会把核心类库与预初始化对象放入共享镜像，供 Zygote 和 app 进程复用。

### 18.3.6 输出文件格式

#### OAT 文件

OAT 存放已编译代码、元数据、dex 引用和运行时辅助信息。

#### VDEX 文件

VDEX 存放验证数据、去 quicken 信息和与 DEX 相关的辅助内容。

### 18.3.7 编译管线内部

编译过程包括 DEX 加载、验证、IR 构建、优化、代码生成、链接和输出文件写入。

### 18.3.8 `CompilerDriver`

`CompilerDriver` 统筹编译流程，管理线程池、任务分发、verification、AOT 编译和输出收集。

#### `CompilerOptions`

该对象封装 ISA、filter、debuggable、PIC、image 编译等配置项。

### 18.3.9 面向 AOT 的优化编译器

AOT 编译器会在编译时完成更多静态优化，以减少运行期开销。

### 18.3.10 链接器与镜像写入器

链接阶段负责把编译结果与镜像布局结合，生成可加载的 OAT/image 产物。

### 18.3.11 编译期验证

在编译期完成验证可减少运行时验证成本，并提前发现非法字节码或不安全访问模式。

### 18.3.12 Transaction Mode

某些编译与 image 构建阶段需要 transaction mode，以确保失败时可回滚或保持一致性。

### 18.3.13 AOT Class Linker

AOT 场景下类链接器会以更偏静态的方式处理类解析和布局，为镜像生成提供支持。

### 18.3.14 SDK Checker

SDK checker 用于确保编译路径与 API 约束、hidden API 策略和兼容要求一致。

### 18.3.15 dex2oat 参数处理

参数处理涵盖输入 dex、boot classpath、ISA、compiler filter、swap file、image 路径和 watchdog 等配置。

### 18.3.16 OAT 文件结构（详细）

OAT 文件除机器码外，还包含 header、dex file metadata、类状态、方法偏移等多类结构。

### 18.3.17 多 Image 编译

系统可能为多个 ISA 或不同镜像片段执行多 image 编译，以适配设备和模块化需求。

### 18.3.18 Watchdog

Watchdog 用于监控长时间运行的编译任务，防止编译器卡住影响系统稳定性。

### 18.3.19 Swap File

对大型编译任务，dex2oat 可使用 swap file 降低内存峰值占用。

---

## 18.4 JIT 编译器

### 18.4.1 JIT 架构

JIT 编译器在应用运行过程中根据热点方法动态编译机器码，实现启动成本与长期性能的平衡。

### 18.4.2 `Jit` 类

`Jit` 类管理 JIT 编译器实例、profile、代码缓存、线程池和编译请求入口。

### 18.4.3 方法 profiling 与热度

ART 通过 hotness 计数、inline cache、profile saver 等机制决定哪些方法值得编译。

### 18.4.4 JIT 线程池

JIT 使用后台线程池编译热点方法，减少对 mutator 线程的直接阻塞。

### 18.4.5 JIT 编译器接口

JIT 编译接口负责接收方法、构建 IR、执行优化并把生成代码安装到代码缓存与方法入口点。

### 18.4.6 编译流程

典型流程为：解释执行收集热度 → 达到阈值 → 提交编译任务 → 编译生成代码 → 更新入口点 → 后续走编译代码执行。

### 18.4.7 模式匹配

JIT 会识别热点调用模式、类型反馈和内联机会，以生成更高质量代码。

### 18.4.8 On-Stack Replacement（OSR）

OSR 允许正在执行的循环或方法中途切换到已编译代码，提高热点长循环收益。

### 18.4.9 JIT 代码缓存

代码缓存存放生成的机器码、相关元数据和入口点映射，容量有限，需要回收与管理。

### 18.4.10 分层编译

ART 会结合解释器、JIT 与 AOT 形成分层编译策略，按方法热度逐步升级执行形态。

### 18.4.11 Zygote JIT 编译

在特定策略下，Zygote 阶段也可能进行有限 JIT 工作，以提高共享热点代码的收益。

### 18.4.12 优化编译器

JIT 与 AOT 共享 ART optimizing compiler 的大部分 IR 和优化能力。

### 18.4.13 优化编译器 Pass 细节

#### Inlining（`inliner.cc`）

内联小函数或热点调用，减少调用开销并暴露更多优化机会。

#### Constant Folding（`constant_folding.cc`）

编译期折叠常量表达式。

#### Dead Code Elimination（`dead_code_elimination.cc`）

移除不可达或无副作用死代码。

#### Bounds Check Elimination（`bounds_check_elimination.cc`）

移除可证明安全的数组边界检查。

#### Code Sinking（`code_sinking.cc`）

把指令下沉到更合适位置，减少热路径负担。

#### Write Barrier Elimination（`write_barrier_elimination.cc`）

在安全前提下移除冗余写屏障。

#### Constructor Fence Redundancy Elimination

优化构造函数中的冗余内存屏障。

#### Control Flow Simplification（`control_flow_simplifier.cc`）

简化控制流图结构，便于后续优化。

#### SSA 优化

基于 SSA 形式执行更强的数据流分析与值传播。

#### Register Allocation（`register_allocator_linear_scan.cc`）

为目标 ISA 分配物理寄存器，是后端代码生成关键步骤。

#### 架构相关优化

不同 CPU 架构会应用特定指令选择与优化策略。

### 18.4.14 Entrypoints

#### Quick Entrypoints（`quick_entrypoints.h`）

Quick entrypoints 提供常用运行时辅助调用入口。

#### Runtime ASM Entrypoints（`runtime_asm_entrypoints.h`）

汇编入口点处理方法调用、异常、栈框架和特定快速路径。

### 18.4.15 Inline Caches

Inline cache 记录调用点实际接收类型，帮助 JIT 做去虚拟化和内联判断。

### 18.4.16 `ProfilingInfo`

ProfilingInfo 保存方法运行时行为数据，是 JIT 决策的重要输入。

### 18.4.17 JIT 内存区域

JIT 需要管理专用可执行内存区域，并在安全与性能之间平衡代码缓存生命周期。

### 18.4.18 JIT 代码垃圾回收

当代码缓存接近上限时，ART 会回收不再热点或失效的编译代码。

### 18.4.19 Profile 文件格式

Profile 文件记录热点方法、类和调用站点信息，是 PGO 的输入来源。

### 18.4.20 编译原因

不同编译原因会影响策略，例如启动优化、后台优化、profile 命中或热度触发。

### 18.4.21 `ProfileSaver`

ProfileSaver 后台持久化热点信息，使后续 dexopt/dex2oat 能进行基于 profile 的编译。

---

## 18.5 垃圾回收

### 18.5.1 GC 架构概览

ART GC 必须在吞吐量、暂停时间、内存占用和移动对象能力之间取得平衡。

### 18.5.2 收集器类型

ART 提供多种 GC collector，例如 concurrent copying、mark-compact 与代际收集等策略。

### 18.5.3 分配器类型

分配器策略影响对象分配速度、碎片与 GC 配合方式。

### 18.5.4 记账基础设施

#### Card Table（`card_table.h`）

记录跨代或跨区域写入的脏卡信息。

#### Space Bitmap（`space_bitmap.h`）

表示对象是否被标记或已分配。

#### Mod Union Table（`mod_union_table.h`）

用于某些空间间引用跟踪。

#### Read Barrier Table（`read_barrier_table.h`）

支撑并发复制和读屏障语义。

### 18.5.5 并发复制收集器

Concurrent Copying（CC）是现代 ART 的关键 GC 实现之一。

#### CC 收集阶段

包括标记、复制、引用更新和清理等阶段。

#### 读屏障

读屏障帮助 mutator 在线程并发访问对象时看到正确版本。

#### 转发指针

转发指针用于标识对象已被移动到新位置。

#### Immune Spaces

某些空间在一次 GC 中可被视为 immune，减少扫描成本。

#### Mark Stack 处理

标记栈推进是可达性分析核心环节。

### 18.5.6 代际收集

Generational GC 利用“新对象更可能死亡”的经验优化年轻代回收效率。

### 18.5.7 Heap Spaces

#### RegionSpace

适合并发复制与区域化管理。

#### Thread-Local Allocation Buffers（TLABs）

为线程提供快速分配缓冲区，减少锁竞争。

#### NonMovingSpace

存放不宜移动或需要稳定地址的对象。

#### LargeObjectSpace

大对象通常进入独立空间，避免移动和碎片问题加剧。

#### ImageSpace

boot image 和相关镜像对象位于 image space。

### 18.5.8 GC 触发器

触发器包括内存阈值、分配失败、显式 GC、后台修剪和系统策略驱动。

### 18.5.9 引用处理

软引用、弱引用、虚引用和 finalizer 相关逻辑都属于 GC 处理范围。

### 18.5.10 Card Table

Card table 是写屏障的重要基础设施，用于减少全堆扫描成本。

### 18.5.11 GC 性能目标

目标通常是降低 pause time、维持吞吐、限制内存膨胀，并保证用户体验稳定。

### 18.5.12 Native 内存跟踪

ART 不仅关注 Java heap，也要跟踪 native allocations 与其对 GC 策略的影响。

### 18.5.13 对象分配

#### 分配快速路径（TLAB）

大多数小对象分配走线程本地快速路径。

#### 分配慢路径

当 TLAB 不足或需要特殊空间时，走慢路径并可能触发 GC。

### 18.5.14 Heap 构建

Heap 初始化会创建各类 space、位图、卡表和分配器结构。

### 18.5.15 进程状态与 GC 行为

前台、后台、系统服务和可感知状态不同，GC 触发与修剪策略也会不同。

### 18.5.16 Heap Trimming

堆修剪将空闲页归还系统，以降低内存占用。

### 18.5.17 Mark-Compact Collector（CMC）

CMC 通过标记与压缩减少碎片，适合特定内存回收场景。

### 18.5.18 GC 校验

ART 提供 GC verification 选项，用于调试内存损坏和写屏障错误。

---

## 18.6 类加载与链接

### 18.6.1 类加载管线

类加载涉及 class loader 查找 dex、解析类定义、创建 `mirror::Class`、验证、链接和初始化。

### 18.6.2 `ClassLinker` 初始化

ClassLinker 在运行时启动时初始化，是所有类解析、方法/字段解析和镜像空间接入的中心组件。

### 18.6.3 `FindClass`

`FindClass` 沿 class loader 链查找目标类，是许多 Java/JNI 路径的基础入口。

### 18.6.4 `DefineClass`

DefineClass 把解析出的类定义转换为运行时类对象，并注册到对应类表。

### 18.6.5 类链接

链接阶段会解析父类、接口、字段布局、方法表和运行时元数据。

### 18.6.6 类验证

验证器检查字节码正确性、类型安全和访问约束，是运行时安全的重要防线。

### 18.6.7 类初始化

类初始化负责执行静态字段初始化与 `<clinit>`，并遵循 Java 语言规范的时序规则。

### 18.6.8 接口方法表（IMT）

IMT 用于接口调用分派优化。

### 18.6.9 虚方法表（vtable）

vtable 支撑虚方法快速分派。

### 18.6.10 类链接内部流程

#### Step 1: 父类解析

首先解析并确保父类已可用。

#### Step 2: 接口解析

处理接口层次与实现关系。

#### Step 3: 虚方法链接

生成和继承 vtable 条目。

#### Step 4: 字段布局

确定实例字段与静态字段布局。

#### Step 5: IMT 填充

为接口调用生成方法表条目。

### 18.6.11 Class Loader Context

Class loader context 描述类加载器链和依赖关系，对 dexopt/odrefresh 产物有效性判断很关键。

### 18.6.12 `DexCache`

DexCache 缓存解析结果，加快后续类与方法访问。

### 18.6.13 解析：字符串、类型、方法、字段

#### String Resolution

把 dex 字符串索引解析为运行时字符串对象。

#### Type Resolution

解析类型描述符为运行时类对象。

#### Method Resolution

确定调用目标方法定义。

#### Field Resolution

解析字段所属类与偏移信息。

### 18.6.14 `ClassTable`

ClassTable 维护 class loader 已定义类的集合。

### 18.6.15 Class Hierarchy Analysis（CHA）

CHA 用于优化编译器的去虚拟化和内联判断。

### 18.6.16 `AddImageSpaces`

把 image spaces 纳入运行时，使预编译类和对象可被直接引用。

---

## 18.7 JNI Bridge

### 18.7.1 JNI 架构

JNI bridge 负责 managed/native 双向调用、引用管理、线程附着和异常传播。

### 18.7.2 `JavaVMExt`

`JavaVMExt` 管理 VM 级 JNI 状态、agent、全局引用和线程附着逻辑。

### 18.7.3 `JNIEnvExt`

`JNIEnvExt` 是线程级 JNI 环境对象，承载本地引用表、线程状态与 CheckJNI 信息。

### 18.7.4 Native 方法注册

Native 方法可通过静态命名约定或 `RegisterNatives` 动态注册。

### 18.7.5 Managed-to-Native 转换

从 Java 调用 native 方法时，ART 需要切换线程状态、建立本地栈帧并跳转到 JNI entrypoint。

### 18.7.6 Native-to-Managed 转换

native 回调 Java 时，运行时需重新附着线程、处理异常与栈遍历语义。

### 18.7.7 CheckJNI

CheckJNI 在调试环境中对 JNI API 使用进行严密校验，可帮助发现悬空引用、错误线程和非法类型使用。

### 18.7.8 JNI Critical Sections

Critical native/array access 等路径减少附加开销，但约束也更严格。

### 18.7.9 间接引用表

ART 使用间接引用表维护 local/global/weak global references，保证 GC 移动对象后引用仍可安全使用。

### 18.7.10 JNI Trampoline 类型

不同 native 方法调用路径会经过不同 trampoline，例如普通 JNI、fast native 和 critical native。

### 18.7.11 `@CriticalNative` 与 `@FastNative`

这些注解为特定 native 调用提供更低开销路径，但也限制可执行的运行时操作。

### 18.7.12 栈遍历

JNI 边界必须兼顾 GC、异常、调试器和 profiler 对栈遍历的需求。

---

## 18.8 odrefresh 与 OTA

### 18.8.1 目的

`odrefresh` 用于在 OTA 或系统变化后刷新 ART 编译产物，确保 boot image 和相关 oat/vdex 产物与当前系统状态一致。

### 18.8.2 架构

odrefresh 包括前置条件检查、缓存状态读取、需要重编译的判定、产物生成、原子替换和指标上报。

### 18.8.3 `OnDeviceRefresh` 类

该类是 odrefresh 逻辑核心，负责实际刷新流程的状态控制。

### 18.8.4 前置条件检查

系统会检查 bootclasspath 变化、产物完整性、版本兼容和可用磁盘空间等条件。

### 18.8.5 编译选项

odrefresh 需要决定 ISA、编译过滤器、image 布局和安全相关选项。

### 18.8.6 Cache Info

Cache info 描述当前已有产物、版本戳和可重用状态。

### 18.8.7 编译结果

结果可能是无需操作、部分刷新、完全重编译或失败回退。

### 18.8.8 指标与上报

odrefresh 会上报耗时、成功率、原因与结果状态，用于系统诊断与 OTA 健康度分析。

### 18.8.9 odrefresh 执行流程（详细）

详细流程涵盖：检查 → 计划 → 编译 → 校验 → staged install → 原子切换。

### 18.8.10 时间管理

为避免系统启动过慢，odrefresh 会对执行时间和条件做严格管理。

### 18.8.11 Staging 与原子性

新产物先写入 staging 区域，完成后再原子替换，以保证崩溃或中断时系统可回退。

### 18.8.12 fs-verity 集成

与 fs-verity 集成可帮助验证编译产物完整性与防篡改能力。

### 18.8.13 Boot Image 布局

Boot image 布局影响类共享、内存映射和启动性能，是 odrefresh 决策的一部分。

---

## 18.9 libnativeloader

### 18.9.1 目的

`libnativeloader` 负责为 app 和系统组件建立 native library namespace，并控制可加载库的可见性。

### 18.9.2 架构

它位于 ART / app 进程与 linker namespace 机制之间，负责命名空间创建、库公开列表与 APEX 集成。

### 18.9.3 库命名空间

命名空间机制限制不同来源 native 库的可见性，是 Android 稳定性与安全性的重要手段。

### 18.9.4 API Domains

不同域会有不同公开库集合和访问限制，例如 system、vendor、product 与 app 域。

### 18.9.5 命名命名空间

系统预定义了一些具名 namespace，供 framework、APEX 和应用使用。

### 18.9.6 为应用创建命名空间

应用启动时会根据 target SDK、是否使用原生桥接和可见库列表创建对应 namespace。

### 18.9.7 APEX Namespaces

APEX 中的 native 库也有独立 namespace，需要与 app 和系统 namespace 正确链接。

### 18.9.8 Public Libraries

仅公开库列表中的库可被普通应用直接加载，是 Android NDK 稳定性的重要运行时保障。

### 18.9.9 Native Bridge 集成

libnativeloader 还需要与 Native Bridge 协同，处理跨 ISA 库加载场景。

### 18.9.10 库加载流程

加载流程包括 namespace 选择、路径解析、可见性校验、linker 调用和错误传播。

### 18.9.11 错误处理

当加载失败时，系统需给出明确错误，并区分路径错误、可见性错误、ABI 不匹配和依赖缺失。

### 18.9.12 命名空间链接

namespace 之间可建立受控链接，用于暴露有限共享库集合。

### 18.9.13 Target SDK 版本影响

应用 target SDK 可能影响可见库策略和兼容行为。

### 18.9.14 测试命名空间行为

AOSP 包含专门测试验证 namespace 可见性与链接规则是否符合预期。

---

## 18.10 ART 调试

### 18.10.1 调试架构

ART 调试能力覆盖 JVMTI、method tracing、signal diagnostics、Perfetto、deoptimization、hidden API 和运行时 instrumentation。

### 18.10.2 可调试运行时状态

Debuggable app 和非 debuggable app 在优化级别、JIT 行为、JVMTI 能力和 hidden API 策略上可能不同。

### 18.10.3 JVMTI 实现

ART 提供 JVMTI 支持，用于断点、类重定义、对象遍历和 profiler/agent 开发。

### 18.10.4 断点

断点会影响方法入口点与 instrumentation 状态，并可能触发 deoptimization 以保证调试正确性。

### 18.10.5 类重定义

类重定义允许在调试期间替换类定义，但必须遵守运行时一致性限制。

### 18.10.6 方法追踪

Method tracing 可记录调用序列与耗时，帮助性能分析。

### 18.10.7 基于信号的诊断

ART 使用 SIGQUIT 等信号触发线程 dump、GC 状态输出和诊断信息。

### 18.10.8 `dexdump` 与 `oatdump`

二者分别用于分析 DEX 和 OAT/VDEX 结构，是理解编译与运行时产物的关键工具。

### 18.10.9 `imgdiag`

imgdiag 用于分析 image 空间与镜像对象情况。

### 18.10.10 Perfetto 集成

Perfetto 能追踪 ART 启动、类加载、JIT、GC 和方法执行相关事件。

### 18.10.11 ART Metrics

ART 上报启动、编译、GC、JIT 和运行时健康指标。

### 18.10.12 诊断命令

#### SIGQUIT 线程转储

```text
# Output written to /data/anr/traces.txt or logcat
```

#### `dumpsys meminfo`

该命令可提供 Java heap、native heap 和 ART 相关内存信息。

#### ART 专用系统属性

系统属性可控制 GC/JIT/class loading/JNI 等详细日志级别。

### 18.10.13 Runtime Instrumentation

Instrumentation 允许 ART 在方法调用、字段访问和调试事件上插入额外逻辑。

### 18.10.14 反优化（Deoptimization）

当调试、类重定义或假设失效时，ART 可以把已编译代码退回解释执行或更保守路径。

### 18.10.15 Hidden API Enforcement

ART 在运行时执行 hidden API 访问限制，是平台兼容与安全策略的一部分。

### 18.10.16 ART 测试基础设施

AOSP 提供大量 runtime、compiler、GC、dex2oat 和 JVMTI 测试。

### 18.10.17 ART Daemon（`artd`）

`artd` 用于某些运行时与编译服务化场景，承担后台任务与系统集成角色。

### 18.10.18 `dexoptanalyzer`

该工具帮助分析某个应用在当前条件下是否需要 dexopt 以及可能采用的编译策略。

---

## 18.11 动手实践

### Exercise 18.1 -- 检查一个 DEX 文件

```bash
# Build dexdump if needed
# Dump the header of framework.jar's DEX file
# Dump a specific class
```

### Exercise 18.2 -- 检查 OAT Header 元数据

```bash
# Dump the boot image OAT header
# Look for the compiler filter, boot classpath, and compilation reason
```

### Exercise 18.3 -- 观察 JIT 编译

```bash
# Enable JIT verbose logging
# Start an app and observe JIT compilations in logcat
```

### Exercise 18.4 -- 触发并观察 GC

```bash
# Enable GC verbose logging
# Force GC via DDMS or:
# Observe GC log
```

### Exercise 18.5 -- 为应用生成 profile 并触发 bg-dexopt

```bash
# Get the current profile for an app
# Force profile compilation
# Check the compilation result
```

### Exercise 18.6 -- 检查 odrefresh 行为

```bash
# Check current odrefresh status
# Check which ISAs have boot images
# Force odrefresh to check artifacts
```

### Exercise 18.7 -- 检查 Native Library Namespaces

```bash
# List public libraries
# Check vendor public libraries
# See the linker namespace configuration for an app process
```

### Exercise 18.8 -- 使用 JVMTI 调试

```bash
# Enable debuggable mode for an app
# List available JVMTI agents
```

### Exercise 18.9 -- 走读类加载链路

从 class loader、DexPathList、ClassLinker、FindClass 和 DefineClass 逐层分析某个类的加载路径。

### Exercise 18.10 -- 测量 GC Pause 时间

```bash
# Dump ART runtime info
# Read the trace file
```

### Exercise 18.11 -- 手工构建并运行 dex2oat

```bash
# Run dex2oat with verbose output
```

### Exercise 18.12 -- 追踪 ART 启动

```bash
# Record a Perfetto trace with ART categories
```

### Exercise 18.13 -- 检查 `ArtMethod` 内部

```bash
# Dump all methods of a specific class
# Then analyze with Android Studio's heap profiler
# Alternatively, use SIGQUIT to see method info in the trace
```

### Exercise 18.14 -- 比较编译过滤器

```bash
# Verify only (fastest compile, slowest run)
# Speed (compile everything)
# Compare file sizes
# Compare using oatdump
```

### Exercise 18.15 -- 监控类加载

```bash
# Enable verbose class loading
# Launch an app
# Watch class loading in logcat
```

### Exercise 18.16 -- 检查 Boot Image

```bash
# List boot image files
# Dump boot image info
# Count classes in the boot image
```

### Exercise 18.17 -- Profile-Guided Optimization 工作流

```bash
# Step 1: Install app (gets verify filter initially)
# Step 2: Use the app to generate profile data
# Step 3: Check profile exists
# Step 4: Merge profiles
# Step 5: Verify the result
```

### Exercise 18.18 -- 探索 GC Spaces

```bash
# Trigger heap dump via SIGQUIT
# Look for space information in the trace
```

### Exercise 18.19 -- VDEX 文件分析

```bash
# Find the VDEX file for an app
# Use oatdump to examine the VDEX
# Check verifier dependencies
```

### Exercise 18.20 -- 理解 `ArtMethod` 入口点

分析解释器入口、quick compiled code 入口和 JNI 入口的切换逻辑。

### Exercise 18.21 -- 检查 Monitor 竞争

```bash
# Enable monitor logging
```

### Exercise 18.22 -- 端到端 PGO 编译

```bash
# 1. Check initial compilation state
# 2. Clear existing profiles
# 3. Use the app normally for 5 minutes to generate profile data
# 4. Dump the profile
# 5. Trigger PGO compilation
# 6. Verify the new compilation state
# 7. Compare cold-start time before and after PGO
```

### Exercise 18.23 -- 检查 Lock Word

```bash
# Capture a heap dump
# Analyze with Android Studio's Memory Profiler or jhat
# Look for objects with non-zero lock word values
# indicating active monitors or hash codes
```

### Exercise 18.24 -- 比较解释器与编译代码性能

```bash
# Run with interpreter only (no JIT, no AOT)
# Run the benchmark and record time
# Run with JIT enabled
# Run the benchmark again and compare
# Run with full AOT
# Run the benchmark again and compare all three
```

### Exercise 18.25 -- 模拟 OTA 并观察 odrefresh

```bash
# Check current odrefresh cache info
# Delete artifacts to simulate need for recompilation
# Trigger odrefresh manually
# Check metrics
```

## Summary

## 总结

ART 是 Android 应用执行的核心基础设施，其职责可概括为：

| 组件 | 核心职责 |
|------|----------|
| `Runtime` | 全局运行时状态与系统初始化 |
| `ClassLinker` | 类加载、解析、验证与链接 |
| `Heap` / GC | 内存分配、回收与对象移动 |
| `dex2oat` | 安装时和系统级 AOT 编译 |
| JIT | 运行时热点编译与 profile 收集 |
| JNI bridge | managed/native 双向调用 |
| `odrefresh` | OTA 后编译产物刷新 |
| `libnativeloader` | native 库命名空间与加载策略 |

ART 的关键架构思想包括：

1. **解释器、JIT 与 AOT 分层协同**。
2. **DEX 作为统一执行输入格式**。
3. **boot image、app image 与 OAT/VDEX 共同降低启动成本**。
4. **类加载、验证、链接和 hidden API 控制深度整合**。
5. **GC 与线程暂停机制围绕移动对象和低停顿优化设计**。
6. **JNI 与 native namespace 机制共同维持 Java/native 边界安全**。

### Architecture Cross-Reference

ART 与系统其他子系统密切相关：

- 与 PackageManager / installd 配合完成 dexopt。
- 与 Zygote 协同完成进程启动。
- 与 linker / libnativeloader 管理 native 库加载。
- 与 Perfetto、JVMTI、debugger 集成提供调试能力。

### Performance Characteristics

ART 性能主要受以下因素影响：

- 编译过滤器与 profile 命中率
- boot image / app image 命中情况
- JIT 热点识别速度
- GC 暂停与内存布局
- 类加载与验证路径复杂度
- JNI 边界频率

### Version History

ART 从 Dalvik 时代的替代方案发展为 Android 统一运行时，经历了：

- 早期以 AOT 为主
- 引入 JIT 混合模式
- 引入 Nterp 与更现代 GC
- 通过 odrefresh 和模块化机制增强系统可更新性

掌握 ART 后，可以沿着“DEX → 类加载 → 执行模式 → GC/JIT/AOT → 调试工具”这条主线理解 Android 应用在运行时的真实执行路径。
