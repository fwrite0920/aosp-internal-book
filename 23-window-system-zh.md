# 第 23 章：窗口系统

Android 窗口系统负责把 Activity、Task、Display、Surface、输入焦点、Insets、多窗口和过渡动画组织成统一的容器树与显示模型。它横跨 `WindowManagerService`、`WindowContainer` 层级、WM Shell、Transition、DisplayArea、Insets、输入系统和 SurfaceControl 事务，是 Android 界面系统的核心支柱之一。本章从 AOSP 源码视角系统梳理窗口系统的结构与关键设计模式。

---

## 23.1 窗口管理架构

### 23.1.1 架构概览

Android 窗口系统可概括为三层：

1. **WMS Core**：负责核心容器树、窗口状态、显示、焦点和布局。
2. **WM Shell**：负责更高层的用户可见窗口交互功能，例如 split screen、PiP、desktop mode 和 transitions。
3. **Surface / Input / Insets 集成层**：负责 surface 事务、输入路由和系统栏/IME/insets 相关行为。

### 23.1.2 `WindowManagerService`

`WindowManagerService` 是窗口系统的核心 Java 服务，负责：

- 窗口添加与移除
- 显示与布局
- 焦点管理
- 输入窗口同步
- 与 ATMS、InputManager、SurfaceFlinger、DisplayManager 协作

### 23.1.3 `WindowContainer` 层级

窗口系统的核心组织方式是 `WindowContainer` 树。Display、Task、TaskFragment、ActivityRecord、WindowToken 和 WindowState 都嵌入这一容器模型中。

### 23.1.4 完整类层级

从上到下，典型层级包括：

- `RootWindowContainer`
- `DisplayContent`
- `DisplayArea` / `TaskDisplayArea`
- `Task`
- `TaskFragment`
- `ActivityRecord`
- `WindowToken`
- `WindowState`

### 23.1.5 `WindowState`

`WindowState` 表示一个具体窗口实例，保存 LayoutParams、surface、可见性、输入特性、焦点状态、token 和 display 归属等信息。

### 23.1.6 `DisplayContent`

`DisplayContent` 表示一个显示设备上的窗口根容器，负责该 display 的焦点、布局、显示区域、旋转与策略状态。

### 23.1.7 `RootWindowContainer`

它是所有显示与窗口层级的全局根节点，是窗口树遍历与全局状态计算的起点。

### 23.1.8 Surface 放置周期

窗口系统通常按“收集变化 → 计算布局/层级 → 生成 SurfaceControl.Transaction → 原子应用”的周期推进 surface 放置。

### 23.1.9 WMS 内部数据结构

WMS 维护大量内部映射与集合，如 token 映射、会话映射、显示映射、焦点状态、窗口列表和动画状态缓存。

### 23.1.10 Window Session

`Session` 是应用客户端与 WMS 之间的 Binder 会话对象，表示一个窗口客户端上下文，是权限与资源归属的重要边界。

### 23.1.11 全局锁与线程安全

WMS 使用 `WindowManagerGlobalLock` 保护关键容器树状态，并通过专用线程、延迟执行与事务边界减少并发问题。

### 23.1.12 `BLASTSyncEngine`

BLASTSyncEngine 用于协调一组窗口/容器变更的同步提交，确保复杂过渡和布局更新在视觉上保持一致。

### 23.1.13 `DisplayContent` 内部

DisplayContent 内部不仅包含窗口树，还承载 DisplayArea 策略、焦点、IME 策略和 per-display 输入/布局状态。

---

## 23.2 WM Shell Library

### 23.2.1 Shell 与 Core：架构拆分

WMS Core 负责底层窗口真实状态与权限边界；Shell 则实现更高层、可快速演化的窗口交互功能。这种拆分让 Android 在不破坏核心服务稳定性的前提下推进新 UI 形态。

### 23.2.2 Shell 目录结构

Shell 源码通常位于 WindowManager Shell 相关模块中，按 split screen、PiP、transitions、desktop mode、common infrastructure 等子模块组织。

### 23.2.3 `ShellTaskOrganizer`

ShellTaskOrganizer 是 Shell 管理 task 生命周期与变化的重要入口，可监听 task appearance、vanish 和 info 更新。

### 23.2.4 依赖注入架构

WM Shell 常使用依赖注入组织组件，方便不同 feature 模块复用 common infrastructure 并按需启用。

### 23.2.5 Shell 通信模型

Shell 与 WMS Core 之间主要通过 organizer、transition、WindowContainerTransaction 和 Binder/回调模型交互。

### 23.2.6 线程模型

WM Shell 使用独立线程、主线程与动画线程协同工作，以避免阻塞 system_server 主路径。

---

## 23.3 Transition 系统

### 23.3.1 概览：从传统 `AppTransition` 到 Shell Transitions

传统窗口切换更依赖 WMS 内建动画路径。现代 Android 则逐步转向统一的 Shell Transition 架构，以支持更复杂的窗口模式与特性模块协同。

### 23.3.2 `TransitionController`（WM Core 侧）

TransitionController 负责在核心窗口树侧收集过渡变化，并生成 transition 对象交给 Shell 播放。

### 23.3.3 `Transition`（WM Core 侧）

Core 侧 Transition 表示一次容器变化事务的语义集合，包括打开、关闭、改变与旋转等。

### 23.3.4 `Transitions`（Shell 侧 —— 动画播放器）

Shell 侧 `Transitions` 负责接收 transition 数据、选择 handler、播放动画并在结束后回传完成状态。

### 23.3.5 Transition Handler 链

多个 handler 按顺序尝试处理同一过渡，例如默认处理器、远端处理器、特性模块处理器和混合处理器。

### 23.3.6 Transition 生命周期：端到端流程

典型流程：

1. WM Core 收集变化。
2. 创建 transition。
3. Shell 接收并选择 handler。
4. 构造 `TransitionInfo`。
5. 播放 SurfaceControl 动画。
6. 完成后通知 Core 提交最终状态。

### 23.3.7 `TransitionInfo`：数据契约

TransitionInfo 是 Core 与 Shell 之间的核心数据契约，描述所有变化容器、边界、模式、flags 和 surface leash 信息。

### 23.3.8 Transition 合并

多个过渡可能被合并，以减少视觉跳变和中间态切换。

### 23.3.9 并行轨道

系统允许不同 transition track 并行执行，以在复杂系统 UI 与应用变化间提升吞吐与流畅度。

### 23.3.10 `DefaultTransitionHandler`

默认处理器负责常规 app/task/window 变化动画，是 Shell transition 的基础实现。

### 23.3.11 `RemoteTransitionHandler`

Remote handler 允许外部组件接管动画逻辑，如 launcher 或 OEM UI。

---

## 23.4 多窗口架构

### 23.4.1 窗口模式

Windowing mode 包括 fullscreen、split screen、PiP、freeform、desktop 等，是任务容器行为的高层约束。

### 23.4.2 分屏架构

Split screen 通过两个主要 task 容器与 divider/organizer 协作，实现双任务并列显示。

### 23.4.3 Picture-in-Picture（PiP）

PiP 将单个任务缩放到浮动小窗中，伴随严格的 bounds、动画与输入策略。

### 23.4.4 Freeform 模式

Freeform 支持可自由定位和调整大小的窗口，是桌面化体验的基础模式之一。

### 23.4.5 Desktop 模式

Desktop mode 在 freeform 基础上提供更完整的窗口桌面体验，包括装饰、拖拽和窗口管理能力。

### 23.4.6 多窗口 Task 流

多窗口系统本质上是 task 和 TaskFragment 在不同 display area/windowing mode 下的重新组织。

### 23.4.7 `WindowContainerTransaction`

WCT 是 Shell 修改窗口容器树的重要工具，用于原子提交 bounds、windowing mode、reparent 等变更。

### 23.4.8 `Task` 与 `TaskFragment` 层级

TaskFragment 允许在 task 内做更细粒度组织，是现代多窗口与 activity embedding 的关键抽象。

### 23.4.9 ActivityRecord 与窗口-Activity 关系

ActivityRecord 是 activity 生命周期模型，但其显示行为通过 WindowState/WindowToken 进入窗口系统，两者在容器树中高度耦合。

### 23.4.10 Bounds 计算

窗口 bounds 受 display、cutout、windowing mode、display area、policy 和 shell organizer 共同影响。

---

## 23.5 多显示

### 23.5.1 `DisplayContent` 与显示模型

每个显示设备对应一个 DisplayContent，系统可同时管理多个物理或虚拟显示。

### 23.5.2 显示标识

Display id、display group 与 display topology 共同描述多显示系统。

### 23.5.3 虚拟显示

虚拟显示允许内容渲染到非物理目标，如投屏、录屏、远程桌面或辅助显示场景。

### 23.5.4 跨显示窗口移动

任务和窗口在多显示之间移动需要重新计算容器归属、焦点和输入目标。

### 23.5.5 每显示焦点

不同 display 可拥有独立焦点状态，这影响输入路由和可见性策略。

### 23.5.6 显示组与拓扑

多个显示可被分组并形成拓扑关系，供输入、系统栏和窗口策略使用。

### 23.5.7 每显示 IME 策略

输入法窗口与 inset 策略可按 display 维度独立管理。

### 23.5.8 显示配置与覆盖

系统支持分辨率、密度和旋转等 display config 的动态覆盖，用于开发测试和特定产品形态。

---

## 23.6 输入系统集成

### 23.6.1 从 InputFlinger 到 WMS 的管线

InputFlinger 需要从 WMS 获取窗口列表、焦点、可触区域和输入特性，才能正确把事件路由给目标窗口。

### 23.6.2 `InputMonitor`

InputMonitor 是 WMS 与输入系统的桥梁之一，用于同步输入窗口信息。

### 23.6.3 窗口目标选择

事件目标由窗口顺序、可见区域、焦点和 flags 共同决定。

### 23.6.4 焦点管理

焦点不仅影响按键事件，还影响部分手势和系统 UI 行为。

### 23.6.5 输入与显示拓扑

在多显示场景中，输入系统需要理解显示拓扑和当前输入目标所在 display。

### 23.6.6 `InputChannel`：事件投递机制

InputChannel 是窗口接收输入事件的实际通道，是输入与窗口系统连接的关键对象。

### 23.6.7 窗口输入 Flags

不同 flags 控制窗口是否可触、是否可聚焦、是否应被遮挡忽略等。

### 23.6.8 输入消费者

系统还支持专门的 input consumer，用于导航手势、系统栏或特定全局交互场景。

### 23.6.9 Spy Windows

Spy windows 能观察输入流而不一定成为主消费目标，适用于监控或特定调试/功能场景。

---

## 23.7 Surface 与 Leash

### 23.7.1 `SurfaceControl` 层级

窗口系统最终通过 `SurfaceControl` 与 SurfaceFlinger 交互。每个窗口或容器可能对应一个或多个 surface 节点。

### 23.7.2 动画 Leash 机制

动画通常不直接作用于原始 surface，而是创建一个中间 leash 容器，把目标 surface 挂载到其下，再对 leash 做变换。

### 23.7.3 动画类型

常见类型包括打开、关闭、改变、旋转、PiP 进入/退出和 shell 特性动画。

### 23.7.4 Layer 分配与 Leash 交互

Leash 的引入会影响 layer assignment 和层级关系，需要系统在动画前后正确恢复原始顺序。

### 23.7.5 动画转移

动画可在容器变化过程中转移到新的 animatable 对象上，以维持视觉连续性。

### 23.7.6 `Animatable` 接口

Animatable 抽象为不同容器提供统一动画控制入口。

### 23.7.7 Leash 创建细节

创建 leash 时需考虑 parent、layer、裁剪、初始变换和事务同步。

### 23.7.8 事务批处理与原子应用

窗口系统大量依赖 `SurfaceControl.Transaction` 批处理并原子提交，避免中间态闪烁。

### 23.7.9 同步事务 vs 待提交事务

系统会区分立即同步应用的 transaction 与挂起等待布局/transition 统一提交的 transaction。

---

## 23.8 窗口类型与 Z 顺序

### 23.8.1 窗口类型范围

Android 定义了应用窗口、子窗口和系统窗口等多类 type，每类具备不同权限与层级语义。

### 23.8.2 应用窗口类型

普通 Activity 窗口、starting window、应用面板等属于应用窗口体系。

### 23.8.3 子窗口类型

子窗口依附于父窗口，例如面板、对话框和某些浮动 UI。

### 23.8.4 系统窗口类型

系统窗口类型包括状态栏、输入法、锁屏、toast、覆盖层等，受更严格权限控制。

### 23.8.5 Z-Order Layer 分配

WMS 会根据窗口类型、容器归属和策略决定 layer，从而控制前后显示顺序。

### 23.8.6 基于 DisplayArea 的 Z 排序

现代系统越来越依赖 DisplayArea 做更结构化的层级与区域管理。

### 23.8.7 `DisplayAreaPolicy` 与 `DisplayAreaPolicyBuilder`

DisplayAreaPolicy 把不同窗口类型映射到适当显示区域，是现代 WMS 架构的重要部分。

### 23.8.8 DisplayArea 变体

不同 DisplayArea 变体可用于应用区、系统栏区、IME 区或特定 shell 功能区域。

### 23.8.9 `DisplayAreaOrganizer`

Organizer 允许高层模块管理 DisplayArea 行为，增强 shell 可定制性。

### 23.8.10 窗口类型到 DisplayArea 的映射

窗口类型并不直接决定 layer，而是先映射到 DisplayArea，再在该区域内进一步计算层级。

---

## 23.9 Insets 系统

### 23.9.1 什么是 Insets？

Insets 描述系统栏、IME、cutout、gesture 区域等对应用可用内容区域的影响。

### 23.9.2 `InsetsStateController`

InsetsStateController 负责全局管理各类 inset source 的状态与同步。

### 23.9.3 InsetsSource 类型

典型 source 包括 status bar、navigation bar、IME、display cutout、system gestures 等。

### 23.9.4 Insets 流：从提供者到消费者

Insets 从 provider（如系统栏、IME）生成，经 WMS 聚合，最终传递给窗口消费者和 app 端布局系统。

### 23.9.5 本地 Insets Source

某些窗口可以本地提供 inset source，例如嵌入式系统 UI 场景。

### 23.9.6 被排除的 Insets 类型

系统可对某些窗口排除特定 insets 类型，以避免错误消费。

### 23.9.7 IME Insets

IME 是最动态的 insets source 之一，与焦点窗口和 per-display policy 紧密耦合。

### 23.9.8 Insets 动画

Insets 动画让应用平滑响应系统栏和 IME 的显隐变化。

### 23.9.9 Edge-to-Edge 与 Insets 消费

现代 edge-to-edge 布局要求应用正确理解并消费 insets，而不是依赖传统稳定内容区域。

### 23.9.10 安全区域边界

安全区域边界用于描述 cutout、圆角等不可安全绘制区域。

---

## 23.10 Shell Features

### 23.10.1 Picture-in-Picture（PiP）

PiP 是 WM Shell 中的重要特性模块，负责小窗视频和活动浮窗体验。

### 23.10.2 Bubbles

Bubbles 把会话型 UI 组织为浮动交互单元，需要窗口、通知与 shell 协同。

### 23.10.3 Split Screen

Split screen 是最典型的 shell 多任务特性之一。

### 23.10.4 Desktop Windowing

桌面窗口化模式强化自由窗、装饰栏和多窗口操作能力。

### 23.10.5 Predictive Back

Predictive Back 通过 shell/wm/input 协同，把返回手势与过渡动画统一起来。

### 23.10.6 其他 Shell 特性

还包括展开屏、letterbox、task organizer 特性、recents 动画等。

### 23.10.7 Feature Module 模式

Shell 功能通常以 feature module 模式实现，便于插拔、测试和灰度。

### 23.10.8 `MixedTransitionHandler`：跨特性交叉协调

当一次过渡同时涉及多种 shell 特性时，MixedTransitionHandler 用于协调它们共同完成动画。

### 23.10.9 Window Decorations

Desktop/freeform 等场景下，窗口装饰由 shell 管理，是现代桌面化体验的基础。

### 23.10.10 Shell 初始化与生命周期

Shell 组件有自己的初始化顺序、组织者注册与生命周期管理。

### 23.10.11 Shell 错误处理

Shell 功能失败时通常要能安全降级回 core 行为，避免破坏基础窗口系统稳定性。

### 23.10.12 性能监控

Shell 需要监控 transition 时长、布局开销和 surface transaction 复杂度。

---

## 23.11 详细参考

### 23.11.1 三部分配套报告

本章可与 Activity/Window 管理、动画系统和显示/渲染相关章节联合阅读，形成完整知识图谱。

### 23.11.2 快速章节索引

当定位问题时，可根据目标主题快速跳到多窗口、输入、insets、transition 或 surface/leash 对应部分。

### 23.11.3 关键源码文件参考

| 路径 | 用途 |
|------|------|
| `frameworks/base/services/core/java/com/android/server/wm/WindowManagerService.java` | WMS 主体 |
| `frameworks/base/services/core/java/com/android/server/wm/DisplayContent.java` | 单显示根容器 |
| `frameworks/base/services/core/java/com/android/server/wm/WindowState.java` | 窗口状态对象 |
| `frameworks/base/libs/WindowManager/Shell/` | WM Shell 特性模块 |
| `frameworks/base/core/java/android/view/Insets*` | Insets 客户端接口 |

### 23.11.4 调试窗口系统

```bash
# Full WMS state dump
# Windows only
# Display state
# Transitions
# Focused window
# Window containers hierarchy
# Display areas
# Input dispatch state
```

### 23.11.5 架构速查表

- WMS Core 维护真实窗口树
- Shell 负责高层窗口特性与动画
- SurfaceControl 负责最终表面操作
- Input 与 Insets 是窗口系统的并行集成子系统

## Summary

## 总结

Android 窗口系统的核心架构可概括为：

| 层级 | 核心组件 |
|------|----------|
| Core | `WindowManagerService`, `WindowContainer`, `WindowState`, `DisplayContent` |
| Shell | `ShellTaskOrganizer`, transitions, PiP, split, desktop |
| Surface | `SurfaceControl`, leash, transaction, BLAST sync |
| Input/Insets | `InputMonitor`, input channel, insets state |

### Architecture Recap

窗口系统围绕“容器树 + 事务提交 + 高层 shell 组织者”展开，是 Activity 系统、输入系统、动画系统和显示系统的交汇点。

### Key Design Patterns

1. **容器树模式**：所有窗口与任务状态统一纳入树结构。
2. **Leash 模式**：动画通过中间容器而不是直接作用原表面。
3. **事务批处理**：所有视觉变化尽量原子提交。
4. **Core/Shell 分层**：稳定核心与快速演进特性分离。
5. **Policy/Organizer 模式**：通过策略与组织者实现高层可定制行为。

### Scale of the System

窗口系统的复杂度来自多显示、多窗口、动画、输入、Insets、Shell 功能和 system_server 核心逻辑的深度耦合。

### Evolution Direction

Android 窗口系统正持续向更模块化、更 shell 化、更适合大屏/桌面/折叠设备和更强过渡系统的方向演进。
